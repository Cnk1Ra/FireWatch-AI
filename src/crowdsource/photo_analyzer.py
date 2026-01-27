"""
Photo analyzer for fire detection in user-submitted images
Uses computer vision to validate fire reports
"""

import logging
import os
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass
from enum import Enum
import base64
import io

logger = logging.getLogger(__name__)


class DetectionType(Enum):
    """Type of detection in image."""
    FIRE = "fire"
    SMOKE = "smoke"
    BOTH = "both"
    NONE = "none"
    UNCERTAIN = "uncertain"


@dataclass
class AnalysisResult:
    """Result of photo analysis."""
    has_fire: bool
    has_smoke: bool
    confidence: float
    detection_type: DetectionType

    # Detailed scores
    fire_confidence: float = 0.0
    smoke_confidence: float = 0.0

    # Bounding boxes (if available)
    fire_regions: List[Dict[str, float]] = None
    smoke_regions: List[Dict[str, float]] = None

    # Image quality
    image_quality: str = "good"  # good, poor, blurry, dark
    is_outdoor: bool = True

    # Additional metadata
    processing_time_ms: float = 0.0
    model_version: str = "1.0"
    warnings: List[str] = None

    def __post_init__(self):
        if self.fire_regions is None:
            self.fire_regions = []
        if self.smoke_regions is None:
            self.smoke_regions = []
        if self.warnings is None:
            self.warnings = []

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "has_fire": self.has_fire,
            "has_smoke": self.has_smoke,
            "confidence": self.confidence,
            "detection_type": self.detection_type.value,
            "fire_confidence": self.fire_confidence,
            "smoke_confidence": self.smoke_confidence,
            "fire_regions": self.fire_regions,
            "smoke_regions": self.smoke_regions,
            "image_quality": self.image_quality,
            "is_outdoor": self.is_outdoor,
            "model_version": self.model_version,
            "warnings": self.warnings
        }


class PhotoAnalyzer:
    """
    Analyzes photos for fire and smoke detection.

    Uses computer vision models to validate user-submitted fire photos.
    """

    # Color thresholds for fire detection (HSV)
    FIRE_HUE_RANGE = (0, 30)  # Red-orange-yellow
    FIRE_SAT_MIN = 100
    FIRE_VAL_MIN = 150

    # Smoke color thresholds (HSV)
    SMOKE_SAT_MAX = 50
    SMOKE_VAL_RANGE = (100, 220)

    def __init__(
        self,
        model_path: Optional[str] = None,
        use_gpu: bool = False,
        confidence_threshold: float = 0.5
    ):
        """
        Initialize photo analyzer.

        Args:
            model_path: Path to trained model
            use_gpu: Use GPU for inference
            confidence_threshold: Minimum confidence for detection
        """
        self.model_path = model_path
        self.use_gpu = use_gpu
        self.confidence_threshold = confidence_threshold

        self._model = None
        self._cv2 = None
        self._np = None

        self._initialize_cv()

    def _initialize_cv(self) -> None:
        """Initialize OpenCV and NumPy."""
        try:
            import cv2
            import numpy as np
            self._cv2 = cv2
            self._np = np
            logger.info("OpenCV initialized for photo analysis")
        except ImportError:
            logger.warning("OpenCV not installed. Using fallback analysis.")

    @property
    def is_ready(self) -> bool:
        """Check if analyzer is ready."""
        return self._cv2 is not None

    def analyze(
        self,
        image_data: bytes,
        include_regions: bool = True
    ) -> AnalysisResult:
        """
        Analyze image for fire and smoke.

        Args:
            image_data: Image bytes (JPEG, PNG)
            include_regions: Include detection bounding boxes

        Returns:
            AnalysisResult with detection details
        """
        import time
        start_time = time.time()

        # Default result
        result = AnalysisResult(
            has_fire=False,
            has_smoke=False,
            confidence=0.0,
            detection_type=DetectionType.NONE
        )

        if not self.is_ready:
            # Fallback: assume report is valid
            result.confidence = 0.5
            result.detection_type = DetectionType.UNCERTAIN
            result.warnings.append("CV not available - using fallback")
            return result

        try:
            # Load image
            image = self._load_image(image_data)
            if image is None:
                result.warnings.append("Failed to load image")
                return result

            # Check image quality
            result.image_quality = self._assess_quality(image)

            # Detect fire using color analysis
            fire_mask, fire_conf = self._detect_fire_colors(image)
            result.fire_confidence = fire_conf
            result.has_fire = fire_conf >= self.confidence_threshold

            # Detect smoke
            smoke_mask, smoke_conf = self._detect_smoke(image)
            result.smoke_confidence = smoke_conf
            result.has_smoke = smoke_conf >= self.confidence_threshold

            # Determine detection type
            if result.has_fire and result.has_smoke:
                result.detection_type = DetectionType.BOTH
                result.confidence = max(fire_conf, smoke_conf)
            elif result.has_fire:
                result.detection_type = DetectionType.FIRE
                result.confidence = fire_conf
            elif result.has_smoke:
                result.detection_type = DetectionType.SMOKE
                result.confidence = smoke_conf
            else:
                result.detection_type = DetectionType.NONE
                result.confidence = 1 - max(fire_conf, smoke_conf)

            # Get regions if requested
            if include_regions:
                if result.has_fire:
                    result.fire_regions = self._get_regions(fire_mask)
                if result.has_smoke:
                    result.smoke_regions = self._get_regions(smoke_mask)

            # Check if outdoor
            result.is_outdoor = self._is_outdoor(image)

        except Exception as e:
            logger.error(f"Photo analysis failed: {e}")
            result.warnings.append(f"Analysis error: {str(e)}")

        result.processing_time_ms = (time.time() - start_time) * 1000

        return result

    def _load_image(self, image_data: bytes):
        """Load image from bytes."""
        try:
            nparr = self._np.frombuffer(image_data, self._np.uint8)
            image = self._cv2.imdecode(nparr, self._cv2.IMREAD_COLOR)
            return image
        except Exception as e:
            logger.error(f"Failed to load image: {e}")
            return None

    def _assess_quality(self, image) -> str:
        """Assess image quality."""
        # Convert to grayscale
        gray = self._cv2.cvtColor(image, self._cv2.COLOR_BGR2GRAY)

        # Check brightness
        mean_brightness = self._np.mean(gray)
        if mean_brightness < 30:
            return "dark"

        # Check blur (Laplacian variance)
        laplacian_var = self._cv2.Laplacian(gray, self._cv2.CV_64F).var()
        if laplacian_var < 100:
            return "blurry"

        # Check if too small
        h, w = image.shape[:2]
        if h < 200 or w < 200:
            return "poor"

        return "good"

    def _detect_fire_colors(self, image) -> Tuple[Any, float]:
        """
        Detect fire using color analysis.

        Returns:
            Tuple of (mask, confidence)
        """
        # Convert to HSV
        hsv = self._cv2.cvtColor(image, self._cv2.COLOR_BGR2HSV)

        # Fire color range (red-orange-yellow)
        lower1 = self._np.array([0, self.FIRE_SAT_MIN, self.FIRE_VAL_MIN])
        upper1 = self._np.array([15, 255, 255])

        lower2 = self._np.array([15, self.FIRE_SAT_MIN, self.FIRE_VAL_MIN])
        upper2 = self._np.array([35, 255, 255])

        # Create masks
        mask1 = self._cv2.inRange(hsv, lower1, upper1)
        mask2 = self._cv2.inRange(hsv, lower2, upper2)
        fire_mask = self._cv2.bitwise_or(mask1, mask2)

        # Apply morphological operations
        kernel = self._np.ones((5, 5), self._np.uint8)
        fire_mask = self._cv2.morphologyEx(fire_mask, self._cv2.MORPH_CLOSE, kernel)
        fire_mask = self._cv2.morphologyEx(fire_mask, self._cv2.MORPH_OPEN, kernel)

        # Calculate confidence based on fire pixel ratio
        total_pixels = image.shape[0] * image.shape[1]
        fire_pixels = self._np.sum(fire_mask > 0)
        fire_ratio = fire_pixels / total_pixels

        # Confidence based on fire area (optimal range: 1-30% of image)
        if fire_ratio < 0.005:
            confidence = fire_ratio * 20  # Small fires: low confidence
        elif fire_ratio < 0.3:
            confidence = 0.5 + fire_ratio  # Normal range: medium-high
        else:
            confidence = max(0.3, 1 - fire_ratio)  # Too much: might be false positive

        return fire_mask, min(1.0, confidence)

    def _detect_smoke(self, image) -> Tuple[Any, float]:
        """
        Detect smoke using color and texture analysis.

        Returns:
            Tuple of (mask, confidence)
        """
        # Convert to HSV
        hsv = self._cv2.cvtColor(image, self._cv2.COLOR_BGR2HSV)

        # Smoke color range (gray/white, low saturation)
        lower = self._np.array([0, 0, self.SMOKE_VAL_RANGE[0]])
        upper = self._np.array([180, self.SMOKE_SAT_MAX, self.SMOKE_VAL_RANGE[1]])

        smoke_mask = self._cv2.inRange(hsv, lower, upper)

        # Calculate confidence
        total_pixels = image.shape[0] * image.shape[1]
        smoke_pixels = self._np.sum(smoke_mask > 0)
        smoke_ratio = smoke_pixels / total_pixels

        # Smoke confidence (large gray areas might be smoke)
        if smoke_ratio < 0.1:
            confidence = smoke_ratio * 3
        elif smoke_ratio < 0.5:
            confidence = 0.3 + smoke_ratio * 0.6
        else:
            confidence = max(0.2, 0.9 - smoke_ratio)  # Too much gray: might be sky

        return smoke_mask, min(1.0, confidence)

    def _get_regions(self, mask) -> List[Dict[str, float]]:
        """Get bounding boxes from detection mask."""
        contours, _ = self._cv2.findContours(
            mask, self._cv2.RETR_EXTERNAL, self._cv2.CHAIN_APPROX_SIMPLE
        )

        regions = []
        h, w = mask.shape

        for contour in contours:
            area = self._cv2.contourArea(contour)
            if area < 100:  # Skip tiny regions
                continue

            x, y, bw, bh = self._cv2.boundingRect(contour)

            regions.append({
                "x": x / w,
                "y": y / h,
                "width": bw / w,
                "height": bh / h,
                "area": area / (h * w)
            })

        return regions[:10]  # Return top 10 regions

    def _is_outdoor(self, image) -> bool:
        """Check if image appears to be outdoors."""
        # Check for sky-like colors in upper portion
        h, w = image.shape[:2]
        upper_region = image[:h//3, :, :]

        hsv = self._cv2.cvtColor(upper_region, self._cv2.COLOR_BGR2HSV)

        # Sky blue range
        lower_sky = self._np.array([100, 50, 100])
        upper_sky = self._np.array([130, 255, 255])

        sky_mask = self._cv2.inRange(hsv, lower_sky, upper_sky)
        sky_ratio = self._np.sum(sky_mask > 0) / (upper_region.shape[0] * upper_region.shape[1])

        return sky_ratio > 0.1  # More than 10% sky-like pixels


def analyze_fire_photo(
    image_data: bytes,
    confidence_threshold: float = 0.5
) -> AnalysisResult:
    """
    Convenience function to analyze a fire photo.

    Args:
        image_data: Image bytes
        confidence_threshold: Minimum confidence

    Returns:
        AnalysisResult
    """
    analyzer = PhotoAnalyzer(confidence_threshold=confidence_threshold)
    return analyzer.analyze(image_data)
