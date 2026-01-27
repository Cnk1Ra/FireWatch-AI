"""
FireWatch AI - Fire Propagation Model
Predicts where fire will spread based on weather, terrain, and fuel.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
import math

from src.core.geo_utils import (
    destination_point,
    create_buffer_polygon,
    calculate_polygon_area,
)


@dataclass
class PropagationStep:
    """Predicted fire state at a specific time."""
    time_hours: float
    timestamp: datetime
    center_latitude: float
    center_longitude: float
    predicted_area_hectares: float
    predicted_perimeter_km: float
    polygon: List[Tuple[float, float]]
    spread_direction_degrees: float
    spread_rate_m_per_min: float
    confidence: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "time_hours": self.time_hours,
            "timestamp": self.timestamp.isoformat(),
            "center": {
                "latitude": self.center_latitude,
                "longitude": self.center_longitude,
            },
            "predicted_area_hectares": round(self.predicted_area_hectares, 2),
            "predicted_perimeter_km": round(self.predicted_perimeter_km, 2),
            "spread_direction_degrees": round(self.spread_direction_degrees, 1),
            "spread_rate_m_per_min": round(self.spread_rate_m_per_min, 2),
            "confidence": round(self.confidence, 2),
        }

    def to_geojson(self) -> Dict[str, Any]:
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
                "time_hours": self.time_hours,
                "area_hectares": round(self.predicted_area_hectares, 2),
                "confidence": round(self.confidence, 2),
            },
        }


@dataclass
class Threat:
    """A community or asset at risk from fire spread."""
    threat_type: str  # populated_area, infrastructure, protected_area
    name: str
    latitude: float
    longitude: float
    distance_km: float
    estimated_arrival_hours: Optional[float]
    population: Optional[int] = None
    evacuation_recommended: bool = False
    priority: str = "medium"  # low, medium, high, critical

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.threat_type,
            "name": self.name,
            "location": {
                "latitude": self.latitude,
                "longitude": self.longitude,
            },
            "distance_km": round(self.distance_km, 2),
            "estimated_arrival_hours": (
                round(self.estimated_arrival_hours, 2)
                if self.estimated_arrival_hours else None
            ),
            "population": self.population,
            "evacuation_recommended": self.evacuation_recommended,
            "priority": self.priority,
        }


@dataclass
class PropagationPrediction:
    """Complete fire propagation prediction."""
    fire_id: str
    prediction_timestamp: datetime
    current_area_hectares: float
    current_center: Tuple[float, float]
    predictions: List[PropagationStep] = field(default_factory=list)
    threats: List[Threat] = field(default_factory=list)

    # Input conditions
    wind_speed_kmh: float = 0.0
    wind_direction_degrees: float = 0.0
    humidity_percent: float = 50.0
    temperature_celsius: float = 25.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "fire_id": self.fire_id,
            "prediction_timestamp": self.prediction_timestamp.isoformat(),
            "current_fire": {
                "center": {
                    "latitude": self.current_center[0],
                    "longitude": self.current_center[1],
                },
                "area_hectares": round(self.current_area_hectares, 2),
            },
            "conditions": {
                "wind_speed_kmh": self.wind_speed_kmh,
                "wind_direction_degrees": self.wind_direction_degrees,
                "humidity_percent": self.humidity_percent,
                "temperature_celsius": self.temperature_celsius,
            },
            "predictions": [p.to_dict() for p in self.predictions],
            "threats": [t.to_dict() for t in self.threats],
        }


def predict_fire_spread(
    center_lat: float,
    center_lon: float,
    current_area_hectares: float,
    wind_speed_kmh: float,
    wind_direction_degrees: float,
    humidity_percent: float = 50.0,
    temperature_celsius: float = 25.0,
    slope_degrees: float = 0.0,
    fuel_type: str = "cerrado",
    prediction_hours: List[int] = None,
    fire_id: str = "FIRE-001"
) -> PropagationPrediction:
    """
    Predict fire spread over time.

    Args:
        center_lat: Current fire center latitude
        center_lon: Current fire center longitude
        current_area_hectares: Current burned area
        wind_speed_kmh: Wind speed
        wind_direction_degrees: Wind direction (fire spreads downwind)
        humidity_percent: Relative humidity
        temperature_celsius: Air temperature
        slope_degrees: Terrain slope
        fuel_type: Vegetation/fuel type
        prediction_hours: List of hours to predict (default: [1, 3, 6])
        fire_id: Fire identifier

    Returns:
        PropagationPrediction object
    """
    if prediction_hours is None:
        prediction_hours = [1, 3, 6]

    now = datetime.now()

    # Calculate base spread rate
    base_spread_rate = calculate_spread_rate(
        wind_speed_kmh=wind_speed_kmh,
        humidity_percent=humidity_percent,
        temperature_celsius=temperature_celsius,
        slope_degrees=slope_degrees,
        fuel_type=fuel_type,
    )

    predictions = []
    current_center = (center_lat, center_lon)
    current_area = current_area_hectares

    for hours in sorted(prediction_hours):
        # Calculate new position (fire center moves downwind)
        spread_distance_km = (base_spread_rate * 60 * hours) / 1000

        # Fire spreads in wind direction
        new_center = destination_point(
            current_center[0], current_center[1],
            spread_distance_km * 0.3,  # Center moves slower than head
            wind_direction_degrees
        )

        # Calculate new area
        # Area growth depends on spread rate and time
        area_growth_factor = 1 + (base_spread_rate * 60 * hours / 1000)  # Rough estimate
        new_area = current_area * area_growth_factor

        # Calculate new perimeter (approximate for ellipse)
        new_perimeter = 2 * math.pi * math.sqrt(new_area / (100 * math.pi)) * 1.2

        # Create prediction polygon (elliptical, elongated in wind direction)
        polygon = _create_elliptical_polygon(
            new_center[0], new_center[1],
            new_area,
            wind_direction_degrees,
            elongation=1.5 + (wind_speed_kmh / 50)  # More elongated with stronger wind
        )

        # Confidence decreases with time
        confidence = max(0.3, 0.95 - (hours * 0.1))

        step = PropagationStep(
            time_hours=hours,
            timestamp=now + timedelta(hours=hours),
            center_latitude=new_center[0],
            center_longitude=new_center[1],
            predicted_area_hectares=new_area,
            predicted_perimeter_km=new_perimeter,
            polygon=polygon,
            spread_direction_degrees=wind_direction_degrees,
            spread_rate_m_per_min=base_spread_rate,
            confidence=confidence,
        )
        predictions.append(step)

    return PropagationPrediction(
        fire_id=fire_id,
        prediction_timestamp=now,
        current_area_hectares=current_area_hectares,
        current_center=(center_lat, center_lon),
        predictions=predictions,
        threats=[],  # Would be populated with nearby communities
        wind_speed_kmh=wind_speed_kmh,
        wind_direction_degrees=wind_direction_degrees,
        humidity_percent=humidity_percent,
        temperature_celsius=temperature_celsius,
    )


def calculate_spread_rate(
    wind_speed_kmh: float,
    humidity_percent: float = 50.0,
    temperature_celsius: float = 25.0,
    slope_degrees: float = 0.0,
    fuel_type: str = "cerrado"
) -> float:
    """
    Calculate fire spread rate using simplified Rothermel-based model.

    Args:
        wind_speed_kmh: Wind speed in km/h
        humidity_percent: Relative humidity (0-100)
        temperature_celsius: Air temperature
        slope_degrees: Terrain slope
        fuel_type: Vegetation type

    Returns:
        Spread rate in meters per minute
    """
    # Fuel factors
    fuel_factors = {
        "floresta_densa": {"base": 3.0, "wind": 0.8},
        "floresta_aberta": {"base": 5.0, "wind": 1.0},
        "cerrado": {"base": 8.0, "wind": 1.3},
        "campo": {"base": 12.0, "wind": 1.5},
        "pastagem": {"base": 15.0, "wind": 1.8},
        "agricultura": {"base": 10.0, "wind": 1.2},
    }

    fuel = fuel_factors.get(fuel_type, fuel_factors["cerrado"])
    base_rate = fuel["base"]

    # Wind factor (exponential relationship)
    wind_ms = wind_speed_kmh / 3.6
    wind_factor = 1.0 + (wind_ms * fuel["wind"] * 0.1)

    # Humidity factor (dry conditions = faster spread)
    humidity_factor = 1.0 + ((50 - humidity_percent) / 100)
    humidity_factor = max(0.5, min(humidity_factor, 2.0))

    # Temperature factor (hot conditions = faster spread)
    temp_factor = 1.0 + ((temperature_celsius - 25) / 50)
    temp_factor = max(0.7, min(temp_factor, 1.5))

    # Slope factor (fire spreads faster uphill)
    # Approximately doubles every 10 degrees of slope
    slope_factor = 2 ** (slope_degrees / 10)
    slope_factor = min(slope_factor, 4.0)  # Cap at 4x

    # Combined spread rate
    spread_rate = base_rate * wind_factor * humidity_factor * temp_factor * slope_factor

    return spread_rate


def _create_elliptical_polygon(
    center_lat: float,
    center_lon: float,
    area_hectares: float,
    direction_degrees: float,
    elongation: float = 1.5,
    num_points: int = 32
) -> List[Tuple[float, float]]:
    """Create an elliptical polygon representing fire shape."""
    area_km2 = area_hectares / 100
    radius_km = math.sqrt(area_km2 / math.pi)

    # Semi-axes
    a = radius_km * math.sqrt(elongation)  # Major axis (in wind direction)
    b = radius_km / math.sqrt(elongation)  # Minor axis

    points = []
    direction_rad = math.radians(direction_degrees)

    for i in range(num_points):
        theta = (2 * math.pi * i) / num_points

        # Ellipse point in local coordinates
        x = a * math.cos(theta)
        y = b * math.sin(theta)

        # Rotate by direction
        x_rot = x * math.cos(direction_rad) - y * math.sin(direction_rad)
        y_rot = x * math.sin(direction_rad) + y * math.cos(direction_rad)

        # Convert to bearing and distance
        distance = math.sqrt(x_rot**2 + y_rot**2)
        bearing = math.degrees(math.atan2(x_rot, y_rot))

        lat, lon = destination_point(center_lat, center_lon, distance, bearing)
        points.append((lat, lon))

    points.append(points[0])  # Close polygon
    return points
