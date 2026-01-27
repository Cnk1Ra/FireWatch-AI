"""
Report validation for crowdsourced fire reports
Cross-validates with satellite data and ML analysis
"""

import logging
import math
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class ValidationStatus(Enum):
    """Validation result status."""
    CONFIRMED = "confirmed"
    LIKELY_VALID = "likely_valid"
    UNCERTAIN = "uncertain"
    LIKELY_FALSE = "likely_false"
    FALSE_REPORT = "false_report"
    DUPLICATE = "duplicate"


@dataclass
class ValidationResult:
    """Result of report validation."""
    status: ValidationStatus
    confidence: float

    # Validation sources
    satellite_match: bool = False
    ml_validated: bool = False
    duplicate_of: Optional[str] = None

    # Matching satellite data
    matched_hotspot_id: Optional[int] = None
    hotspot_distance_km: Optional[float] = None
    hotspot_time_diff_minutes: Optional[int] = None

    # ML analysis
    photo_analysis_score: Optional[float] = None
    photo_has_fire: bool = False
    photo_has_smoke: bool = False

    # Validation details
    validation_factors: Dict[str, float] = None
    warnings: List[str] = None
    notes: str = ""

    def __post_init__(self):
        if self.validation_factors is None:
            self.validation_factors = {}
        if self.warnings is None:
            self.warnings = []

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "status": self.status.value,
            "confidence": self.confidence,
            "satellite_match": self.satellite_match,
            "ml_validated": self.ml_validated,
            "duplicate_of": self.duplicate_of,
            "matched_hotspot_id": self.matched_hotspot_id,
            "hotspot_distance_km": self.hotspot_distance_km,
            "hotspot_time_diff_minutes": self.hotspot_time_diff_minutes,
            "photo_analysis_score": self.photo_analysis_score,
            "photo_has_fire": self.photo_has_fire,
            "photo_has_smoke": self.photo_has_smoke,
            "validation_factors": self.validation_factors,
            "warnings": self.warnings,
            "notes": self.notes
        }


class ReportValidator:
    """
    Validates fire reports using multiple data sources.

    Cross-references with:
    - NASA FIRMS satellite hotspots
    - ML photo analysis
    - Other user reports (duplicate detection)
    - Weather conditions
    """

    # Validation thresholds
    MAX_HOTSPOT_DISTANCE_KM = 5.0
    MAX_TIME_DIFFERENCE_HOURS = 6
    MIN_CONFIDENCE_THRESHOLD = 0.5

    # Validation weights
    WEIGHT_SATELLITE = 0.4
    WEIGHT_PHOTO = 0.3
    WEIGHT_WEATHER = 0.15
    WEIGHT_LOCATION = 0.15

    def __init__(
        self,
        hotspot_client=None,
        weather_client=None,
        photo_analyzer=None
    ):
        """
        Initialize validator.

        Args:
            hotspot_client: Client for satellite hotspot data
            weather_client: Client for weather data
            photo_analyzer: Photo analysis service
        """
        self.hotspot_client = hotspot_client
        self.weather_client = weather_client
        self.photo_analyzer = photo_analyzer

        logger.info("ReportValidator initialized")

    def validate(
        self,
        latitude: float,
        longitude: float,
        reported_at: datetime,
        photo_data: Optional[bytes] = None,
        existing_reports: Optional[List[Dict]] = None,
        weather_data: Optional[Dict] = None
    ) -> ValidationResult:
        """
        Validate a fire report.

        Args:
            latitude: Report latitude
            longitude: Report longitude
            reported_at: Report timestamp
            photo_data: Optional photo bytes
            existing_reports: Other reports for duplicate check
            weather_data: Current weather conditions

        Returns:
            ValidationResult with validation details
        """
        result = ValidationResult(
            status=ValidationStatus.UNCERTAIN,
            confidence=0.5
        )

        factors = {}
        total_weight = 0

        # 1. Check for duplicates
        if existing_reports:
            duplicate = self._check_duplicates(
                latitude, longitude, reported_at, existing_reports
            )
            if duplicate:
                result.status = ValidationStatus.DUPLICATE
                result.duplicate_of = duplicate
                result.confidence = 0.9
                return result

        # 2. Satellite validation
        satellite_score = self._validate_with_satellite(
            latitude, longitude, reported_at, result
        )
        if satellite_score is not None:
            factors["satellite"] = satellite_score
            total_weight += self.WEIGHT_SATELLITE

        # 3. Photo analysis
        if photo_data:
            photo_score = self._validate_photo(photo_data, result)
            if photo_score is not None:
                factors["photo"] = photo_score
                total_weight += self.WEIGHT_PHOTO

        # 4. Weather conditions
        if weather_data:
            weather_score = self._validate_weather(weather_data)
            factors["weather"] = weather_score
            total_weight += self.WEIGHT_WEATHER

        # 5. Location plausibility
        location_score = self._validate_location(latitude, longitude)
        factors["location"] = location_score
        total_weight += self.WEIGHT_LOCATION

        # Calculate final confidence
        result.validation_factors = factors

        if total_weight > 0:
            weighted_sum = sum(
                score * self._get_weight(factor)
                for factor, score in factors.items()
            )
            result.confidence = weighted_sum / total_weight

        # Determine final status
        result.status = self._determine_status(result)

        logger.info(
            f"Validation complete: {result.status.value} "
            f"(confidence={result.confidence:.2f})"
        )

        return result

    def _check_duplicates(
        self,
        latitude: float,
        longitude: float,
        reported_at: datetime,
        existing_reports: List[Dict]
    ) -> Optional[str]:
        """Check if report is a duplicate."""
        for report in existing_reports:
            # Check time (within 1 hour)
            report_time = report.get("reported_at")
            if isinstance(report_time, str):
                report_time = datetime.fromisoformat(report_time)

            time_diff = abs((reported_at - report_time).total_seconds())
            if time_diff > 3600:  # 1 hour
                continue

            # Check distance (within 500m)
            distance = self._haversine_distance(
                latitude, longitude,
                report.get("latitude", 0),
                report.get("longitude", 0)
            )

            if distance <= 0.5:  # 500 meters
                return report.get("id")

        return None

    def _validate_with_satellite(
        self,
        latitude: float,
        longitude: float,
        reported_at: datetime,
        result: ValidationResult
    ) -> Optional[float]:
        """
        Validate against satellite hotspots.

        Returns confidence score 0-1.
        """
        if not self.hotspot_client:
            # Simulate satellite validation
            return self._simulate_satellite_validation(latitude, longitude)

        try:
            # Fetch nearby hotspots
            hotspots = self.hotspot_client.get_hotspots(
                west=longitude - 0.1,
                south=latitude - 0.1,
                east=longitude + 0.1,
                north=latitude + 0.1,
                days=1
            )

            if not hotspots:
                result.warnings.append("No satellite hotspots in area")
                return 0.3  # No data doesn't mean false

            # Find closest hotspot
            closest = None
            closest_distance = float('inf')

            for hotspot in hotspots:
                distance = self._haversine_distance(
                    latitude, longitude,
                    hotspot.latitude, hotspot.longitude
                )

                if distance < closest_distance:
                    closest_distance = distance
                    closest = hotspot

            if closest and closest_distance <= self.MAX_HOTSPOT_DISTANCE_KM:
                result.satellite_match = True
                result.matched_hotspot_id = getattr(closest, 'id', None)
                result.hotspot_distance_km = round(closest_distance, 2)

                # Time difference
                if hasattr(closest, 'acq_datetime'):
                    time_diff = abs((reported_at - closest.acq_datetime).total_seconds() / 60)
                    result.hotspot_time_diff_minutes = int(time_diff)

                # Score based on distance
                return max(0.5, 1 - (closest_distance / self.MAX_HOTSPOT_DISTANCE_KM))

            return 0.3  # Hotspots exist but not close

        except Exception as e:
            logger.error(f"Satellite validation error: {e}")
            result.warnings.append(f"Satellite check failed: {str(e)}")
            return None

    def _simulate_satellite_validation(
        self,
        latitude: float,
        longitude: float
    ) -> float:
        """Simulate satellite validation for testing."""
        # Brazilian fire-prone areas get higher scores
        if -20 <= latitude <= -5 and -60 <= longitude <= -45:
            return 0.7  # Amazon/Cerrado region
        elif -25 <= latitude <= -15 and -55 <= longitude <= -50:
            return 0.6  # Pantanal region
        else:
            return 0.4

    def _validate_photo(
        self,
        photo_data: bytes,
        result: ValidationResult
    ) -> Optional[float]:
        """Validate using photo analysis."""
        if not self.photo_analyzer:
            # Use local analyzer
            from .photo_analyzer import PhotoAnalyzer
            analyzer = PhotoAnalyzer()
            analysis = analyzer.analyze(photo_data)
        else:
            analysis = self.photo_analyzer.analyze(photo_data)

        result.photo_has_fire = analysis.has_fire
        result.photo_has_smoke = analysis.has_smoke
        result.photo_analysis_score = analysis.confidence

        if analysis.has_fire and analysis.has_smoke:
            result.ml_validated = True
            return analysis.confidence
        elif analysis.has_fire or analysis.has_smoke:
            return analysis.confidence * 0.8
        else:
            return analysis.confidence * 0.3

    def _validate_weather(self, weather_data: Dict) -> float:
        """
        Validate based on weather conditions.

        High temperature + low humidity = more likely fire.
        """
        temp = weather_data.get("temperature", 25)
        humidity = weather_data.get("humidity", 50)
        wind = weather_data.get("wind_speed", 10)
        precipitation = weather_data.get("precipitation", 0)

        score = 0.5

        # Temperature factor
        if temp >= 35:
            score += 0.2
        elif temp >= 30:
            score += 0.1
        elif temp <= 20:
            score -= 0.1

        # Humidity factor (low humidity = higher fire risk)
        if humidity <= 30:
            score += 0.15
        elif humidity <= 50:
            score += 0.05
        elif humidity >= 80:
            score -= 0.15

        # Wind factor
        if wind >= 20:
            score += 0.1

        # Precipitation factor
        if precipitation > 5:
            score -= 0.2

        return max(0, min(1, score))

    def _validate_location(
        self,
        latitude: float,
        longitude: float
    ) -> float:
        """
        Validate location plausibility.

        Checks if location is in fire-prone area.
        """
        # Check if in Brazil
        if not (-34 <= latitude <= 5 and -74 <= longitude <= -34):
            return 0.3  # Outside Brazil

        # Fire-prone biomes (simplified)
        biomes = [
            {"name": "Amazonia", "score": 0.8, "bounds": (-10, -74, 5, -44)},
            {"name": "Cerrado", "score": 0.9, "bounds": (-24, -60, -2, -41)},
            {"name": "Pantanal", "score": 0.85, "bounds": (-22, -59, -15, -54)},
            {"name": "Caatinga", "score": 0.7, "bounds": (-17, -46, -2, -35)},
        ]

        for biome in biomes:
            south, west, north, east = biome["bounds"]
            if south <= latitude <= north and west <= longitude <= east:
                return biome["score"]

        return 0.5  # Default for other areas

    def _get_weight(self, factor: str) -> float:
        """Get weight for validation factor."""
        weights = {
            "satellite": self.WEIGHT_SATELLITE,
            "photo": self.WEIGHT_PHOTO,
            "weather": self.WEIGHT_WEATHER,
            "location": self.WEIGHT_LOCATION
        }
        return weights.get(factor, 0.1)

    def _determine_status(self, result: ValidationResult) -> ValidationStatus:
        """Determine final validation status based on confidence."""
        if result.satellite_match and result.ml_validated:
            return ValidationStatus.CONFIRMED
        elif result.confidence >= 0.8:
            return ValidationStatus.CONFIRMED
        elif result.confidence >= 0.6:
            return ValidationStatus.LIKELY_VALID
        elif result.confidence >= 0.4:
            return ValidationStatus.UNCERTAIN
        elif result.confidence >= 0.2:
            return ValidationStatus.LIKELY_FALSE
        else:
            return ValidationStatus.FALSE_REPORT

    def _haversine_distance(
        self,
        lat1: float, lon1: float,
        lat2: float, lon2: float
    ) -> float:
        """Calculate distance between two points in km."""
        R = 6371  # Earth radius in km

        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        delta_lat = math.radians(lat2 - lat1)
        delta_lon = math.radians(lon2 - lon1)

        a = (math.sin(delta_lat / 2) ** 2 +
             math.cos(lat1_rad) * math.cos(lat2_rad) *
             math.sin(delta_lon / 2) ** 2)
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

        return R * c


def validate_report(
    latitude: float,
    longitude: float,
    reported_at: Optional[datetime] = None,
    photo_data: Optional[bytes] = None,
    **kwargs
) -> ValidationResult:
    """
    Convenience function to validate a fire report.

    Args:
        latitude: Report latitude
        longitude: Report longitude
        reported_at: Report timestamp (default: now)
        photo_data: Optional photo bytes
        **kwargs: Additional validation parameters

    Returns:
        ValidationResult
    """
    validator = ReportValidator()
    return validator.validate(
        latitude=latitude,
        longitude=longitude,
        reported_at=reported_at or datetime.utcnow(),
        photo_data=photo_data,
        **kwargs
    )
