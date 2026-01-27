"""
FireWatch AI - Fire Clustering
Groups nearby fire hotspots into clusters representing individual fires.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, Tuple
import math

from src.core.geo_utils import (
    haversine_distance,
    calculate_centroid,
    calculate_convex_hull,
    calculate_polygon_area,
)


@dataclass
class FireCluster:
    """A cluster of fire hotspots representing a single fire event."""
    cluster_id: str
    hotspots: List[Any]  # List of FireHotspot objects
    center_latitude: float
    center_longitude: float
    bounding_box: Tuple[float, float, float, float]  # (west, south, east, north)
    convex_hull: List[Tuple[float, float]]
    first_detection: datetime
    last_detection: datetime
    total_frp: float
    average_frp: float
    max_frp: float
    area_km2: float
    high_confidence_count: int

    @property
    def duration_hours(self) -> float:
        """Calculate how long the fire has been active."""
        delta = self.last_detection - self.first_detection
        return delta.total_seconds() / 3600

    @property
    def hotspot_count(self) -> int:
        return len(self.hotspots)

    @property
    def intensity_level(self) -> str:
        """Classify fire intensity based on FRP."""
        if self.max_frp >= 100:
            return "extreme"
        elif self.max_frp >= 50:
            return "high"
        elif self.max_frp >= 20:
            return "moderate"
        else:
            return "low"

    @property
    def confidence_level(self) -> str:
        """Overall confidence based on high-confidence hotspot ratio."""
        if self.hotspot_count == 0:
            return "unknown"
        ratio = self.high_confidence_count / self.hotspot_count
        if ratio >= 0.7:
            return "high"
        elif ratio >= 0.4:
            return "moderate"
        else:
            return "low"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cluster_id": self.cluster_id,
            "center": {
                "latitude": self.center_latitude,
                "longitude": self.center_longitude,
            },
            "bounding_box": {
                "west": self.bounding_box[0],
                "south": self.bounding_box[1],
                "east": self.bounding_box[2],
                "north": self.bounding_box[3],
            },
            "hotspot_count": self.hotspot_count,
            "first_detection": self.first_detection.isoformat(),
            "last_detection": self.last_detection.isoformat(),
            "duration_hours": round(self.duration_hours, 2),
            "total_frp_mw": round(self.total_frp, 2),
            "average_frp_mw": round(self.average_frp, 2),
            "max_frp_mw": round(self.max_frp, 2),
            "area_km2": round(self.area_km2, 4),
            "intensity_level": self.intensity_level,
            "confidence_level": self.confidence_level,
            "high_confidence_count": self.high_confidence_count,
            "convex_hull": self.convex_hull,
        }

    def to_geojson(self) -> Dict[str, Any]:
        """Convert cluster to GeoJSON Feature."""
        # Reverse coordinates for GeoJSON (lon, lat)
        coordinates = [[lon, lat] for lat, lon in self.convex_hull]
        if coordinates and coordinates[0] != coordinates[-1]:
            coordinates.append(coordinates[0])  # Close the polygon

        return {
            "type": "Feature",
            "geometry": {
                "type": "Polygon",
                "coordinates": [coordinates],
            },
            "properties": {
                "cluster_id": self.cluster_id,
                "hotspot_count": self.hotspot_count,
                "max_frp_mw": round(self.max_frp, 2),
                "area_km2": round(self.area_km2, 4),
                "intensity_level": self.intensity_level,
            },
        }


def cluster_hotspots(
    hotspots: List[Any],
    distance_threshold_km: float = 5.0,
    time_threshold_hours: Optional[float] = None
) -> List[FireCluster]:
    """
    Cluster fire hotspots using DBSCAN-like algorithm.

    Args:
        hotspots: List of FireHotspot objects
        distance_threshold_km: Maximum distance between hotspots in same cluster
        time_threshold_hours: Optional time threshold for temporal clustering

    Returns:
        List of FireCluster objects
    """
    if not hotspots:
        return []

    # Initialize each hotspot as unvisited
    visited = [False] * len(hotspots)
    clusters = []
    cluster_count = 0

    for i, hotspot in enumerate(hotspots):
        if visited[i]:
            continue

        # Find all neighbors
        neighbors = _find_neighbors(
            hotspots, i, distance_threshold_km, time_threshold_hours
        )

        if len(neighbors) >= 1:  # At least 1 neighbor (including self)
            cluster_count += 1
            cluster_hotspots_list = _expand_cluster(
                hotspots, visited, i, neighbors,
                distance_threshold_km, time_threshold_hours
            )

            if cluster_hotspots_list:
                cluster = _create_cluster(
                    f"FIRE-{cluster_count:04d}",
                    cluster_hotspots_list
                )
                clusters.append(cluster)

    # Sort clusters by hotspot count (largest first)
    clusters.sort(key=lambda c: c.hotspot_count, reverse=True)

    return clusters


def _find_neighbors(
    hotspots: List[Any],
    index: int,
    distance_km: float,
    time_hours: Optional[float]
) -> List[int]:
    """Find all hotspots within distance threshold."""
    neighbors = []
    target = hotspots[index]

    for i, hotspot in enumerate(hotspots):
        dist = haversine_distance(
            target.latitude, target.longitude,
            hotspot.latitude, hotspot.longitude
        )

        if dist <= distance_km:
            # Check time threshold if specified
            if time_hours is not None:
                time_diff = abs(
                    (target.datetime - hotspot.datetime).total_seconds() / 3600
                )
                if time_diff <= time_hours:
                    neighbors.append(i)
            else:
                neighbors.append(i)

    return neighbors


def _expand_cluster(
    hotspots: List[Any],
    visited: List[bool],
    seed_index: int,
    neighbors: List[int],
    distance_km: float,
    time_hours: Optional[float]
) -> List[Any]:
    """Expand cluster from seed point."""
    cluster_hotspots = []
    queue = list(neighbors)

    while queue:
        current = queue.pop(0)
        if visited[current]:
            continue

        visited[current] = True
        cluster_hotspots.append(hotspots[current])

        # Find new neighbors
        new_neighbors = _find_neighbors(
            hotspots, current, distance_km, time_hours
        )

        for neighbor in new_neighbors:
            if not visited[neighbor] and neighbor not in queue:
                queue.append(neighbor)

    return cluster_hotspots


def _create_cluster(cluster_id: str, hotspots: List[Any]) -> FireCluster:
    """Create a FireCluster from a list of hotspots."""
    if not hotspots:
        raise ValueError("Cannot create cluster from empty hotspot list")

    # Extract coordinates
    points = [(h.latitude, h.longitude) for h in hotspots]

    # Calculate center
    center = calculate_centroid(points)

    # Calculate bounding box
    lats = [p[0] for p in points]
    lons = [p[1] for p in points]
    bbox = (min(lons), min(lats), max(lons), max(lats))

    # Calculate convex hull
    hull = calculate_convex_hull(points) if len(points) >= 3 else points

    # Calculate area
    area = calculate_polygon_area(hull) if len(hull) >= 3 else 0.0

    # Get timestamps
    timestamps = [h.datetime for h in hotspots if h.datetime]
    first_detection = min(timestamps) if timestamps else datetime.now()
    last_detection = max(timestamps) if timestamps else datetime.now()

    # Calculate FRP statistics
    frp_values = [h.frp for h in hotspots if h.frp and h.frp > 0]
    total_frp = sum(frp_values)
    average_frp = total_frp / len(frp_values) if frp_values else 0
    max_frp = max(frp_values) if frp_values else 0

    # Count high confidence hotspots
    high_conf = sum(1 for h in hotspots if h.confidence in ['h', 'high'])

    return FireCluster(
        cluster_id=cluster_id,
        hotspots=hotspots,
        center_latitude=center[0],
        center_longitude=center[1],
        bounding_box=bbox,
        convex_hull=hull,
        first_detection=first_detection,
        last_detection=last_detection,
        total_frp=total_frp,
        average_frp=average_frp,
        max_frp=max_frp,
        area_km2=area,
        high_confidence_count=high_conf,
    )


def get_cluster_statistics(clusters: List[FireCluster]) -> Dict[str, Any]:
    """
    Get aggregate statistics for a list of fire clusters.

    Args:
        clusters: List of FireCluster objects

    Returns:
        Dictionary with aggregate statistics
    """
    if not clusters:
        return {
            "total_clusters": 0,
            "total_hotspots": 0,
            "total_area_km2": 0,
            "total_frp_mw": 0,
        }

    total_hotspots = sum(c.hotspot_count for c in clusters)
    total_area = sum(c.area_km2 for c in clusters)
    total_frp = sum(c.total_frp for c in clusters)

    intensity_counts = {
        "extreme": 0,
        "high": 0,
        "moderate": 0,
        "low": 0,
    }
    for c in clusters:
        intensity_counts[c.intensity_level] += 1

    return {
        "total_clusters": len(clusters),
        "total_hotspots": total_hotspots,
        "total_area_km2": round(total_area, 2),
        "total_frp_mw": round(total_frp, 2),
        "average_cluster_size": round(total_hotspots / len(clusters), 1),
        "largest_cluster_hotspots": max(c.hotspot_count for c in clusters),
        "max_frp_mw": round(max(c.max_frp for c in clusters), 2),
        "intensity_distribution": intensity_counts,
    }
