"""
Smoke detection in satellite imagery using ML
Detects smoke plumes to identify potential fires
"""

import logging
import os
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
import math

logger = logging.getLogger(__name__)


class SmokeIntensity(Enum):
    """Smoke intensity levels."""
    NONE = "none"
    LIGHT = "light"
    MODERATE = "moderate"
    HEAVY = "heavy"
    EXTREME = "extreme"


@dataclass
class SmokeDetectionResult:
    """Result of smoke detection."""
    detected: bool
    confidence: float
    intensity: SmokeIntensity

    # Detection details
    smoke_coverage_percent: float = 0.0
    plume_direction: Optional[float] = None  # degrees
    plume_length_km: Optional[float] = None

    # Source estimation
    estimated_source_lat: Optional[float] = None
    estimated_source_lon: Optional[float] = None

    # Regions detected
    smoke_regions: List[Dict[str, float]] = field(default_factory=list)

    # Processing info
    processing_time_ms: float = 0.0
    model_version: str = "1.0"
    image_source: str = "unknown"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "detected": self.detected,
            "confidence": self.confidence,
            "intensity": self.intensity.value,
            "smoke_coverage_percent": self.smoke_coverage_percent,
            "plume_direction": self.plume_direction,
            "plume_length_km": self.plume_length_km,
            "estimated_source": {
                "lat": self.estimated_source_lat,
                "lon": self.estimated_source_lon
            } if self.estimated_source_lat else None,
            "smoke_regions": self.smoke_regions,
            "model_version": self.model_version
        }


class SmokeDetector:
    """
    Smoke detection in satellite imagery.

    Uses computer vision and ML to detect smoke plumes.
    """

    # Smoke color characteristics (in various color spaces)
    SMOKE_GRAY_RANGE = (120, 220)
    SMOKE_SAT_MAX = 40

    def __init__(
        self,
        model_path: Optional[str] = None,
        confidence_threshold: float = 0.5,
        use_gpu: bool = False
    ):
        """
        Initialize smoke detector.

        Args:
            model_path: Path to trained model
            confidence_threshold: Minimum detection confidence
            use_gpu: Use GPU acceleration
        """
        self.model_path = model_path
        self.confidence_threshold = confidence_threshold
        self.use_gpu = use_gpu

        self._model = None
        self._cv2 = None
        self._np = None

        self._initialize()

    def _initialize(self) -> None:
        """Initialize dependencies."""
        try:
            import cv2
            import numpy as np
            self._cv2 = cv2
            self._np = np
            logger.info("SmokeDetector initialized with OpenCV")
        except ImportError:
            logger.warning("OpenCV not available for smoke detection")

        # Load ML model if available
        if self.model_path and os.path.exists(self.model_path):
            self._load_model()

    def _load_model(self) -> None:
        """Load trained smoke detection model."""
        try:
            # Try TensorFlow/Keras
            import tensorflow as tf
            self._model = tf.keras.models.load_model(self.model_path)
            logger.info(f"Loaded smoke detection model: {self.model_path}")
        except Exception as e:
            logger.warning(f"Could not load ML model: {e}")

    @property
    def is_ready(self) -> bool:
        """Check if detector is ready."""
        return self._cv2 is not None

    def detect(
        self,
        image_data: bytes,
        image_bounds: Optional[Dict[str, float]] = None
    ) -> SmokeDetectionResult:
        """
        Detect smoke in satellite image.

        Args:
            image_data: Image bytes
            image_bounds: Geographic bounds {west, south, east, north}

        Returns:
            SmokeDetectionResult
        """
        import time
        start_time = time.time()

        result = SmokeDetectionResult(
            detected=False,
            confidence=0.0,
            intensity=SmokeIntensity.NONE
        )

        if not self.is_ready:
            result.model_version = "fallback"
            return result

        try:
            # Load image
            image = self._load_image(image_data)
            if image is None:
                return result

            # Detect smoke using color analysis
            smoke_mask, confidence = self._detect_smoke_colors(image)

            # Calculate coverage
            total_pixels = image.shape[0] * image.shape[1]
            smoke_pixels = self._np.sum(smoke_mask > 0)
            coverage = (smoke_pixels / total_pixels) * 100

            result.smoke_coverage_percent = round(coverage, 2)
            result.confidence = confidence

            # Determine if smoke detected
            result.detected = (
                confidence >= self.confidence_threshold and
                coverage >= 1.0  # At least 1% coverage
            )

            # Determine intensity
            result.intensity = self._determine_intensity(coverage, confidence)

            if result.detected:
                # Analyze plume
                plume_info = self._analyze_plume(smoke_mask, image_bounds)
                result.plume_direction = plume_info.get("direction")
                result.plume_length_km = plume_info.get("length_km")
                result.estimated_source_lat = plume_info.get("source_lat")
                result.estimated_source_lon = plume_info.get("source_lon")

                # Get smoke regions
                result.smoke_regions = self._get_regions(smoke_mask)

            # Use ML model if available
            if self._model is not None:
                ml_result = self._ml_detect(image)
                # Combine with color-based detection
                result.confidence = (result.confidence + ml_result) / 2

        except Exception as e:
            logger.error(f"Smoke detection failed: {e}")

        result.processing_time_ms = (time.time() - start_time) * 1000
        return result

    def detect_from_sentinel(
        self,
        bands: Dict[str, Any],
        bounds: Dict[str, float]
    ) -> SmokeDetectionResult:
        """
        Detect smoke from Sentinel-2 bands.

        Args:
            bands: Dictionary of band arrays (B2, B3, B4, B8, B11, B12)
            bounds: Geographic bounds

        Returns:
            SmokeDetectionResult
        """
        result = SmokeDetectionResult(
            detected=False,
            confidence=0.0,
            intensity=SmokeIntensity.NONE,
            image_source="sentinel-2"
        )

        if not self._np:
            return result

        try:
            # Calculate smoke indices
            # Aerosol Optical Depth approximation using visible bands
            if "B2" in bands and "B4" in bands:
                blue = bands["B2"].astype(float)
                red = bands["B4"].astype(float)

                # Simple smoke index
                smoke_index = (blue - red) / (blue + red + 0.0001)

                # Threshold for smoke
                smoke_mask = smoke_index > 0.1

                coverage = (self._np.sum(smoke_mask) / smoke_mask.size) * 100
                result.smoke_coverage_percent = round(coverage, 2)

                # Confidence based on coverage and index values
                if coverage > 5:
                    result.detected = True
                    result.confidence = min(0.9, 0.5 + coverage / 50)
                    result.intensity = self._determine_intensity(coverage, result.confidence)

        except Exception as e:
            logger.error(f"Sentinel smoke detection failed: {e}")

        return result

    def _load_image(self, image_data: bytes):
        """Load image from bytes."""
        try:
            nparr = self._np.frombuffer(image_data, self._np.uint8)
            image = self._cv2.imdecode(nparr, self._cv2.IMREAD_COLOR)
            return image
        except Exception:
            return None

    def _detect_smoke_colors(self, image) -> Tuple[Any, float]:
        """Detect smoke using color analysis."""
        # Convert to HSV
        hsv = self._cv2.cvtColor(image, self._cv2.COLOR_BGR2HSV)

        # Smoke characteristics: low saturation, medium-high value
        lower = self._np.array([0, 0, self.SMOKE_GRAY_RANGE[0]])
        upper = self._np.array([180, self.SMOKE_SAT_MAX, self.SMOKE_GRAY_RANGE[1]])

        smoke_mask = self._cv2.inRange(hsv, lower, upper)

        # Apply morphological operations
        kernel = self._np.ones((5, 5), self._np.uint8)
        smoke_mask = self._cv2.morphologyEx(smoke_mask, self._cv2.MORPH_CLOSE, kernel)
        smoke_mask = self._cv2.morphologyEx(smoke_mask, self._cv2.MORPH_OPEN, kernel)

        # Calculate confidence
        coverage = self._np.sum(smoke_mask > 0) / smoke_mask.size

        # Higher coverage with consistent gray = higher confidence
        if coverage < 0.01:
            confidence = 0.1
        elif coverage < 0.05:
            confidence = 0.3 + coverage * 5
        elif coverage < 0.3:
            confidence = 0.5 + coverage
        else:
            confidence = 0.7  # Very high coverage might be clouds

        return smoke_mask, min(1.0, confidence)

    def _determine_intensity(
        self,
        coverage: float,
        confidence: float
    ) -> SmokeIntensity:
        """Determine smoke intensity."""
        if coverage < 1 or confidence < 0.3:
            return SmokeIntensity.NONE
        elif coverage < 5:
            return SmokeIntensity.LIGHT
        elif coverage < 15:
            return SmokeIntensity.MODERATE
        elif coverage < 30:
            return SmokeIntensity.HEAVY
        else:
            return SmokeIntensity.EXTREME

    def _analyze_plume(
        self,
        smoke_mask,
        bounds: Optional[Dict[str, float]]
    ) -> Dict[str, Any]:
        """Analyze smoke plume characteristics."""
        result = {}

        # Find contours
        contours, _ = self._cv2.findContours(
            smoke_mask, self._cv2.RETR_EXTERNAL, self._cv2.CHAIN_APPROX_SIMPLE
        )

        if not contours:
            return result

        # Get largest contour (main plume)
        largest = max(contours, key=self._cv2.contourArea)

        # Fit ellipse to get direction
        if len(largest) >= 5:
            ellipse = self._cv2.fitEllipse(largest)
            center, axes, angle = ellipse
            result["direction"] = angle

            # Estimate plume length
            major_axis = max(axes)
            h, w = smoke_mask.shape

            if bounds:
                # Convert to km
                lat_range = bounds["north"] - bounds["south"]
                km_per_pixel = (lat_range * 111) / h
                result["length_km"] = round(major_axis * km_per_pixel, 1)

                # Estimate source (upwind end of plume)
                # Simplified: use centroid
                M = self._cv2.moments(largest)
                if M["m00"] > 0:
                    cx = int(M["m10"] / M["m00"])
                    cy = int(M["m01"] / M["m00"])

                    # Convert to geographic coordinates
                    lon_range = bounds["east"] - bounds["west"]
                    result["source_lon"] = bounds["west"] + (cx / w) * lon_range
                    result["source_lat"] = bounds["north"] - (cy / h) * lat_range

        return result

    def _get_regions(self, mask) -> List[Dict[str, float]]:
        """Get bounding boxes of smoke regions."""
        contours, _ = self._cv2.findContours(
            mask, self._cv2.RETR_EXTERNAL, self._cv2.CHAIN_APPROX_SIMPLE
        )

        regions = []
        h, w = mask.shape

        for contour in sorted(contours, key=self._cv2.contourArea, reverse=True)[:5]:
            x, y, bw, bh = self._cv2.boundingRect(contour)
            area = self._cv2.contourArea(contour)

            if area < 100:
                continue

            regions.append({
                "x": x / w,
                "y": y / h,
                "width": bw / w,
                "height": bh / h,
                "area_percent": (area / (h * w)) * 100
            })

        return regions

    def _ml_detect(self, image) -> float:
        """Use ML model for detection."""
        try:
            # Preprocess image
            resized = self._cv2.resize(image, (224, 224))
            normalized = resized / 255.0
            batch = self._np.expand_dims(normalized, axis=0)

            # Predict
            prediction = self._model.predict(batch, verbose=0)
            return float(prediction[0][0])

        except Exception as e:
            logger.error(f"ML detection failed: {e}")
            return 0.5


def detect_smoke(
    image_data: bytes,
    confidence_threshold: float = 0.5
) -> SmokeDetectionResult:
    """
    Convenience function to detect smoke in image.

    Args:
        image_data: Image bytes
        confidence_threshold: Minimum confidence

    Returns:
        SmokeDetectionResult
    """
    detector = SmokeDetector(confidence_threshold=confidence_threshold)
    return detector.detect(image_data)
