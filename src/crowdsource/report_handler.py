"""
Fire report handler for crowdsourced data
Receives and processes fire reports from citizens
"""

import logging
import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class ReportStatus(Enum):
    """Status of a fire report."""
    PENDING = "pending"
    UNDER_REVIEW = "under_review"
    VALIDATED = "validated"
    REJECTED = "rejected"
    DUPLICATE = "duplicate"
    FORWARDED = "forwarded"


class ReportPriority(Enum):
    """Priority level of a report."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class FireReport:
    """
    Fire report submitted by a citizen.

    Contains location, description, and optional photo.
    """
    id: str
    latitude: float
    longitude: float

    # Report details
    description: Optional[str] = None
    photo_url: Optional[str] = None
    photo_data: Optional[bytes] = None

    # Fire characteristics
    has_flames: bool = True
    has_smoke: bool = True
    estimated_size: str = "medium"  # small, medium, large, very_large
    fire_type: str = "vegetation"  # vegetation, structure, vehicle, other

    # Reporter information
    reporter_name: Optional[str] = None
    reporter_phone: Optional[str] = None
    reporter_email: Optional[str] = None
    reporter_anonymous: bool = True

    # Location details
    address: Optional[str] = None
    state: Optional[str] = None
    city: Optional[str] = None
    reference_point: Optional[str] = None

    # Status and validation
    status: ReportStatus = ReportStatus.PENDING
    priority: ReportPriority = ReportPriority.MEDIUM
    ml_confidence: Optional[float] = None
    validated_by_satellite: bool = False
    matched_hotspot_id: Optional[int] = None

    # Timestamps
    reported_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None
    validated_at: Optional[datetime] = None

    # Metadata
    device_info: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "description": self.description,
            "photo_url": self.photo_url,
            "has_flames": self.has_flames,
            "has_smoke": self.has_smoke,
            "estimated_size": self.estimated_size,
            "fire_type": self.fire_type,
            "reporter_name": self.reporter_name if not self.reporter_anonymous else None,
            "address": self.address,
            "state": self.state,
            "city": self.city,
            "status": self.status.value,
            "priority": self.priority.value,
            "ml_confidence": self.ml_confidence,
            "validated_by_satellite": self.validated_by_satellite,
            "matched_hotspot_id": self.matched_hotspot_id,
            "reported_at": self.reported_at.isoformat() if self.reported_at else None
        }


class ReportHandler:
    """
    Handles fire reports from citizens.

    Receives, validates, and processes crowdsourced fire data.
    """

    def __init__(
        self,
        storage_backend: Optional[Any] = None,
        enable_photo_analysis: bool = True,
        enable_satellite_validation: bool = True
    ):
        """
        Initialize report handler.

        Args:
            storage_backend: Backend for storing reports (database, file, etc.)
            enable_photo_analysis: Enable ML photo analysis
            enable_satellite_validation: Enable satellite cross-validation
        """
        self.storage = storage_backend
        self.enable_photo_analysis = enable_photo_analysis
        self.enable_satellite_validation = enable_satellite_validation

        self._reports: Dict[str, FireReport] = {}
        self._pending_count = 0

        logger.info("ReportHandler initialized")

    def create_report(
        self,
        latitude: float,
        longitude: float,
        description: Optional[str] = None,
        photo_data: Optional[bytes] = None,
        reporter_info: Optional[Dict[str, str]] = None,
        **kwargs
    ) -> FireReport:
        """
        Create a new fire report.

        Args:
            latitude: Report latitude
            longitude: Report longitude
            description: Text description
            photo_data: Photo bytes
            reporter_info: Reporter contact info
            **kwargs: Additional report fields

        Returns:
            Created FireReport
        """
        report_id = str(uuid.uuid4())[:12].upper()

        report = FireReport(
            id=report_id,
            latitude=latitude,
            longitude=longitude,
            description=description,
            photo_data=photo_data,
            **kwargs
        )

        # Add reporter info
        if reporter_info:
            report.reporter_name = reporter_info.get("name")
            report.reporter_phone = reporter_info.get("phone")
            report.reporter_email = reporter_info.get("email")
            report.reporter_anonymous = reporter_info.get("anonymous", True)

        # Determine initial priority
        report.priority = self._determine_priority(report)

        # Store report
        self._reports[report_id] = report
        self._pending_count += 1

        logger.info(f"New report created: {report_id} at ({latitude}, {longitude})")

        return report

    def get_report(self, report_id: str) -> Optional[FireReport]:
        """Get report by ID."""
        return self._reports.get(report_id)

    def get_pending_reports(self) -> List[FireReport]:
        """Get all pending reports."""
        return [
            r for r in self._reports.values()
            if r.status == ReportStatus.PENDING
        ]

    def get_reports_in_area(
        self,
        west: float,
        south: float,
        east: float,
        north: float
    ) -> List[FireReport]:
        """
        Get reports within a geographic area.

        Args:
            west, south, east, north: Bounding box

        Returns:
            List of reports in area
        """
        return [
            r for r in self._reports.values()
            if west <= r.longitude <= east and south <= r.latitude <= north
        ]

    def update_status(
        self,
        report_id: str,
        new_status: ReportStatus,
        validated_by: Optional[str] = None,
        notes: Optional[str] = None
    ) -> Optional[FireReport]:
        """
        Update report status.

        Args:
            report_id: Report ID
            new_status: New status
            validated_by: Who validated (system or user)
            notes: Validation notes

        Returns:
            Updated report or None
        """
        report = self._reports.get(report_id)
        if not report:
            return None

        old_status = report.status
        report.status = new_status
        report.updated_at = datetime.utcnow()

        if new_status in [ReportStatus.VALIDATED, ReportStatus.REJECTED]:
            report.validated_at = datetime.utcnow()
            if validated_by:
                report.metadata["validated_by"] = validated_by

        if notes:
            report.metadata["validation_notes"] = notes

        if old_status == ReportStatus.PENDING:
            self._pending_count -= 1

        logger.info(f"Report {report_id} status: {old_status.value} -> {new_status.value}")

        return report

    def link_to_hotspot(
        self,
        report_id: str,
        hotspot_id: int
    ) -> Optional[FireReport]:
        """
        Link report to satellite-detected hotspot.

        Args:
            report_id: Report ID
            hotspot_id: Satellite hotspot ID

        Returns:
            Updated report
        """
        report = self._reports.get(report_id)
        if not report:
            return None

        report.matched_hotspot_id = hotspot_id
        report.validated_by_satellite = True
        report.updated_at = datetime.utcnow()

        if report.status == ReportStatus.PENDING:
            report.status = ReportStatus.VALIDATED
            report.validated_at = datetime.utcnow()
            self._pending_count -= 1

        logger.info(f"Report {report_id} linked to hotspot {hotspot_id}")

        return report

    def set_ml_confidence(
        self,
        report_id: str,
        confidence: float
    ) -> Optional[FireReport]:
        """
        Set ML analysis confidence score.

        Args:
            report_id: Report ID
            confidence: Confidence score (0-1)

        Returns:
            Updated report
        """
        report = self._reports.get(report_id)
        if not report:
            return None

        report.ml_confidence = confidence
        report.updated_at = datetime.utcnow()

        # Auto-update priority based on confidence
        if confidence >= 0.9:
            report.priority = ReportPriority.CRITICAL
        elif confidence >= 0.7:
            report.priority = ReportPriority.HIGH
        elif confidence >= 0.5:
            report.priority = ReportPriority.MEDIUM
        else:
            report.priority = ReportPriority.LOW

        return report

    def find_duplicates(
        self,
        latitude: float,
        longitude: float,
        time_window_minutes: int = 60,
        distance_km: float = 1.0
    ) -> List[FireReport]:
        """
        Find potential duplicate reports.

        Args:
            latitude: Location latitude
            longitude: Location longitude
            time_window_minutes: Time window to check
            distance_km: Distance threshold

        Returns:
            List of potential duplicates
        """
        import math
        from datetime import timedelta

        now = datetime.utcnow()
        time_threshold = now - timedelta(minutes=time_window_minutes)

        duplicates = []

        for report in self._reports.values():
            # Skip old reports
            if report.reported_at < time_threshold:
                continue

            # Calculate distance
            dlat = report.latitude - latitude
            dlon = report.longitude - longitude
            distance = math.sqrt(dlat**2 + dlon**2) * 111  # Approximate km

            if distance <= distance_km:
                duplicates.append(report)

        return duplicates

    def get_statistics(self) -> Dict[str, Any]:
        """Get report statistics."""
        total = len(self._reports)

        by_status = {}
        by_priority = {}
        validated_by_satellite = 0
        with_photo = 0

        for report in self._reports.values():
            status = report.status.value
            by_status[status] = by_status.get(status, 0) + 1

            priority = report.priority.value
            by_priority[priority] = by_priority.get(priority, 0) + 1

            if report.validated_by_satellite:
                validated_by_satellite += 1

            if report.photo_url or report.photo_data:
                with_photo += 1

        return {
            "total_reports": total,
            "pending_count": self._pending_count,
            "by_status": by_status,
            "by_priority": by_priority,
            "validated_by_satellite": validated_by_satellite,
            "with_photo": with_photo,
            "validation_rate": validated_by_satellite / total if total > 0 else 0
        }

    def _determine_priority(self, report: FireReport) -> ReportPriority:
        """Determine initial priority based on report content."""
        # Large fires are critical
        if report.estimated_size == "very_large":
            return ReportPriority.CRITICAL

        # Fires with flames are higher priority
        if report.has_flames and report.estimated_size == "large":
            return ReportPriority.HIGH

        # Structure fires are higher priority
        if report.fire_type == "structure":
            return ReportPriority.HIGH

        # Default based on size
        if report.estimated_size in ["large", "medium"]:
            return ReportPriority.MEDIUM

        return ReportPriority.LOW


def create_report(
    latitude: float,
    longitude: float,
    **kwargs
) -> FireReport:
    """
    Convenience function to create a fire report.

    Args:
        latitude: Location latitude
        longitude: Location longitude
        **kwargs: Additional report fields

    Returns:
        Created FireReport
    """
    handler = ReportHandler()
    return handler.create_report(latitude, longitude, **kwargs)
