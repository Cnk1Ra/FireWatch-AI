"""
FireWatch AI - Crowdsource Module
Handles citizen fire reports and validation.
"""

from src.crowdsource.report_handler import (
    ReportHandler,
    FireReport,
    ReportStatus,
    create_report,
)
from src.crowdsource.photo_analyzer import (
    PhotoAnalyzer,
    AnalysisResult,
    analyze_fire_photo,
)
from src.crowdsource.validation import (
    ReportValidator,
    ValidationResult,
    validate_report,
)

__all__ = [
    # Report Handler
    "ReportHandler",
    "FireReport",
    "ReportStatus",
    "create_report",
    # Photo Analyzer
    "PhotoAnalyzer",
    "AnalysisResult",
    "analyze_fire_photo",
    # Validation
    "ReportValidator",
    "ValidationResult",
    "validate_report",
]
