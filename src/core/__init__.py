"""
FireWatch AI - Core Utilities
Central configuration, logging, and utility functions.
"""

from src.core.config import settings
from src.core.constants import (
    BRAZIL_BBOX,
    BIOME_BIOMASS,
    VEGETATION_FUEL_FACTORS,
    CONFIDENCE_LEVELS,
)
from src.core.geo_utils import (
    haversine_distance,
    calculate_bearing,
    point_in_polygon,
    create_buffer_polygon,
    calculate_polygon_area,
)

__all__ = [
    "settings",
    "BRAZIL_BBOX",
    "BIOME_BIOMASS",
    "VEGETATION_FUEL_FACTORS",
    "CONFIDENCE_LEVELS",
    "haversine_distance",
    "calculate_bearing",
    "point_in_polygon",
    "create_buffer_polygon",
    "calculate_polygon_area",
]
