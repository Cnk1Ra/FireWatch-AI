"""
SQLAlchemy models for FireWatch AI
Uses GeoAlchemy2 for PostGIS spatial types
"""

from datetime import datetime
from typing import Optional, List
import json

from sqlalchemy import (
    Column, Integer, Float, String, Text, Boolean,
    DateTime, ForeignKey, Index, Enum as SQLEnum
)
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.dialects.postgresql import JSONB
from geoalchemy2 import Geometry
from geoalchemy2.shape import to_shape, from_shape
from shapely.geometry import Point, Polygon

import enum

Base = declarative_base()


class AlertLevel(enum.Enum):
    """Alert severity levels."""
    LOW = "BAIXO"
    MODERATE = "MODERADO"
    HIGH = "ALTO"
    VERY_HIGH = "MUITO ALTO"
    CRITICAL = "CRITICO"


class ReportStatus(enum.Enum):
    """User report validation status."""
    PENDING = "pending"
    VALIDATED = "validated"
    REJECTED = "rejected"
    DUPLICATE = "duplicate"


class Hotspot(Base):
    """
    Fire hotspot detected by satellite.

    Stores individual fire detection points from NASA FIRMS.
    """
    __tablename__ = "hotspots"

    id = Column(Integer, primary_key=True, index=True)

    # Location (PostGIS point)
    location = Column(Geometry("POINT", srid=4326), nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)

    # Fire metrics
    brightness = Column(Float, nullable=False)
    frp = Column(Float, nullable=False)  # Fire Radiative Power (MW)
    confidence = Column(String(20), nullable=False)

    # Acquisition info
    acq_datetime = Column(DateTime, nullable=False, index=True)
    satellite = Column(String(50), nullable=False)
    daynight = Column(String(1), nullable=False)  # D or N

    # Classification
    biome = Column(String(50))
    state = Column(String(50))

    # Cluster reference
    cluster_id = Column(Integer, ForeignKey("fire_clusters.id"), nullable=True)
    cluster = relationship("FireCluster", back_populates="hotspots")

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    source = Column(String(50), default="VIIRS_NOAA20_NRT")

    # Indexes
    __table_args__ = (
        Index("idx_hotspot_location", location, postgresql_using="gist"),
        Index("idx_hotspot_acq_datetime", acq_datetime),
        Index("idx_hotspot_state_biome", state, biome),
    )

    def __repr__(self):
        return f"<Hotspot({self.id}, lat={self.latitude}, lon={self.longitude}, frp={self.frp})>"

    @classmethod
    def from_dict(cls, data: dict) -> "Hotspot":
        """Create Hotspot from dictionary."""
        point = Point(data["longitude"], data["latitude"])
        return cls(
            location=from_shape(point, srid=4326),
            latitude=data["latitude"],
            longitude=data["longitude"],
            brightness=data.get("brightness", 0),
            frp=data.get("frp", 0),
            confidence=data.get("confidence", "nominal"),
            acq_datetime=datetime.fromisoformat(data.get("acq_datetime", datetime.utcnow().isoformat())),
            satellite=data.get("satellite", "NOAA-20"),
            daynight=data.get("daynight", "D"),
            biome=data.get("biome"),
            state=data.get("state")
        )

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "brightness": self.brightness,
            "frp": self.frp,
            "confidence": self.confidence,
            "acq_datetime": self.acq_datetime.isoformat() if self.acq_datetime else None,
            "satellite": self.satellite,
            "daynight": self.daynight,
            "biome": self.biome,
            "state": self.state,
            "cluster_id": self.cluster_id
        }


class FireCluster(Base):
    """
    Cluster of related hotspots forming an active fire.

    Groups nearby hotspots into fire events.
    """
    __tablename__ = "fire_clusters"

    id = Column(Integer, primary_key=True, index=True)

    # Center location (PostGIS point)
    center = Column(Geometry("POINT", srid=4326), nullable=False)
    center_lat = Column(Float, nullable=False)
    center_lon = Column(Float, nullable=False)

    # Cluster metrics
    hotspot_count = Column(Integer, default=0)
    total_frp = Column(Float, default=0)
    max_frp = Column(Float, default=0)
    avg_frp = Column(Float, default=0)
    estimated_area_ha = Column(Float, default=0)

    # Perimeter (PostGIS polygon)
    perimeter = Column(Geometry("POLYGON", srid=4326), nullable=True)

    # Classification
    biome = Column(String(50))
    state = Column(String(50))

    # Timeline
    first_detected = Column(DateTime, nullable=False)
    last_updated = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)

    # Risk assessment
    risk_level = Column(SQLEnum(AlertLevel), default=AlertLevel.MODERATE)
    spread_rate = Column(Float)  # m/min
    spread_direction = Column(Float)  # degrees

    # Relationships
    hotspots = relationship("Hotspot", back_populates="cluster")
    alerts = relationship("Alert", back_populates="cluster")

    # Metadata
    metadata = Column(JSONB, default={})

    __table_args__ = (
        Index("idx_cluster_center", center, postgresql_using="gist"),
        Index("idx_cluster_active", is_active),
        Index("idx_cluster_first_detected", first_detected),
    )

    def __repr__(self):
        return f"<FireCluster({self.id}, count={self.hotspot_count}, area={self.estimated_area_ha}ha)>"

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "center_lat": self.center_lat,
            "center_lon": self.center_lon,
            "count": self.hotspot_count,
            "total_frp": self.total_frp,
            "max_frp": self.max_frp,
            "avg_frp": self.avg_frp,
            "estimated_area_ha": self.estimated_area_ha,
            "biome": self.biome,
            "state": self.state,
            "first_detected": self.first_detected.isoformat() if self.first_detected else None,
            "last_updated": self.last_updated.isoformat() if self.last_updated else None,
            "is_active": self.is_active,
            "risk_level": self.risk_level.value if self.risk_level else None,
            "spread_rate": self.spread_rate,
            "spread_direction": self.spread_direction
        }


class WeatherRecord(Base):
    """
    Weather data record for a location.

    Stores historical weather data for analysis.
    """
    __tablename__ = "weather_records"

    id = Column(Integer, primary_key=True, index=True)

    # Location
    location = Column(Geometry("POINT", srid=4326), nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)

    # Weather data
    temperature = Column(Float, nullable=False)
    humidity = Column(Float, nullable=False)
    wind_speed = Column(Float, nullable=False)
    wind_direction = Column(Float, nullable=False)
    precipitation = Column(Float, default=0)

    # Timestamps
    recorded_at = Column(DateTime, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Source
    source = Column(String(50), default="open-meteo")

    __table_args__ = (
        Index("idx_weather_location", location, postgresql_using="gist"),
        Index("idx_weather_recorded_at", recorded_at),
    )

    def __repr__(self):
        return f"<WeatherRecord({self.id}, temp={self.temperature}, humid={self.humidity})>"


class Alert(Base):
    """
    Fire alert notification.

    Stores alerts generated by the system.
    """
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, index=True)

    # Alert details
    level = Column(SQLEnum(AlertLevel), nullable=False)
    title = Column(String(200), nullable=False)
    message = Column(Text, nullable=False)

    # Location
    location = Column(Geometry("POINT", srid=4326), nullable=True)
    latitude = Column(Float)
    longitude = Column(Float)
    state = Column(String(50))
    biome = Column(String(50))

    # Related cluster
    cluster_id = Column(Integer, ForeignKey("fire_clusters.id"), nullable=True)
    cluster = relationship("FireCluster", back_populates="alerts")

    # Status
    is_active = Column(Boolean, default=True)
    acknowledged = Column(Boolean, default=False)
    acknowledged_at = Column(DateTime)
    acknowledged_by = Column(String(100))

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    expires_at = Column(DateTime)

    # Notification tracking
    email_sent = Column(Boolean, default=False)
    sms_sent = Column(Boolean, default=False)
    push_sent = Column(Boolean, default=False)

    __table_args__ = (
        Index("idx_alert_level", level),
        Index("idx_alert_active", is_active),
        Index("idx_alert_created_at", created_at),
    )

    def __repr__(self):
        return f"<Alert({self.id}, level={self.level.value}, title={self.title[:30]})>"

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "level": self.level.value,
            "title": self.title,
            "message": self.message,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "state": self.state,
            "biome": self.biome,
            "cluster_id": self.cluster_id,
            "is_active": self.is_active,
            "acknowledged": self.acknowledged,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }


class UserReport(Base):
    """
    Fire report submitted by citizens.

    Crowdsourced fire detection data.
    """
    __tablename__ = "user_reports"

    id = Column(Integer, primary_key=True, index=True)

    # Location
    location = Column(Geometry("POINT", srid=4326), nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)

    # Report details
    description = Column(Text)
    photo_url = Column(String(500))
    has_flames = Column(Boolean, default=True)
    has_smoke = Column(Boolean, default=True)
    estimated_size = Column(String(20))  # small, medium, large

    # Reporter info
    reporter_name = Column(String(100))
    reporter_phone = Column(String(20))
    reporter_email = Column(String(100))

    # Validation
    status = Column(SQLEnum(ReportStatus), default=ReportStatus.PENDING)
    validated_by = Column(String(100))
    validated_at = Column(DateTime)
    matched_hotspot_id = Column(Integer, ForeignKey("hotspots.id"), nullable=True)

    # Confidence score from ML validation
    ml_confidence = Column(Float)

    # Timestamps
    reported_at = Column(DateTime, default=datetime.utcnow, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_report_location", location, postgresql_using="gist"),
        Index("idx_report_status", status),
        Index("idx_report_reported_at", reported_at),
    )

    def __repr__(self):
        return f"<UserReport({self.id}, status={self.status.value}, lat={self.latitude})>"

    def to_dict(self) -> dict:
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
            "status": self.status.value,
            "ml_confidence": self.ml_confidence,
            "reported_at": self.reported_at.isoformat() if self.reported_at else None
        }


class BiomeArea(Base):
    """
    Biome geographic area.

    Stores biome polygons and metadata.
    """
    __tablename__ = "biome_areas"

    id = Column(Integer, primary_key=True, index=True)

    # Biome info
    name = Column(String(50), nullable=False, unique=True)
    area = Column(Geometry("MULTIPOLYGON", srid=4326), nullable=False)

    # Properties
    carbon_tons_ha = Column(Float, nullable=False)
    recovery_years = Column(Integer, nullable=False)
    spread_factor = Column(Float, default=1.0)

    # Statistics
    total_area_km2 = Column(Float)
    fire_count_year = Column(Integer, default=0)
    burned_area_year_ha = Column(Float, default=0)

    # Metadata
    metadata = Column(JSONB, default={})
    updated_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_biome_area", area, postgresql_using="gist"),
    )

    def __repr__(self):
        return f"<BiomeArea({self.name}, carbon={self.carbon_tons_ha}t/ha)>"
