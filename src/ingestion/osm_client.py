"""
FireWatch AI - OpenStreetMap Client
Fetches road networks and infrastructure data for evacuation routing.
"""

import httpx
import time
from dataclasses import dataclass, field
from typing import List, Tuple, Optional, Dict, Any
from enum import Enum


class RoadType(str, Enum):
    """OpenStreetMap road classification."""
    MOTORWAY = "motorway"
    TRUNK = "trunk"
    PRIMARY = "primary"
    SECONDARY = "secondary"
    TERTIARY = "tertiary"
    RESIDENTIAL = "residential"
    UNCLASSIFIED = "unclassified"
    SERVICE = "service"
    TRACK = "track"
    PATH = "path"


@dataclass
class Road:
    """Road segment from OpenStreetMap."""
    osm_id: int
    name: Optional[str]
    road_type: str
    coordinates: List[Tuple[float, float]]  # List of (lat, lon) points
    lanes: int = 1
    max_speed_kmh: Optional[int] = None
    surface: Optional[str] = None
    oneway: bool = False

    @property
    def length_km(self) -> float:
        """Calculate approximate road length in kilometers."""
        from src.core.geo_utils import haversine_distance

        if len(self.coordinates) < 2:
            return 0.0

        total = 0.0
        for i in range(len(self.coordinates) - 1):
            lat1, lon1 = self.coordinates[i]
            lat2, lon2 = self.coordinates[i + 1]
            total += haversine_distance(lat1, lon1, lat2, lon2)

        return total

    @property
    def estimated_speed_kmh(self) -> int:
        """Estimate travel speed based on road type."""
        if self.max_speed_kmh:
            return self.max_speed_kmh

        speed_map = {
            "motorway": 100,
            "trunk": 80,
            "primary": 60,
            "secondary": 50,
            "tertiary": 40,
            "residential": 30,
            "unclassified": 30,
            "service": 20,
            "track": 20,
            "path": 10,
        }
        return speed_map.get(self.road_type, 30)

    @property
    def evacuation_capacity(self) -> str:
        """Assess road capacity for evacuation."""
        if self.road_type in ["motorway", "trunk"]:
            return "high"
        elif self.road_type in ["primary", "secondary"]:
            return "medium"
        else:
            return "low"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "osm_id": self.osm_id,
            "name": self.name,
            "road_type": self.road_type,
            "length_km": round(self.length_km, 2),
            "lanes": self.lanes,
            "max_speed_kmh": self.max_speed_kmh or self.estimated_speed_kmh,
            "surface": self.surface,
            "oneway": self.oneway,
            "evacuation_capacity": self.evacuation_capacity,
            "coordinates": self.coordinates,
        }


@dataclass
class Place:
    """A place/location from OpenStreetMap."""
    osm_id: int
    name: str
    place_type: str  # city, town, village, hamlet
    latitude: float
    longitude: float
    population: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "osm_id": self.osm_id,
            "name": self.name,
            "place_type": self.place_type,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "population": self.population,
        }


@dataclass
class EmergencyFacility:
    """Emergency facility (fire station, hospital, etc.)."""
    osm_id: int
    name: Optional[str]
    facility_type: str  # fire_station, hospital, police, shelter
    latitude: float
    longitude: float
    phone: Optional[str] = None
    address: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "osm_id": self.osm_id,
            "name": self.name,
            "facility_type": self.facility_type,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "phone": self.phone,
            "address": self.address,
        }


@dataclass
class RoadNetwork:
    """Road network for an area."""
    roads: List[Road] = field(default_factory=list)
    places: List[Place] = field(default_factory=list)
    emergency_facilities: List[EmergencyFacility] = field(default_factory=list)

    @property
    def total_road_length_km(self) -> float:
        return sum(r.length_km for r in self.roads)

    @property
    def major_roads(self) -> List[Road]:
        """Get only major roads suitable for evacuation."""
        major_types = ["motorway", "trunk", "primary", "secondary"]
        return [r for r in self.roads if r.road_type in major_types]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_roads": len(self.roads),
            "total_road_length_km": round(self.total_road_length_km, 2),
            "places": [p.to_dict() for p in self.places],
            "emergency_facilities": [f.to_dict() for f in self.emergency_facilities],
            "roads": [r.to_dict() for r in self.roads],
        }


class OSMClient:
    """
    Client for OpenStreetMap data via Overpass API.
    Rate limited to 1 request per second.
    """

    OVERPASS_URL = "https://overpass-api.de/api/interpreter"
    NOMINATIM_URL = "https://nominatim.openstreetmap.org"

    def __init__(self, timeout: float = 60.0):
        """
        Initialize the OSM client.

        Args:
            timeout: Request timeout in seconds
        """
        self.timeout = timeout
        self._client: Optional[httpx.Client] = None
        self._last_request_time = 0.0

    def __enter__(self):
        self._client = httpx.Client(timeout=self.timeout)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._client:
            self._client.close()

    def _get_client(self) -> httpx.Client:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.Client(
                timeout=self.timeout,
                headers={"User-Agent": "FireWatch-AI/1.0"}
            )
        return self._client

    def _rate_limit(self):
        """Ensure we don't exceed rate limits."""
        elapsed = time.time() - self._last_request_time
        if elapsed < 1.0:
            time.sleep(1.0 - elapsed)
        self._last_request_time = time.time()

    def get_roads_in_area(
        self,
        south: float,
        west: float,
        north: float,
        east: float,
        road_types: Optional[List[str]] = None
    ) -> List[Road]:
        """
        Get roads within a bounding box.

        Args:
            south, west, north, east: Bounding box coordinates
            road_types: Filter for specific road types (default: all main roads)

        Returns:
            List of Road objects
        """
        self._rate_limit()

        if road_types is None:
            road_types = ["motorway", "trunk", "primary", "secondary", "tertiary"]

        highway_filter = "|".join(road_types)

        query = f"""
        [out:json][timeout:60];
        (
          way["highway"~"^({highway_filter})$"]({south},{west},{north},{east});
        );
        out body;
        >;
        out skel qt;
        """

        response = self._get_client().post(
            self.OVERPASS_URL,
            data={"data": query}
        )
        response.raise_for_status()
        data = response.json()

        # Parse nodes and ways
        nodes = {}
        for element in data.get("elements", []):
            if element["type"] == "node":
                nodes[element["id"]] = (element["lat"], element["lon"])

        roads = []
        for element in data.get("elements", []):
            if element["type"] == "way":
                tags = element.get("tags", {})
                node_ids = element.get("nodes", [])

                # Get coordinates for all nodes in the way
                coords = []
                for nid in node_ids:
                    if nid in nodes:
                        coords.append(nodes[nid])

                if coords:
                    road = Road(
                        osm_id=element["id"],
                        name=tags.get("name"),
                        road_type=tags.get("highway", "unclassified"),
                        coordinates=coords,
                        lanes=int(tags.get("lanes", 1)),
                        max_speed_kmh=self._parse_speed(tags.get("maxspeed")),
                        surface=tags.get("surface"),
                        oneway=tags.get("oneway") == "yes",
                    )
                    roads.append(road)

        return roads

    def _parse_speed(self, speed_str: Optional[str]) -> Optional[int]:
        """Parse speed limit string to integer."""
        if not speed_str:
            return None
        try:
            # Handle formats like "60", "60 km/h", "60 mph"
            speed_str = speed_str.replace("km/h", "").replace("mph", "").strip()
            return int(speed_str)
        except (ValueError, AttributeError):
            return None

    def get_places_in_area(
        self,
        south: float,
        west: float,
        north: float,
        east: float
    ) -> List[Place]:
        """
        Get populated places within a bounding box.

        Args:
            south, west, north, east: Bounding box coordinates

        Returns:
            List of Place objects
        """
        self._rate_limit()

        query = f"""
        [out:json][timeout:60];
        (
          node["place"~"city|town|village|hamlet"]({south},{west},{north},{east});
        );
        out body;
        """

        response = self._get_client().post(
            self.OVERPASS_URL,
            data={"data": query}
        )
        response.raise_for_status()
        data = response.json()

        places = []
        for element in data.get("elements", []):
            if element["type"] == "node":
                tags = element.get("tags", {})
                population = tags.get("population")

                place = Place(
                    osm_id=element["id"],
                    name=tags.get("name", "Unknown"),
                    place_type=tags.get("place", "unknown"),
                    latitude=element["lat"],
                    longitude=element["lon"],
                    population=int(population) if population else None,
                )
                places.append(place)

        return places

    def get_emergency_facilities(
        self,
        south: float,
        west: float,
        north: float,
        east: float
    ) -> List[EmergencyFacility]:
        """
        Get emergency facilities within a bounding box.

        Args:
            south, west, north, east: Bounding box coordinates

        Returns:
            List of EmergencyFacility objects
        """
        self._rate_limit()

        query = f"""
        [out:json][timeout:60];
        (
          node["amenity"="fire_station"]({south},{west},{north},{east});
          node["amenity"="hospital"]({south},{west},{north},{east});
          node["amenity"="police"]({south},{west},{north},{east});
          node["emergency"="assembly_point"]({south},{west},{north},{east});
          way["amenity"="fire_station"]({south},{west},{north},{east});
          way["amenity"="hospital"]({south},{west},{north},{east});
        );
        out center;
        """

        response = self._get_client().post(
            self.OVERPASS_URL,
            data={"data": query}
        )
        response.raise_for_status()
        data = response.json()

        facilities = []
        for element in data.get("elements", []):
            tags = element.get("tags", {})

            # Get coordinates (center for ways)
            if "center" in element:
                lat = element["center"]["lat"]
                lon = element["center"]["lon"]
            else:
                lat = element.get("lat", 0)
                lon = element.get("lon", 0)

            facility_type = tags.get("amenity") or tags.get("emergency") or "unknown"

            facility = EmergencyFacility(
                osm_id=element["id"],
                name=tags.get("name"),
                facility_type=facility_type,
                latitude=lat,
                longitude=lon,
                phone=tags.get("phone"),
                address=tags.get("addr:street"),
            )
            facilities.append(facility)

        return facilities

    def get_road_network(
        self,
        center_lat: float,
        center_lon: float,
        radius_km: float = 10
    ) -> RoadNetwork:
        """
        Get complete road network around a point.

        Args:
            center_lat: Center latitude
            center_lon: Center longitude
            radius_km: Radius in kilometers

        Returns:
            RoadNetwork object with roads, places, and facilities
        """
        # Calculate bounding box
        # Approximate: 1 degree ≈ 111 km
        delta = radius_km / 111

        south = center_lat - delta
        north = center_lat + delta
        west = center_lon - delta
        east = center_lon + delta

        # Get all data
        roads = self.get_roads_in_area(south, west, north, east)
        places = self.get_places_in_area(south, west, north, east)
        facilities = self.get_emergency_facilities(south, west, north, east)

        return RoadNetwork(
            roads=roads,
            places=places,
            emergency_facilities=facilities,
        )

    def geocode(
        self,
        query: str
    ) -> Optional[Tuple[float, float]]:
        """
        Geocode an address or place name.

        Args:
            query: Address or place name

        Returns:
            Tuple of (latitude, longitude) or None if not found
        """
        self._rate_limit()

        params = {
            "q": query,
            "format": "json",
            "limit": 1,
        }

        response = self._get_client().get(
            f"{self.NOMINATIM_URL}/search",
            params=params
        )
        response.raise_for_status()
        data = response.json()

        if data:
            return (float(data[0]["lat"]), float(data[0]["lon"]))
        return None

    def reverse_geocode(
        self,
        latitude: float,
        longitude: float
    ) -> Optional[str]:
        """
        Reverse geocode coordinates to an address.

        Args:
            latitude: Location latitude
            longitude: Location longitude

        Returns:
            Address string or None
        """
        self._rate_limit()

        params = {
            "lat": latitude,
            "lon": longitude,
            "format": "json",
        }

        response = self._get_client().get(
            f"{self.NOMINATIM_URL}/reverse",
            params=params
        )
        response.raise_for_status()
        data = response.json()

        return data.get("display_name")


def get_evacuation_roads(
    fire_lat: float,
    fire_lon: float,
    radius_km: float = 20,
    timeout: float = 60.0
) -> RoadNetwork:
    """
    Convenience function to get road network for evacuation planning.

    Args:
        fire_lat: Fire center latitude
        fire_lon: Fire center longitude
        radius_km: Search radius in kilometers
        timeout: Request timeout

    Returns:
        RoadNetwork object
    """
    with OSMClient(timeout=timeout) as client:
        return client.get_road_network(fire_lat, fire_lon, radius_km)
