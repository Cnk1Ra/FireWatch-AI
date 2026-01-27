"""
ML-based validation for user fire reports
Uses multiple signals to validate crowdsourced reports
"""

import logging
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime
import math

logger = logging.getLogger(__name__)


@dataclass
class ValidationPrediction:
    """ML validation prediction for a report."""
    is_valid: bool
    confidence: float  # 0-1

    # Individual model scores
    photo_score: Optional[float] = None
    location_score: Optional[float] = None
    temporal_score: Optional[float] = None
    text_score: Optional[float] = None
    satellite_score: Optional[float] = None

    # Validation details
    validation_reasons: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    # Model info
    model_version: str = "1.0"
    processing_time_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "is_valid": self.is_valid,
            "confidence": self.confidence,
            "scores": {
                "photo": self.photo_score,
                "location": self.location_score,
                "temporal": self.temporal_score,
                "text": self.text_score,
                "satellite": self.satellite_score
            },
            "validation_reasons": self.validation_reasons,
            "warnings": self.warnings,
            "model_version": self.model_version
        }


class MLReportValidator:
    """
    ML-based fire report validation.

    Combines multiple models and signals to validate reports.
    """

    # Validation thresholds
    VALIDATION_THRESHOLD = 0.6
    HIGH_CONFIDENCE_THRESHOLD = 0.85

    # Score weights
    WEIGHTS = {
        "photo": 0.30,
        "location": 0.20,
        "temporal": 0.15,
        "text": 0.10,
        "satellite": 0.25
    }

    def __init__(
        self,
        photo_model_path: Optional[str] = None,
        text_model_path: Optional[str] = None
    ):
        """
        Initialize validator.

        Args:
            photo_model_path: Path to photo analysis model
            text_model_path: Path to text classification model
        """
        self.photo_model_path = photo_model_path
        self.text_model_path = text_model_path

        self._photo_model = None
        self._text_model = None

        self._load_models()

    def _load_models(self) -> None:
        """Load ML models."""
        # Photo model
        if self.photo_model_path:
            try:
                import tensorflow as tf
                self._photo_model = tf.keras.models.load_model(
                    self.photo_model_path
                )
                logger.info("Loaded photo validation model")
            except Exception as e:
                logger.warning(f"Could not load photo model: {e}")

        # Text model
        if self.text_model_path:
            try:
                import joblib
                self._text_model = joblib.load(self.text_model_path)
                logger.info("Loaded text validation model")
            except Exception as e:
                logger.warning(f"Could not load text model: {e}")

    def validate(
        self,
        latitude: float,
        longitude: float,
        reported_at: datetime,
        description: Optional[str] = None,
        photo_data: Optional[bytes] = None,
        satellite_hotspots: Optional[List[Dict]] = None,
        weather_data: Optional[Dict] = None
    ) -> ValidationPrediction:
        """
        Validate a fire report using ML.

        Args:
            latitude: Report latitude
            longitude: Report longitude
            reported_at: Report timestamp
            description: Text description
            photo_data: Photo bytes
            satellite_hotspots: Nearby satellite detections
            weather_data: Current weather

        Returns:
            ValidationPrediction
        """
        import time
        start_time = time.time()

        result = ValidationPrediction(
            is_valid=False,
            confidence=0.5
        )

        scores = {}
        reasons = []

        # 1. Photo validation
        if photo_data:
            photo_score = self._validate_photo(photo_data)
            scores["photo"] = photo_score
            result.photo_score = photo_score

            if photo_score >= 0.7:
                reasons.append("Photo shows fire/smoke indicators")
            elif photo_score < 0.3:
                result.warnings.append("Photo does not clearly show fire")

        # 2. Location validation
        location_score = self._validate_location(latitude, longitude)
        scores["location"] = location_score
        result.location_score = location_score

        if location_score >= 0.7:
            reasons.append("Location in fire-prone area")

        # 3. Temporal validation
        temporal_score = self._validate_temporal(reported_at, weather_data)
        scores["temporal"] = temporal_score
        result.temporal_score = temporal_score

        if temporal_score >= 0.7:
            reasons.append("Favorable fire conditions")

        # 4. Text validation
        if description:
            text_score = self._validate_text(description)
            scores["text"] = text_score
            result.text_score = text_score

            if text_score >= 0.7:
                reasons.append("Description consistent with fire report")
            elif text_score < 0.3:
                result.warnings.append("Description unclear or inconsistent")

        # 5. Satellite cross-validation
        if satellite_hotspots:
            satellite_score = self._validate_with_satellite(
                latitude, longitude, reported_at, satellite_hotspots
            )
            scores["satellite"] = satellite_score
            result.satellite_score = satellite_score

            if satellite_score >= 0.7:
                reasons.append("Confirmed by satellite detection")

        # Calculate weighted confidence
        total_weight = 0
        weighted_sum = 0

        for key, score in scores.items():
            weight = self.WEIGHTS.get(key, 0.1)
            weighted_sum += score * weight
            total_weight += weight

        if total_weight > 0:
            result.confidence = weighted_sum / total_weight

        # Determine validity
        result.is_valid = result.confidence >= self.VALIDATION_THRESHOLD
        result.validation_reasons = reasons

        # High confidence detection
        if result.confidence >= self.HIGH_CONFIDENCE_THRESHOLD:
            result.validation_reasons.insert(0, "High confidence detection")

        result.processing_time_ms = (time.time() - start_time) * 1000

        logger.info(
            f"Report validation: valid={result.is_valid}, "
            f"confidence={result.confidence:.2f}"
        )

        return result

    def _validate_photo(self, photo_data: bytes) -> float:
        """Validate photo using ML."""
        # Use photo model if available
        if self._photo_model is not None:
            try:
                import cv2
                import numpy as np

                # Decode image
                nparr = np.frombuffer(photo_data, np.uint8)
                image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

                if image is None:
                    return 0.3

                # Preprocess
                resized = cv2.resize(image, (224, 224))
                normalized = resized / 255.0
                batch = np.expand_dims(normalized, axis=0)

                # Predict
                prediction = self._photo_model.predict(batch, verbose=0)
                return float(prediction[0][0])

            except Exception as e:
                logger.error(f"Photo validation error: {e}")

        # Fallback: use color analysis
        return self._analyze_photo_colors(photo_data)

    def _analyze_photo_colors(self, photo_data: bytes) -> float:
        """Analyze photo colors for fire/smoke indicators."""
        try:
            import cv2
            import numpy as np

            nparr = np.frombuffer(photo_data, np.uint8)
            image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

            if image is None:
                return 0.3

            # Convert to HSV
            hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)

            # Fire colors (red/orange/yellow)
            fire_lower = np.array([0, 100, 150])
            fire_upper = np.array([35, 255, 255])
            fire_mask = cv2.inRange(hsv, fire_lower, fire_upper)

            # Smoke colors (gray)
            smoke_lower = np.array([0, 0, 100])
            smoke_upper = np.array([180, 40, 220])
            smoke_mask = cv2.inRange(hsv, smoke_lower, smoke_upper)

            # Calculate ratios
            total = image.shape[0] * image.shape[1]
            fire_ratio = np.sum(fire_mask > 0) / total
            smoke_ratio = np.sum(smoke_mask > 0) / total

            # Score based on fire/smoke presence
            if fire_ratio > 0.05 and smoke_ratio > 0.1:
                return 0.85  # Both fire and smoke
            elif fire_ratio > 0.03:
                return 0.7  # Fire colors
            elif smoke_ratio > 0.15:
                return 0.6  # Smoke only
            elif fire_ratio > 0.01 or smoke_ratio > 0.05:
                return 0.4  # Some indicators
            else:
                return 0.2  # No clear indicators

        except Exception:
            return 0.5  # Default on error

    def _validate_location(
        self,
        latitude: float,
        longitude: float
    ) -> float:
        """Validate location plausibility."""
        # Check if in Brazil
        if not (-34 <= latitude <= 5 and -74 <= longitude <= -34):
            return 0.2  # Outside Brazil

        # Fire-prone biomes
        biome_scores = [
            # (south, west, north, east, score)
            (-10, -74, 5, -44, 0.6),     # Amazonia
            (-24, -60, -2, -41, 0.85),   # Cerrado
            (-22, -59, -15, -54, 0.9),   # Pantanal
            (-17, -46, -2, -35, 0.7),    # Caatinga
            (-30, -55, -3, -34, 0.5),    # Mata Atlantica
        ]

        for south, west, north, east, score in biome_scores:
            if south <= latitude <= north and west <= longitude <= east:
                return score

        return 0.4  # Unknown area

    def _validate_temporal(
        self,
        reported_at: datetime,
        weather_data: Optional[Dict]
    ) -> float:
        """Validate temporal factors."""
        score = 0.5

        # Check time of day (fires more common in afternoon)
        hour = reported_at.hour
        if 12 <= hour <= 18:
            score += 0.2
        elif 10 <= hour <= 20:
            score += 0.1

        # Check weather conditions
        if weather_data:
            temp = weather_data.get("temperature", 25)
            humidity = weather_data.get("humidity", 50)

            if temp >= 30 and humidity <= 40:
                score += 0.3  # High fire risk conditions
            elif temp >= 25 and humidity <= 50:
                score += 0.15

        # Check season (dry season in Brazil: May-September)
        month = reported_at.month
        if 5 <= month <= 9:
            score += 0.1  # Dry season

        return min(1.0, score)

    def _validate_text(self, description: str) -> float:
        """Validate text description."""
        # Use text model if available
        if self._text_model is not None:
            try:
                prediction = self._text_model.predict([description])[0]
                return float(prediction)
            except Exception:
                pass

        # Fallback: keyword analysis
        return self._analyze_text_keywords(description)

    def _analyze_text_keywords(self, text: str) -> float:
        """Analyze text for fire-related keywords."""
        text_lower = text.lower()

        # Positive indicators
        fire_keywords = [
            "fogo", "incendio", "queimada", "chamas", "fumaca",
            "queimando", "ardendo", "pegando fogo", "labaredas"
        ]

        # Negative indicators
        negative_keywords = [
            "teste", "brincadeira", "falso", "mentira",
            "engano", "erro"
        ]

        # Count matches
        positive_count = sum(1 for kw in fire_keywords if kw in text_lower)
        negative_count = sum(1 for kw in negative_keywords if kw in text_lower)

        if negative_count > 0:
            return 0.2

        if positive_count >= 3:
            return 0.85
        elif positive_count >= 2:
            return 0.7
        elif positive_count >= 1:
            return 0.5
        else:
            return 0.3

    def _validate_with_satellite(
        self,
        latitude: float,
        longitude: float,
        reported_at: datetime,
        hotspots: List[Dict]
    ) -> float:
        """Cross-validate with satellite hotspots."""
        if not hotspots:
            return 0.4  # No data to validate against

        closest_distance = float('inf')
        time_diff_hours = float('inf')

        for hotspot in hotspots:
            # Calculate distance
            h_lat = hotspot.get("latitude", 0)
            h_lon = hotspot.get("longitude", 0)

            distance = math.sqrt(
                (latitude - h_lat)**2 +
                (longitude - h_lon)**2
            ) * 111  # km

            if distance < closest_distance:
                closest_distance = distance

                # Calculate time difference
                h_time = hotspot.get("acq_datetime")
                if h_time:
                    if isinstance(h_time, str):
                        h_time = datetime.fromisoformat(h_time.replace(" ", "T"))
                    diff = abs((reported_at - h_time).total_seconds() / 3600)
                    time_diff_hours = diff

        # Score based on distance and time
        if closest_distance <= 2:
            distance_score = 1.0
        elif closest_distance <= 5:
            distance_score = 0.8
        elif closest_distance <= 10:
            distance_score = 0.6
        else:
            distance_score = 0.3

        if time_diff_hours <= 2:
            time_score = 1.0
        elif time_diff_hours <= 6:
            time_score = 0.8
        elif time_diff_hours <= 12:
            time_score = 0.6
        else:
            time_score = 0.4

        return (distance_score + time_score) / 2


def validate_report_ml(
    latitude: float,
    longitude: float,
    reported_at: Optional[datetime] = None,
    description: Optional[str] = None,
    photo_data: Optional[bytes] = None,
    **kwargs
) -> ValidationPrediction:
    """
    Convenience function for ML report validation.

    Args:
        latitude: Report latitude
        longitude: Report longitude
        reported_at: Report timestamp
        description: Text description
        photo_data: Photo bytes
        **kwargs: Additional validation data

    Returns:
        ValidationPrediction
    """
    validator = MLReportValidator()
    return validator.validate(
        latitude=latitude,
        longitude=longitude,
        reported_at=reported_at or datetime.utcnow(),
        description=description,
        photo_data=photo_data,
        **kwargs
    )
