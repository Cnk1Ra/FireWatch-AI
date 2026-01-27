"""
FireWatch AI - Evacuation Route Calculator
Calculates safe evacuation routes away from fire spread.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
import math

from src.core.geo_utils import haversine_distance, calculate_bearing, destination_point


@dataclass
class AtRiskCommunity:
    """A community at risk from fire spread."""
    name: str
    latitude: float
    longitude: float
    population: int
    distance_from_fire_km: float
    estimated_arrival_hours: Optional[float]
    risk_level: str  # low, medium, high, critical
    evacuation_priority: int  # 1 = highest

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "location": {
                "latitude": self.latitude,
                "longitude": self.longitude,
            },
            "population": self.population,
            "distance_from_fire_km": round(self.distance_from_fire_km, 2),
            "estimated_arrival_hours": (
                round(self.estimated_arrival_hours, 2)
                if self.estimated_arrival_hours else None
            ),
            "risk_level": self.risk_level,
            "evacuation_priority": self.evacuation_priority,
        }


@dataclass
class EvacuationRoute:
    """A single evacuation route."""
    route_id: int
    origin_name: str
    destination_name: str
    destination_type: str  # shelter, safe_zone, hospital
    distance_km: float
    estimated_time_minutes: int
    road_name: str
    is_recommended: bool
    warning: Optional[str] = None
    polyline: List[Tuple[float, float]] = field(default_factory=list)
    instructions: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "route_id": self.route_id,
            "origin": self.origin_name,
            "destination": {
                "name": self.destination_name,
                "type": self.destination_type,
            },
            "distance_km": round(self.distance_km, 2),
            "estimated_time_minutes": self.estimated_time_minutes,
            "road": self.road_name,
            "is_recommended": self.is_recommended,
            "warning": self.warning,
            "instructions": self.instructions,
        }


@dataclass
class ShelterPoint:
    """Emergency shelter location."""
    name: str
    address: str
    latitude: float
    longitude: float
    capacity: int
    facilities: List[str]
    contact_phone: Optional[str] = None
    current_occupancy: int = 0

    @property
    def available_capacity(self) -> int:
        return max(0, self.capacity - self.current_occupancy)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "address": self.address,
            "location": {
                "latitude": self.latitude,
                "longitude": self.longitude,
            },
            "capacity": self.capacity,
            "available_capacity": self.available_capacity,
            "facilities": self.facilities,
            "contact_phone": self.contact_phone,
        }


@dataclass
class EvacuationPlan:
    """Complete evacuation plan for a fire event."""
    fire_id: str
    plan_timestamp: datetime
    fire_center: Tuple[float, float]
    fire_spread_direction: float
    evacuation_zones: List[AtRiskCommunity]
    routes: Dict[str, List[EvacuationRoute]]  # community_name -> routes
    shelter_points: List[ShelterPoint]
    emergency_contacts: Dict[str, str]
    general_instructions: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "fire_id": self.fire_id,
            "plan_timestamp": self.plan_timestamp.isoformat(),
            "fire_info": {
                "center": {
                    "latitude": self.fire_center[0],
                    "longitude": self.fire_center[1],
                },
                "spread_direction_degrees": round(self.fire_spread_direction, 1),
            },
            "evacuation_zones": [z.to_dict() for z in self.evacuation_zones],
            "routes_by_community": {
                name: [r.to_dict() for r in routes]
                for name, routes in self.routes.items()
            },
            "shelter_points": [s.to_dict() for s in self.shelter_points],
            "emergency_contacts": self.emergency_contacts,
            "general_instructions": self.general_instructions,
        }


def calculate_evacuation_routes(
    fire_center_lat: float,
    fire_center_lon: float,
    fire_spread_direction: float,
    spread_rate_m_per_min: float,
    communities: List[Dict[str, Any]],
    fire_id: str = "FIRE-001"
) -> EvacuationPlan:
    """
    Calculate evacuation routes for communities at risk.

    Args:
        fire_center_lat: Fire center latitude
        fire_center_lon: Fire center longitude
        fire_spread_direction: Direction fire is spreading (degrees)
        spread_rate_m_per_min: Fire spread rate
        communities: List of community dicts with name, lat, lon, population
        fire_id: Fire identifier

    Returns:
        EvacuationPlan object
    """
    at_risk = identify_at_risk_communities(
        fire_center_lat, fire_center_lon,
        fire_spread_direction, spread_rate_m_per_min,
        communities
    )

    # Calculate routes for each community
    all_routes: Dict[str, List[EvacuationRoute]] = {}

    for community in at_risk:
        routes = _calculate_routes_for_community(
            community, fire_center_lat, fire_center_lon, fire_spread_direction
        )
        all_routes[community.name] = routes

    # Generate shelter points
    shelters = _generate_shelter_points(
        fire_center_lat, fire_center_lon, fire_spread_direction
    )

    # Emergency contacts (Brazil)
    emergency_contacts = {
        "fire_department": "193",
        "civil_defense": "199",
        "military_police": "190",
        "ambulance": "192",
    }

    # General instructions
    instructions = [
        "Permaneça calmo e siga as instruções das autoridades",
        "Leve apenas itens essenciais: documentos, medicamentos, água",
        "Desligue gás e eletricidade antes de sair",
        "Feche portas e janelas (não tranque)",
        "Evite estradas que cruzam a direção do fogo",
        "Dirija com faróis ligados",
        "Se preso pela fumaça, reduza velocidade e ligue o pisca-alerta",
        "Vá para o abrigo mais próximo se não souber para onde ir",
    ]

    return EvacuationPlan(
        fire_id=fire_id,
        plan_timestamp=datetime.now(),
        fire_center=(fire_center_lat, fire_center_lon),
        fire_spread_direction=fire_spread_direction,
        evacuation_zones=at_risk,
        routes=all_routes,
        shelter_points=shelters,
        emergency_contacts=emergency_contacts,
        general_instructions=instructions,
    )


def identify_at_risk_communities(
    fire_lat: float,
    fire_lon: float,
    spread_direction: float,
    spread_rate_m_per_min: float,
    communities: List[Dict[str, Any]],
    max_radius_km: float = 30.0
) -> List[AtRiskCommunity]:
    """
    Identify communities at risk from fire spread.

    Args:
        fire_lat: Fire center latitude
        fire_lon: Fire center longitude
        spread_direction: Fire spread direction in degrees
        spread_rate_m_per_min: Spread rate in m/min
        communities: List of community dicts
        max_radius_km: Maximum radius to consider

    Returns:
        List of AtRiskCommunity objects, sorted by priority
    """
    at_risk = []

    for comm in communities:
        lat = comm.get("latitude", comm.get("lat", 0))
        lon = comm.get("longitude", comm.get("lon", 0))
        name = comm.get("name", "Unknown")
        population = comm.get("population", 1000)

        # Calculate distance and bearing
        distance = haversine_distance(fire_lat, fire_lon, lat, lon)

        if distance > max_radius_km:
            continue

        bearing = calculate_bearing(fire_lat, fire_lon, lat, lon)

        # Calculate angular difference from spread direction
        angle_diff = abs((bearing - spread_direction + 180) % 360 - 180)

        # Communities in spread direction are at higher risk
        if angle_diff > 90:
            # Behind the fire - lower risk
            risk_factor = 0.3
        elif angle_diff > 45:
            # Flanking position - medium risk
            risk_factor = 0.7
        else:
            # In direct path - high risk
            risk_factor = 1.0

        # Estimate time for fire to reach community
        if spread_rate_m_per_min > 0 and risk_factor > 0.5:
            effective_distance = distance * 1000 * (1 + angle_diff / 90)
            arrival_hours = (effective_distance / spread_rate_m_per_min) / 60
        else:
            arrival_hours = None

        # Determine risk level
        if arrival_hours is not None and arrival_hours < 2:
            risk_level = "critical"
            priority = 1
        elif arrival_hours is not None and arrival_hours < 6:
            risk_level = "high"
            priority = 2
        elif risk_factor > 0.7:
            risk_level = "medium"
            priority = 3
        else:
            risk_level = "low"
            priority = 4

        at_risk.append(AtRiskCommunity(
            name=name,
            latitude=lat,
            longitude=lon,
            population=population,
            distance_from_fire_km=distance,
            estimated_arrival_hours=arrival_hours,
            risk_level=risk_level,
            evacuation_priority=priority,
        ))

    # Sort by priority (1 = highest)
    at_risk.sort(key=lambda x: (x.evacuation_priority, -x.population))

    return at_risk


def _calculate_routes_for_community(
    community: AtRiskCommunity,
    fire_lat: float,
    fire_lon: float,
    fire_direction: float
) -> List[EvacuationRoute]:
    """Calculate evacuation routes for a single community."""
    routes = []

    # Calculate safe directions (away from fire)
    safe_direction = (fire_direction + 180) % 360

    # Generate potential destinations in safe directions
    distances = [10, 20, 30]  # km
    directions = [safe_direction, (safe_direction - 45) % 360, (safe_direction + 45) % 360]

    route_id = 1
    for dist in distances[:2]:  # Limit to 2 destinations
        for dir_offset, direction in enumerate(directions[:2]):
            dest_lat, dest_lon = destination_point(
                community.latitude, community.longitude, dist, direction
            )

            # Check if route crosses fire path
            warning = None
            route_bearing = calculate_bearing(
                community.latitude, community.longitude, dest_lat, dest_lon
            )
            angle_to_fire = abs((route_bearing - fire_direction + 180) % 360 - 180)

            if angle_to_fire < 30:
                warning = "ATENÇÃO: Esta rota passa próximo à direção do fogo"
                is_recommended = False
            else:
                is_recommended = (route_id == 1)

            # Estimate travel time (average 40 km/h in emergency)
            travel_time = int((dist / 40) * 60)

            # Generate basic instructions
            cardinal = _degrees_to_cardinal(direction)
            instructions = [
                f"Saia de {community.name} em direção {cardinal}",
                f"Siga pela estrada principal por {dist} km",
                f"Chegue ao ponto seguro em aproximadamente {travel_time} minutos",
            ]

            routes.append(EvacuationRoute(
                route_id=route_id,
                origin_name=community.name,
                destination_name=f"Ponto Seguro {route_id}",
                destination_type="safe_zone",
                distance_km=dist,
                estimated_time_minutes=travel_time,
                road_name=f"Estrada {cardinal}",
                is_recommended=is_recommended,
                warning=warning,
                instructions=instructions,
            ))
            route_id += 1

    return routes


def _generate_shelter_points(
    fire_lat: float,
    fire_lon: float,
    fire_direction: float
) -> List[ShelterPoint]:
    """Generate sample shelter points away from fire."""
    shelters = []

    # Place shelters in safe directions
    safe_direction = (fire_direction + 180) % 360

    for i, (dist, offset) in enumerate([(15, 0), (20, -30), (25, 30)]):
        direction = (safe_direction + offset) % 360
        lat, lon = destination_point(fire_lat, fire_lon, dist, direction)

        shelter = ShelterPoint(
            name=f"Abrigo Municipal {i + 1}",
            address=f"Centro da cidade, {dist}km da área de risco",
            latitude=lat,
            longitude=lon,
            capacity=500 * (i + 1),
            facilities=["água", "banheiros", "alimentação", "atendimento médico"],
            contact_phone=f"(XX) 9999-000{i + 1}",
        )
        shelters.append(shelter)

    return shelters


def _degrees_to_cardinal(degrees: float) -> str:
    """Convert degrees to cardinal direction in Portuguese."""
    directions = {
        "N": "Norte",
        "NE": "Nordeste",
        "E": "Leste",
        "SE": "Sudeste",
        "S": "Sul",
        "SW": "Sudoeste",
        "W": "Oeste",
        "NW": "Noroeste",
    }
    abbrev = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
    index = round(degrees / 45) % 8
    return directions[abbrev[index]]


def estimate_evacuation_time(
    population: int,
    num_routes: int = 2,
    vehicles_per_route_per_hour: int = 600
) -> Dict[str, Any]:
    """
    Estimate time needed to evacuate a population.

    Args:
        population: Number of people to evacuate
        num_routes: Number of evacuation routes available
        vehicles_per_route_per_hour: Vehicle capacity per route

    Returns:
        Dictionary with evacuation time estimates
    """
    # Assume average 2.5 people per vehicle
    people_per_vehicle = 2.5
    vehicles_needed = math.ceil(population / people_per_vehicle)

    total_capacity_per_hour = num_routes * vehicles_per_route_per_hour * people_per_vehicle
    hours_needed = population / total_capacity_per_hour

    return {
        "population": population,
        "vehicles_needed": vehicles_needed,
        "routes_available": num_routes,
        "evacuation_time_hours": round(hours_needed, 1),
        "recommended_start": "immediate" if hours_needed > 2 else "within 1 hour",
    }
