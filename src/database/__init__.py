"""
Database module for FireWatch AI
PostgreSQL + PostGIS for geospatial data persistence
"""

from .connection import DatabaseConnection, get_db, init_db
from .models import (
    Base,
    Hotspot,
    FireCluster,
    WeatherRecord,
    Alert,
    UserReport,
    BiomeArea
)

__all__ = [
    "DatabaseConnection",
    "get_db",
    "init_db",
    "Base",
    "Hotspot",
    "FireCluster",
    "WeatherRecord",
    "Alert",
    "UserReport",
    "BiomeArea"
]
