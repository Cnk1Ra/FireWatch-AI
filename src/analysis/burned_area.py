"""
FireWatch AI - Burned Area Calculation
Estimates the area affected by fire based on hotspot data.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import List, Dict, Any, Tuple, Optional
import math

from src.core.geo_utils import (
    calculate_convex_hull,
    calculate_polygon_area,
    create_buffer_polygon,
    haversine_distance,
)


@dataclass
class BurnedAreaEstimate:
    """Estimate of burned area for a fire."""
    fire_id: str
    calculation_method: str
    timestamp: datetime
    center_latitude: float
    center_longitude: float
    total_area_hectares: float
    confidence_interval: Tuple[float, float]  # (min, max)
    confidence_level: float  # 0-1
    perimeter_km: float
    polygon: List[Tuple[float, float]]  # List of (lat, lon) vertices

    # Severity breakdown
    severe_area_hectares: float = 0.0
    moderate_area_hectares: float = 0.0
    light_area_hectares: float = 0.0

    # Expansion rate
    expansion_rate_ha_per_hour: Optional[float] = None

    @property
    def total_area_km2(self) -> float:
        return self.total_area_hectares / 100

    def to_dict(self) -> Dict[str, Any]:
        return {
            "fire_id": self.fire_id,
            "calculation_method": self.calculation_method,
            "timestamp": self.timestamp.isoformat(),
            "center": {
                "latitude": self.center_latitude,
                "longitude": self.center_longitude,
            },
            "burned_area": {
                "total_hectares": round(self.total_area_hectares, 2),
                "total_km2": round(self.total_area_km2, 4),
                "confidence_interval": [
                    round(self.confidence_interval[0], 2),
                    round(self.confidence_interval[1], 2),
                ],
                "confidence_level": round(self.confidence_level, 2),
            },
            "severity_breakdown": {
                "severe_hectares": round(self.severe_area_hectares, 2),
                "moderate_hectares": round(self.moderate_area_hectares, 2),
                "light_hectares": round(self.light_area_hectares, 2),
            },
            "perimeter_km": round(self.perimeter_km, 2),
            "expansion_rate_ha_per_hour": (
                round(self.expansion_rate_ha_per_hour, 2)
                if self.expansion_rate_ha_per_hour else None
            ),
        }

    def to_geojson(self) -> Dict[str, Any]:
        """Convert to GeoJSON Feature."""
        coordinates = [[lon, lat] for lat, lon in self.polygon]
        if coordinates and coordinates[0] != coordinates[-1]:
            coordinates.append(coordinates[0])

        return {
            "type": "Feature",
            "geometry": {
                "type": "Polygon",
                "coordinates": [coordinates],
            },
            "properties": {
                "fire_id": self.fire_id,
                "total_hectares": round(self.total_area_hectares, 2),
                "perimeter_km": round(self.perimeter_km, 2),
                "confidence_level": round(self.confidence_level, 2),
            },
        }


def calculate_burned_area(
    hotspots: List[Any],
    fire_id: str = "FIRE-001",
    method: str = "hybrid"
) -> BurnedAreaEstimate:
    """
    Calculate burned area from fire hotspots.

    Args:
        hotspots: List of FireHotspot objects
        fire_id: Identifier for this fire
        method: Calculation method ('convex_hull', 'buffer', 'hybrid')

    Returns:
        BurnedAreaEstimate object
    """
    if not hotspots:
        return BurnedAreaEstimate(
            fire_id=fire_id,
            calculation_method=method,
            timestamp=datetime.now(),
            center_latitude=0,
            center_longitude=0,
            total_area_hectares=0,
            confidence_interval=(0, 0),
            confidence_level=0,
            perimeter_km=0,
            polygon=[],
        )

    # Extract coordinates and FRP values
    points = [(h.latitude, h.longitude) for h in hotspots]
    frp_values = [h.frp for h in hotspots if h.frp and h.frp > 0]

    # Calculate center
    center_lat = sum(p[0] for p in points) / len(points)
    center_lon = sum(p[1] for p in points) / len(points)

    # Calculate area based on method
    if method == "convex_hull":
        polygon, area_km2 = _convex_hull_method(points)
    elif method == "buffer":
        polygon, area_km2 = _buffer_method(points, frp_values)
    else:  # hybrid
        polygon, area_km2 = _hybrid_method(points, frp_values)

    # Convert to hectares
    area_hectares = area_km2 * 100

    # Calculate perimeter
    perimeter = _calculate_perimeter(polygon)

    # Estimate severity distribution based on FRP
    severe, moderate, light = _estimate_severity_distribution(
        area_hectares, frp_values
    )

    # Calculate confidence based on number of hotspots and their distribution
    confidence = _calculate_confidence(hotspots, area_km2)

    # Confidence interval (±20% for typical uncertainty)
    margin = area_hectares * 0.2
    confidence_interval = (
        max(0, area_hectares - margin),
        area_hectares + margin
    )

    return BurnedAreaEstimate(
        fire_id=fire_id,
        calculation_method=method,
        timestamp=datetime.now(),
        center_latitude=center_lat,
        center_longitude=center_lon,
        total_area_hectares=area_hectares,
        confidence_interval=confidence_interval,
        confidence_level=confidence,
        perimeter_km=perimeter,
        polygon=polygon,
        severe_area_hectares=severe,
        moderate_area_hectares=moderate,
        light_area_hectares=light,
    )


def _convex_hull_method(
    points: List[Tuple[float, float]]
) -> Tuple[List[Tuple[float, float]], float]:
    """Calculate area using convex hull of hotspots."""
    if len(points) < 3:
        # For fewer than 3 points, create a small buffer
        if points:
            center = points[0]
            polygon = create_buffer_polygon(center[0], center[1], 0.5)
            return polygon, 0.79  # Approximate area of 0.5km radius circle
        return [], 0.0

    hull = calculate_convex_hull(points)
    area = calculate_polygon_area(hull)
    return hull, area


def _buffer_method(
    points: List[Tuple[float, float]],
    frp_values: List[float]
) -> Tuple[List[Tuple[float, float]], float]:
    """Calculate area using FRP-weighted buffers around hotspots."""
    if not points:
        return [], 0.0

    # Calculate buffer radius based on FRP
    # Higher FRP = larger affected area
    avg_frp = sum(frp_values) / len(frp_values) if frp_values else 10

    # Base radius: 375m (VIIRS pixel size) + FRP scaling
    base_radius_km = 0.375
    frp_factor = math.sqrt(avg_frp / 10)  # Square root scaling
    radius_km = base_radius_km * frp_factor

    # For simplicity, create a single buffer around center
    center_lat = sum(p[0] for p in points) / len(points)
    center_lon = sum(p[1] for p in points) / len(points)

    # Adjust radius based on spread of points
    if len(points) > 1:
        max_dist = max(
            haversine_distance(center_lat, center_lon, p[0], p[1])
            for p in points
        )
        radius_km = max(radius_km, max_dist + 0.5)

    polygon = create_buffer_polygon(center_lat, center_lon, radius_km)
    area = math.pi * radius_km ** 2

    return polygon, area


def _hybrid_method(
    points: List[Tuple[float, float]],
    frp_values: List[float]
) -> Tuple[List[Tuple[float, float]], float]:
    """
    Hybrid method combining convex hull with buffer expansion.

    Uses convex hull as base, then expands based on FRP intensity.
    """
    if len(points) < 3:
        return _buffer_method(points, frp_values)

    # Start with convex hull
    hull = calculate_convex_hull(points)
    base_area = calculate_polygon_area(hull)

    # Expand based on FRP
    avg_frp = sum(frp_values) / len(frp_values) if frp_values else 10

    # Expansion factor based on FRP (fires often burn beyond detected hotspots)
    expansion = 1.0 + (math.sqrt(avg_frp) / 20)  # 1.0 to ~1.5 for typical fires

    # Apply expansion to area estimate
    expanded_area = base_area * expansion

    # For the polygon, we keep the hull but note the area is expanded
    # (A more sophisticated approach would expand the hull vertices)

    return hull, expanded_area


def _calculate_perimeter(polygon: List[Tuple[float, float]]) -> float:
    """Calculate perimeter of a polygon in kilometers."""
    if len(polygon) < 2:
        return 0.0

    perimeter = 0.0
    for i in range(len(polygon)):
        j = (i + 1) % len(polygon)
        perimeter += haversine_distance(
            polygon[i][0], polygon[i][1],
            polygon[j][0], polygon[j][1]
        )

    return perimeter


def _estimate_severity_distribution(
    total_hectares: float,
    frp_values: List[float]
) -> Tuple[float, float, float]:
    """
    Estimate severity distribution based on FRP.

    Returns: (severe_ha, moderate_ha, light_ha)
    """
    if not frp_values or total_hectares <= 0:
        return 0.0, 0.0, total_hectares

    avg_frp = sum(frp_values) / len(frp_values)
    max_frp = max(frp_values)

    # Estimate percentages based on FRP distribution
    if max_frp >= 100:
        severe_pct = 0.3
        moderate_pct = 0.5
    elif max_frp >= 50:
        severe_pct = 0.15
        moderate_pct = 0.45
    elif max_frp >= 20:
        severe_pct = 0.05
        moderate_pct = 0.35
    else:
        severe_pct = 0.02
        moderate_pct = 0.28

    light_pct = 1.0 - severe_pct - moderate_pct

    return (
        total_hectares * severe_pct,
        total_hectares * moderate_pct,
        total_hectares * light_pct,
    )


def _calculate_confidence(
    hotspots: List[Any],
    area_km2: float
) -> float:
    """
    Calculate confidence level based on data quality.

    Factors:
    - Number of hotspots
    - Ratio of high-confidence hotspots
    - Hotspot density
    """
    if not hotspots:
        return 0.0

    n = len(hotspots)

    # Factor 1: Number of hotspots (more is better, up to a point)
    count_factor = min(n / 20, 1.0)

    # Factor 2: High confidence ratio
    high_conf = sum(1 for h in hotspots if h.confidence in ['h', 'high'])
    conf_ratio = high_conf / n

    # Factor 3: Density (hotspots per km2)
    density = n / area_km2 if area_km2 > 0 else 0
    density_factor = min(density / 10, 1.0)  # Cap at 10 per km2

    # Combined confidence
    confidence = (count_factor * 0.3 + conf_ratio * 0.4 + density_factor * 0.3)

    return min(confidence, 0.95)  # Cap at 95%


def estimate_area_from_hotspots(
    hotspots: List[Any],
    expansion_factor: float = 1.2
) -> float:
    """
    Quick estimate of burned area from hotspots.

    Args:
        hotspots: List of FireHotspot objects
        expansion_factor: Factor to expand estimated area

    Returns:
        Estimated area in hectares
    """
    if not hotspots:
        return 0.0

    points = [(h.latitude, h.longitude) for h in hotspots]

    if len(points) < 3:
        # Minimum area based on pixel size
        return len(points) * 14.0625  # VIIRS 375m pixel ≈ 14 hectares

    hull = calculate_convex_hull(points)
    area_km2 = calculate_polygon_area(hull)

    return area_km2 * 100 * expansion_factor
