"""
FireWatch AI - Geospatial Utilities
Common geospatial calculations and transformations.
"""

import math
from typing import List, Tuple, Optional
from dataclasses import dataclass

# Earth's radius in kilometers
EARTH_RADIUS_KM = 6371.0


@dataclass
class Point:
    """Geographic point with latitude and longitude."""
    latitude: float
    longitude: float

    def to_tuple(self) -> Tuple[float, float]:
        return (self.latitude, self.longitude)

    def to_tuple_lonlat(self) -> Tuple[float, float]:
        """Return as (longitude, latitude) for GeoJSON compatibility."""
        return (self.longitude, self.latitude)


@dataclass
class BoundingBox:
    """Geographic bounding box."""
    west: float   # min longitude
    south: float  # min latitude
    east: float   # max longitude
    north: float  # max latitude

    def contains(self, point: Point) -> bool:
        """Check if a point is within the bounding box."""
        return (
            self.west <= point.longitude <= self.east and
            self.south <= point.latitude <= self.north
        )

    def to_tuple(self) -> Tuple[float, float, float, float]:
        return (self.west, self.south, self.east, self.north)

    @property
    def center(self) -> Point:
        """Get the center point of the bounding box."""
        return Point(
            latitude=(self.south + self.north) / 2,
            longitude=(self.west + self.east) / 2
        )


def haversine_distance(
    lat1: float, lon1: float,
    lat2: float, lon2: float
) -> float:
    """
    Calculate the great-circle distance between two points on Earth.

    Args:
        lat1, lon1: First point coordinates in decimal degrees
        lat2, lon2: Second point coordinates in decimal degrees

    Returns:
        Distance in kilometers
    """
    # Convert to radians
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)

    # Haversine formula
    a = (
        math.sin(delta_lat / 2) ** 2 +
        math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return EARTH_RADIUS_KM * c


def calculate_bearing(
    lat1: float, lon1: float,
    lat2: float, lon2: float
) -> float:
    """
    Calculate the initial bearing from point 1 to point 2.

    Args:
        lat1, lon1: Start point coordinates in decimal degrees
        lat2, lon2: End point coordinates in decimal degrees

    Returns:
        Bearing in degrees (0-360, where 0=North, 90=East)
    """
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lon = math.radians(lon2 - lon1)

    x = math.sin(delta_lon) * math.cos(lat2_rad)
    y = (
        math.cos(lat1_rad) * math.sin(lat2_rad) -
        math.sin(lat1_rad) * math.cos(lat2_rad) * math.cos(delta_lon)
    )

    bearing = math.degrees(math.atan2(x, y))
    return (bearing + 360) % 360


def destination_point(
    lat: float, lon: float,
    distance_km: float,
    bearing_degrees: float
) -> Tuple[float, float]:
    """
    Calculate destination point given start, distance, and bearing.

    Args:
        lat, lon: Start point coordinates in decimal degrees
        distance_km: Distance to travel in kilometers
        bearing_degrees: Bearing in degrees (0=North, 90=East)

    Returns:
        Tuple of (latitude, longitude) of destination point
    """
    lat_rad = math.radians(lat)
    lon_rad = math.radians(lon)
    bearing_rad = math.radians(bearing_degrees)
    angular_distance = distance_km / EARTH_RADIUS_KM

    dest_lat = math.asin(
        math.sin(lat_rad) * math.cos(angular_distance) +
        math.cos(lat_rad) * math.sin(angular_distance) * math.cos(bearing_rad)
    )

    dest_lon = lon_rad + math.atan2(
        math.sin(bearing_rad) * math.sin(angular_distance) * math.cos(lat_rad),
        math.cos(angular_distance) - math.sin(lat_rad) * math.sin(dest_lat)
    )

    return (math.degrees(dest_lat), math.degrees(dest_lon))


def point_in_polygon(
    point: Tuple[float, float],
    polygon: List[Tuple[float, float]]
) -> bool:
    """
    Check if a point is inside a polygon using ray casting algorithm.

    Args:
        point: (latitude, longitude) tuple
        polygon: List of (latitude, longitude) tuples forming the polygon

    Returns:
        True if point is inside polygon
    """
    x, y = point
    n = len(polygon)
    inside = False

    p1x, p1y = polygon[0]
    for i in range(1, n + 1):
        p2x, p2y = polygon[i % n]
        if y > min(p1y, p2y):
            if y <= max(p1y, p2y):
                if x <= max(p1x, p2x):
                    if p1y != p2y:
                        xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                    if p1x == p2x or x <= xinters:
                        inside = not inside
        p1x, p1y = p2x, p2y

    return inside


def create_buffer_polygon(
    center_lat: float,
    center_lon: float,
    radius_km: float,
    num_points: int = 32
) -> List[Tuple[float, float]]:
    """
    Create a circular polygon (buffer) around a point.

    Args:
        center_lat, center_lon: Center point coordinates
        radius_km: Radius of the buffer in kilometers
        num_points: Number of points to approximate the circle

    Returns:
        List of (latitude, longitude) tuples forming the polygon
    """
    points = []
    for i in range(num_points):
        bearing = (360 / num_points) * i
        lat, lon = destination_point(center_lat, center_lon, radius_km, bearing)
        points.append((lat, lon))

    # Close the polygon
    points.append(points[0])
    return points


def calculate_polygon_area(polygon: List[Tuple[float, float]]) -> float:
    """
    Calculate the area of a polygon on Earth's surface.
    Uses the shoelace formula with latitude correction.

    Args:
        polygon: List of (latitude, longitude) tuples

    Returns:
        Area in square kilometers (approximate)
    """
    if len(polygon) < 3:
        return 0.0

    n = len(polygon)
    area = 0.0

    for i in range(n):
        j = (i + 1) % n
        lat1, lon1 = polygon[i]
        lat2, lon2 = polygon[j]

        # Convert to radians
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        lon1_rad = math.radians(lon1)
        lon2_rad = math.radians(lon2)

        # Spherical excess formula (simplified)
        area += (lon2_rad - lon1_rad) * (
            2 + math.sin(lat1_rad) + math.sin(lat2_rad)
        )

    area = abs(area) * EARTH_RADIUS_KM ** 2 / 2
    return area


def calculate_centroid(
    points: List[Tuple[float, float]]
) -> Tuple[float, float]:
    """
    Calculate the centroid (center of mass) of a set of points.

    Args:
        points: List of (latitude, longitude) tuples

    Returns:
        Tuple of (latitude, longitude) of the centroid
    """
    if not points:
        return (0.0, 0.0)

    lat_sum = sum(p[0] for p in points)
    lon_sum = sum(p[1] for p in points)
    n = len(points)

    return (lat_sum / n, lon_sum / n)


def calculate_convex_hull(
    points: List[Tuple[float, float]]
) -> List[Tuple[float, float]]:
    """
    Calculate the convex hull of a set of points using Graham scan.

    Args:
        points: List of (latitude, longitude) tuples

    Returns:
        List of points forming the convex hull
    """
    if len(points) < 3:
        return points

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    # Sort points lexicographically
    points = sorted(set(points))

    # Build lower hull
    lower = []
    for p in points:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)

    # Build upper hull
    upper = []
    for p in reversed(points):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)

    return lower[:-1] + upper[:-1]


def degrees_to_cardinal(degrees: float) -> str:
    """
    Convert bearing in degrees to cardinal direction.

    Args:
        degrees: Bearing in degrees (0-360)

    Returns:
        Cardinal direction string (N, NE, E, SE, S, SW, W, NW)
    """
    directions = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
    index = round(degrees / 45) % 8
    return directions[index]


def meters_to_degrees_lat(meters: float) -> float:
    """Convert meters to degrees of latitude."""
    return meters / 111320


def meters_to_degrees_lon(meters: float, latitude: float) -> float:
    """Convert meters to degrees of longitude at a given latitude."""
    return meters / (111320 * math.cos(math.radians(latitude)))


def degrees_to_meters_lat(degrees: float) -> float:
    """Convert degrees of latitude to meters."""
    return degrees * 111320


def degrees_to_meters_lon(degrees: float, latitude: float) -> float:
    """Convert degrees of longitude to meters at a given latitude."""
    return degrees * 111320 * math.cos(math.radians(latitude))
