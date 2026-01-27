"""
FireWatch AI - Terrain Client
Fetches elevation and terrain data from Open-Meteo Elevation API and Open-Elevation.
"""

import httpx
import math
from dataclasses import dataclass
from typing import List, Tuple, Optional, Dict, Any


@dataclass
class TerrainData:
    """Terrain information for a location."""
    latitude: float
    longitude: float
    elevation_meters: float
    slope_degrees: Optional[float] = None
    aspect_degrees: Optional[float] = None  # Direction the slope faces (0=N, 90=E, 180=S, 270=W)

    @property
    def slope_percent(self) -> Optional[float]:
        """Convert slope from degrees to percent."""
        if self.slope_degrees is None:
            return None
        return math.tan(math.radians(self.slope_degrees)) * 100

    @property
    def aspect_cardinal(self) -> Optional[str]:
        """Get aspect as cardinal direction."""
        if self.aspect_degrees is None:
            return None
        directions = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
        index = round(self.aspect_degrees / 45) % 8
        return directions[index]

    @property
    def uphill_fire_factor(self) -> float:
        """
        Calculate fire spread factor based on slope.
        Fire spreads faster uphill - approximately doubles every 10 degrees.
        """
        if self.slope_degrees is None or self.slope_degrees <= 0:
            return 1.0
        return 2 ** (self.slope_degrees / 10)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "latitude": self.latitude,
            "longitude": self.longitude,
            "elevation_meters": self.elevation_meters,
            "slope_degrees": self.slope_degrees,
            "slope_percent": self.slope_percent,
            "aspect_degrees": self.aspect_degrees,
            "aspect_cardinal": self.aspect_cardinal,
            "uphill_fire_factor": self.uphill_fire_factor,
        }


@dataclass
class TerrainProfile:
    """Terrain profile along a line."""
    points: List[TerrainData]
    total_distance_km: float
    elevation_gain_m: float
    elevation_loss_m: float
    max_elevation_m: float
    min_elevation_m: float

    @property
    def average_slope(self) -> float:
        """Calculate average slope along the profile."""
        if not self.points or len(self.points) < 2:
            return 0.0
        slopes = [p.slope_degrees for p in self.points if p.slope_degrees is not None]
        return sum(slopes) / len(slopes) if slopes else 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_distance_km": self.total_distance_km,
            "elevation_gain_m": self.elevation_gain_m,
            "elevation_loss_m": self.elevation_loss_m,
            "max_elevation_m": self.max_elevation_m,
            "min_elevation_m": self.min_elevation_m,
            "average_slope": self.average_slope,
            "points": [p.to_dict() for p in self.points],
        }


class TerrainClient:
    """
    Client for terrain/elevation data.
    Uses Open-Meteo Elevation API (free, no auth required).
    """

    BASE_URL = "https://api.open-meteo.com/v1/elevation"
    OPEN_ELEVATION_URL = "https://api.open-elevation.com/api/v1/lookup"

    def __init__(self, timeout: float = 30.0):
        """
        Initialize the terrain client.

        Args:
            timeout: Request timeout in seconds
        """
        self.timeout = timeout
        self._client: Optional[httpx.Client] = None

    def __enter__(self):
        self._client = httpx.Client(timeout=self.timeout)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._client:
            self._client.close()

    def _get_client(self) -> httpx.Client:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.Client(timeout=self.timeout)
        return self._client

    def get_elevation(
        self,
        latitude: float,
        longitude: float
    ) -> float:
        """
        Get elevation for a single point.

        Args:
            latitude: Location latitude (-90 to 90)
            longitude: Location longitude (-180 to 180)

        Returns:
            Elevation in meters
        """
        params = {
            "latitude": latitude,
            "longitude": longitude,
        }

        response = self._get_client().get(self.BASE_URL, params=params)
        response.raise_for_status()
        data = response.json()

        elevations = data.get("elevation", [0])
        return elevations[0] if elevations else 0.0

    def get_elevations(
        self,
        points: List[Tuple[float, float]]
    ) -> List[float]:
        """
        Get elevations for multiple points.

        Args:
            points: List of (latitude, longitude) tuples

        Returns:
            List of elevations in meters
        """
        if not points:
            return []

        # Open-Meteo accepts comma-separated coordinates
        latitudes = ",".join(str(p[0]) for p in points)
        longitudes = ",".join(str(p[1]) for p in points)

        params = {
            "latitude": latitudes,
            "longitude": longitudes,
        }

        response = self._get_client().get(self.BASE_URL, params=params)
        response.raise_for_status()
        data = response.json()

        return data.get("elevation", [0] * len(points))

    def get_terrain_data(
        self,
        latitude: float,
        longitude: float,
        calculate_slope: bool = True
    ) -> TerrainData:
        """
        Get comprehensive terrain data for a location.

        Args:
            latitude: Location latitude
            longitude: Location longitude
            calculate_slope: Whether to calculate slope and aspect

        Returns:
            TerrainData object with elevation, slope, and aspect
        """
        elevation = self.get_elevation(latitude, longitude)

        slope = None
        aspect = None

        if calculate_slope:
            # Calculate slope using surrounding points
            # Use a small delta (approximately 100m)
            delta = 0.001  # ~111m at equator

            # Get elevations of 4 surrounding points
            points = [
                (latitude + delta, longitude),  # North
                (latitude - delta, longitude),  # South
                (latitude, longitude + delta),  # East
                (latitude, longitude - delta),  # West
            ]

            try:
                elevations = self.get_elevations(points)
                elev_n, elev_s, elev_e, elev_w = elevations

                # Calculate slope components (rise over run)
                # Distance in meters (approximate)
                distance_m = delta * 111320  # degrees to meters

                dz_dx = (elev_e - elev_w) / (2 * distance_m)  # East-West slope
                dz_dy = (elev_n - elev_s) / (2 * distance_m)  # North-South slope

                # Calculate slope magnitude (degrees)
                slope = math.degrees(math.atan(math.sqrt(dz_dx**2 + dz_dy**2)))

                # Calculate aspect (direction the slope faces)
                if dz_dx == 0 and dz_dy == 0:
                    aspect = 0  # Flat terrain
                else:
                    aspect = math.degrees(math.atan2(-dz_dx, -dz_dy))
                    aspect = (aspect + 360) % 360  # Normalize to 0-360

            except Exception:
                # If slope calculation fails, just return elevation
                pass

        return TerrainData(
            latitude=latitude,
            longitude=longitude,
            elevation_meters=elevation,
            slope_degrees=slope,
            aspect_degrees=aspect,
        )

    def get_terrain_profile(
        self,
        start: Tuple[float, float],
        end: Tuple[float, float],
        num_points: int = 20
    ) -> TerrainProfile:
        """
        Get terrain profile along a line between two points.

        Args:
            start: (latitude, longitude) of start point
            end: (latitude, longitude) of end point
            num_points: Number of sample points along the line

        Returns:
            TerrainProfile object with elevation data along the path
        """
        from src.core.geo_utils import haversine_distance

        # Generate points along the line
        points = []
        for i in range(num_points):
            t = i / (num_points - 1)
            lat = start[0] + t * (end[0] - start[0])
            lon = start[1] + t * (end[1] - start[1])
            points.append((lat, lon))

        # Get elevations
        elevations = self.get_elevations(points)

        # Calculate total distance
        total_distance = haversine_distance(
            start[0], start[1], end[0], end[1]
        )

        # Build terrain data points
        terrain_points = []
        elevation_gain = 0.0
        elevation_loss = 0.0

        for i, (point, elev) in enumerate(zip(points, elevations)):
            # Calculate slope between consecutive points
            slope = None
            if i > 0:
                prev_elev = elevations[i - 1]
                segment_distance = total_distance / (num_points - 1) * 1000  # km to m
                rise = elev - prev_elev

                if rise > 0:
                    elevation_gain += rise
                else:
                    elevation_loss += abs(rise)

                if segment_distance > 0:
                    slope = math.degrees(math.atan(rise / segment_distance))

            terrain_points.append(TerrainData(
                latitude=point[0],
                longitude=point[1],
                elevation_meters=elev,
                slope_degrees=slope,
            ))

        return TerrainProfile(
            points=terrain_points,
            total_distance_km=total_distance,
            elevation_gain_m=elevation_gain,
            elevation_loss_m=elevation_loss,
            max_elevation_m=max(elevations) if elevations else 0,
            min_elevation_m=min(elevations) if elevations else 0,
        )

    def get_terrain_grid(
        self,
        center_lat: float,
        center_lon: float,
        radius_km: float,
        grid_size: int = 10
    ) -> List[List[TerrainData]]:
        """
        Get terrain data for a grid around a center point.

        Args:
            center_lat: Center latitude
            center_lon: Center longitude
            radius_km: Radius in kilometers
            grid_size: Number of points per side

        Returns:
            2D list of TerrainData objects
        """
        from src.core.geo_utils import meters_to_degrees_lat, meters_to_degrees_lon

        # Calculate grid spacing
        delta_lat = meters_to_degrees_lat(radius_km * 1000 * 2 / grid_size)
        delta_lon = meters_to_degrees_lon(radius_km * 1000 * 2 / grid_size, center_lat)

        # Generate all points
        all_points = []
        for i in range(grid_size):
            for j in range(grid_size):
                lat = center_lat - radius_km * 0.009 + i * delta_lat
                lon = center_lon - radius_km * 0.009 / math.cos(math.radians(center_lat)) + j * delta_lon
                all_points.append((lat, lon))

        # Get all elevations in one request
        elevations = self.get_elevations(all_points)

        # Build grid
        grid = []
        idx = 0
        for i in range(grid_size):
            row = []
            for j in range(grid_size):
                point = all_points[idx]
                row.append(TerrainData(
                    latitude=point[0],
                    longitude=point[1],
                    elevation_meters=elevations[idx],
                ))
                idx += 1
            grid.append(row)

        return grid


def get_elevation_for_hotspot(
    latitude: float,
    longitude: float,
    timeout: float = 30.0
) -> TerrainData:
    """
    Convenience function to get terrain data for a fire hotspot.

    Args:
        latitude: Hotspot latitude
        longitude: Hotspot longitude
        timeout: Request timeout

    Returns:
        TerrainData object
    """
    with TerrainClient(timeout=timeout) as client:
        return client.get_terrain_data(latitude, longitude)
