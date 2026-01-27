"""
FireWatch AI - Machine Learning Module
Fire detection and prediction using ML models.
"""

from src.ml.smoke_detection import (
    SmokeDetector,
    SmokeDetectionResult,
    detect_smoke,
)
from src.ml.ignition_predictor import (
    IgnitionPredictor,
    IgnitionRisk,
    predict_ignition_risk,
)
from src.ml.report_validator import (
    MLReportValidator,
    ValidationPrediction,
    validate_report_ml,
)

__all__ = [
    # Smoke Detection
    "SmokeDetector",
    "SmokeDetectionResult",
    "detect_smoke",
    # Ignition Prediction
    "IgnitionPredictor",
    "IgnitionRisk",
    "predict_ignition_risk",
    # Report Validation
    "MLReportValidator",
    "ValidationPrediction",
    "validate_report_ml",
]
