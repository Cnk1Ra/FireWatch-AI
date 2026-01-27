"""
FireWatch AI - Fire Perimeter Calculation
Calculates and tracks fire perimeter from hotspot data.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import List, Dict, Any, Tuple, Optional
import math

from src.core.geo_utils import (
    calculate_convex_hull,
    calculate_polygon_area,
    haversine_distance,
    create_buffer_polygon,
    destination_point,
)


@dataclass
class FirePerimeter:
    """Fire perimeter representation."""
    fire_id: str
    timestamp: datetime
    polygon: List[Tuple[float, float]]  # List of (lat, lon) vertices
    center_latitude: float
    center_longitude: float
    area_hectares: float
    perimeter_km: float

    # Shape metrics
    compactness: float  # 0-1, 1 = perfect circle
    elongation: float   # ratio of major to minor axis

    # Fire spread info
    head_direction_degrees: Optional[float] = None  # Direction of fastest spread
    head_rate_m_per_min: Optional[float] = None     # Rate of spread at head

    def to_dict(self) -> Dict[str, Any]:
        return {
            "fire_id": self.fire_id,
            "timestamp": self.timestamp.isoformat(),
            "center": {
                "latitude": self.center_latitude,
                "longitude": self.center_longitude,
            },
            "area_hectares": round(self.area_hectares, 2),
            "area_km2": round(self.area_hectares / 100, 4),
            "perimeter_km": round(self.perimeter_km, 2),
            "shape": {
                "compactness": round(self.compactness, 3),
                "elongation": round(self.elongation, 2),
            },
            "spread": {
                "head_direction_degrees": self.head_direction_degrees,
                "head_rate_m_per_min": self.head_rate_m_per_min,
            },
            "vertices": len(self.polygon),
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
                "area_hectares": round(self.area_hectares, 2),
                "perimeter_km": round(self.perimeter_km, 2),
            },
        }


def calculate_perimeter(
    hotspots: List[Any],
    fire_id: str = "FIRE-001",
    wind_direction: Optional[float] = None,
    wind_speed_kmh: Optional[float] = None
) -> FirePerimeter:
    """
    Calculate fire perimeter from hotspots.

    Args:
        hotspots: List of FireHotspot objects
        fire_id: Fire identifier
        wind_direction: Wind direction in degrees (0=N, 90=E)
        wind_speed_kmh: Wind speed in km/h

    Returns:
        FirePerimeter object
    """
    if not hotspots:
        return FirePerimeter(
            fire_id=fire_id,
            timestamp=datetime.now(),
            polygon=[],
            center_latitude=0,
            center_longitude=0,
            area_hectares=0,
            perimeter_km=0,
            compactness=0,
            elongation=1,
        )

    # Extract coordinates
    points = [(h.latitude, h.longitude) for h in hotspots]

    # Calculate center
    center_lat = sum(p[0] for p in points) / len(points)
    center_lon = sum(p[1] for p in points) / len(points)

    # Create perimeter polygon
    if len(points) < 3:
        # For few points, create a buffer
        avg_frp = sum(h.frp for h in hotspots if h.frp) / len(hotspots) if hotspots else 10
        radius_km = 0.375 * math.sqrt(avg_frp / 10)  # Scale by FRP
        polygon = create_buffer_polygon(center_lat, center_lon, max(radius_km, 0.5))
    else:
        # Use convex hull
        polygon = calculate_convex_hull(points)

        # Expand polygon based on FRP (fires burn beyond hotspot locations)
        avg_frp = sum(h.frp for h in hotspots if h.frp) / len(hotspots) if hotspots else 10
        expansion_factor = 1.0 + (avg_frp / 100)  # 1.0 to 2.0
        polygon = _expand_polygon(polygon, center_lat, center_lon, expansion_factor)

    # Calculate metrics
    area_km2 = calculate_polygon_area(polygon)
    area_hectares = area_km2 * 100
    perimeter_km = _calculate_perimeter_length(polygon)

    # Calculate shape metrics
    compactness = _calculate_compactness(area_km2, perimeter_km)
    elongation = _calculate_elongation(polygon)

    # Calculate spread direction if wind data provided
    head_direction = None
    head_rate = None
    if wind_direction is not None and wind_speed_kmh is not None:
        head_direction = wind_direction  # Fire spreads downwind
        # Estimate head fire rate (simplified)
        head_rate = _estimate_spread_rate(wind_speed_kmh, avg_frp if hotspots else 10)

    return FirePerimeter(
        fire_id=fire_id,
        timestamp=datetime.now(),
        polygon=polygon,
        center_latitude=center_lat,
        center_longitude=center_lon,
        area_hectares=area_hectares,
        perimeter_km=perimeter_km,
        compactness=compactness,
        elongation=elongation,
        head_direction_degrees=head_direction,
        head_rate_m_per_min=head_rate,
    )


def create_fire_polygon(
    center_lat: float,
    center_lon: float,
    area_hectares: float,
    wind_direction: Optional[float] = None,
    elongation_factor: float = 1.5
) -> List[Tuple[float, float]]:
    """
    Create a fire polygon based on area and wind direction.

    Args:
        center_lat: Center latitude
        center_lon: Center longitude
        area_hectares: Desired area in hectares
        wind_direction: Wind direction in degrees (affects shape)
        elongation_factor: How elongated the fire shape is (1.0 = circle)

    Returns:
        List of (lat, lon) vertices forming the polygon
    """
    # Calculate radius for equivalent circular area
    area_km2 = area_hectares / 100
    radius_km = math.sqrt(area_km2 / math.pi)

    if wind_direction is None or elongation_factor <= 1.0:
        # Create circular polygon
        return create_buffer_polygon(center_lat, center_lon, radius_km, num_points=32)

    # Create elliptical polygon (elongated in wind direction)
    # Semi-major axis in wind direction, semi-minor perpendicular
    a = radius_km * math.sqrt(elongation_factor)  # Semi-major
    b = radius_km / math.sqrt(elongation_factor)  # Semi-minor

    points = []
    num_points = 32
    wind_rad = math.radians(wind_direction)

    for i in range(num_points):
        # Angle around the ellipse
        theta = (2 * math.pi * i) / num_points

        # Ellipse in local coordinates
        x = a * math.cos(theta)
        y = b * math.sin(theta)

        # Rotate by wind direction
        x_rot = x * math.cos(wind_rad) - y * math.sin(wind_rad)
        y_rot = x * math.sin(wind_rad) + y * math.cos(wind_rad)

        # Convert to lat/lon
        lat, lon = destination_point(center_lat, center_lon,
                                     math.sqrt(x_rot**2 + y_rot**2),
                                     math.degrees(math.atan2(x_rot, y_rot)))
        points.append((lat, lon))

    # Close the polygon
    points.append(points[0])

    return points


def _expand_polygon(
    polygon: List[Tuple[float, float]],
    center_lat: float,
    center_lon: float,
    factor: float
) -> List[Tuple[float, float]]:
    """Expand polygon outward from center."""
    expanded = []
    for lat, lon in polygon:
        # Vector from center to point
        dlat = lat - center_lat
        dlon = lon - center_lon

        # Scale the vector
        new_lat = center_lat + dlat * factor
        new_lon = center_lon + dlon * factor

        expanded.append((new_lat, new_lon))

    return expanded


def _calculate_perimeter_length(polygon: List[Tuple[float, float]]) -> float:
    """Calculate perimeter length in kilometers."""
    if len(polygon) < 2:
        return 0.0

    total = 0.0
    for i in range(len(polygon)):
        j = (i + 1) % len(polygon)
        total += haversine_distance(
            polygon[i][0], polygon[i][1],
            polygon[j][0], polygon[j][1]
        )

    return total


def _calculate_compactness(area_km2: float, perimeter_km: float) -> float:
    """
    Calculate compactness index (Polsby-Popper).
    1.0 = perfect circle, lower = more irregular.
    """
    if perimeter_km <= 0:
        return 0.0

    # Compactness = 4π × Area / Perimeter²
    return (4 * math.pi * area_km2) / (perimeter_km ** 2)


def _calculate_elongation(polygon: List[Tuple[float, float]]) -> float:
    """
    Calculate elongation ratio using bounding box.
    """
    if len(polygon) < 3:
        return 1.0

    lats = [p[0] for p in polygon]
    lons = [p[1] for p in polygon]

    # Bounding box dimensions (approximate km)
    lat_range = (max(lats) - min(lats)) * 111  # degrees to km
    lon_range = (max(lons) - min(lons)) * 111 * math.cos(math.radians(sum(lats)/len(lats)))

    if min(lat_range, lon_range) <= 0:
        return 1.0

    return max(lat_range, lon_range) / min(lat_range, lon_range)


def _estimate_spread_rate(wind_speed_kmh: float, frp: float) -> float:
    """
    Estimate fire spread rate at head (downwind).

    Args:
        wind_speed_kmh: Wind speed in km/h
        frp: Fire Radiative Power in MW

    Returns:
        Spread rate in meters per minute
    """
    # Base spread rate (m/min) - typical for moderate conditions
    base_rate = 5.0

    # Wind factor - spread rate increases with wind
    wind_factor = 1.0 + (wind_speed_kmh / 30)  # Linear increase

    # Intensity factor - more intense fires spread faster
    intensity_factor = 1.0 + math.sqrt(frp / 50)

    return base_rate * wind_factor * intensity_factor


def track_perimeter_change(
    old_perimeter: FirePerimeter,
    new_perimeter: FirePerimeter
) -> Dict[str, Any]:
    """
    Track changes between two perimeter measurements.

    Args:
        old_perimeter: Previous perimeter measurement
        new_perimeter: Current perimeter measurement

    Returns:
        Dictionary with change metrics
    """
    time_diff = (new_perimeter.timestamp - old_perimeter.timestamp).total_seconds() / 3600

    if time_diff <= 0:
        return {"error": "New timestamp must be after old timestamp"}

    area_change = new_perimeter.area_hectares - old_perimeter.area_hectares
    perimeter_change = new_perimeter.perimeter_km - old_perimeter.perimeter_km

    return {
        "time_difference_hours": round(time_diff, 2),
        "area_change_hectares": round(area_change, 2),
        "area_change_rate_ha_per_hour": round(area_change / time_diff, 2),
        "perimeter_change_km": round(perimeter_change, 2),
        "is_growing": area_change > 0,
        "growth_percentage": round(
            (area_change / old_perimeter.area_hectares * 100)
            if old_perimeter.area_hectares > 0 else 0, 1
        ),
    }
