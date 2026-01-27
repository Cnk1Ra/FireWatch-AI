"""
FireWatch AI - Fire Risk Index
Calculates fire danger based on weather, fuel, and historical data.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import math


@dataclass
class RiskFactor:
    """Individual risk factor assessment."""
    name: str
    value: float
    weight: float
    risk_level: str  # low, moderate, high, extreme
    description: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "value": round(self.value, 2),
            "weight": self.weight,
            "risk_level": self.risk_level,
            "description": self.description,
        }


@dataclass
class FireRiskAssessment:
    """Complete fire risk assessment for a location."""
    latitude: float
    longitude: float
    assessment_timestamp: datetime
    overall_risk_index: float  # 0-100
    overall_risk_level: str    # low, moderate, high, very_high, extreme

    factors: List[RiskFactor] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)

    # Input conditions
    temperature_celsius: float = 25.0
    humidity_percent: float = 50.0
    wind_speed_kmh: float = 10.0
    days_without_rain: int = 0
    vegetation_dryness: float = 0.5  # 0-1

    def to_dict(self) -> Dict[str, Any]:
        return {
            "location": {
                "latitude": self.latitude,
                "longitude": self.longitude,
            },
            "assessment_timestamp": self.assessment_timestamp.isoformat(),
            "risk": {
                "index": round(self.overall_risk_index, 1),
                "level": self.overall_risk_level,
            },
            "conditions": {
                "temperature_celsius": self.temperature_celsius,
                "humidity_percent": self.humidity_percent,
                "wind_speed_kmh": self.wind_speed_kmh,
                "days_without_rain": self.days_without_rain,
                "vegetation_dryness": round(self.vegetation_dryness, 2),
            },
            "factors": [f.to_dict() for f in self.factors],
            "recommendations": self.recommendations,
        }


@dataclass
class DailyRiskForecast:
    """Daily fire risk forecast."""
    date: datetime
    risk_index: float
    risk_level: str
    max_temperature: float
    min_humidity: float
    max_wind_speed: float
    precipitation_probability: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "date": self.date.strftime("%Y-%m-%d"),
            "risk_index": round(self.risk_index, 1),
            "risk_level": self.risk_level,
            "weather": {
                "max_temperature": self.max_temperature,
                "min_humidity": self.min_humidity,
                "max_wind_speed": self.max_wind_speed,
                "precipitation_probability": self.precipitation_probability,
            },
        }


def calculate_fire_risk(
    latitude: float,
    longitude: float,
    temperature_celsius: float,
    humidity_percent: float,
    wind_speed_kmh: float,
    days_without_rain: int = 0,
    vegetation_dryness: float = 0.5,
    biome: str = "Cerrado"
) -> FireRiskAssessment:
    """
    Calculate fire risk index for a location.

    Uses a weighted combination of weather, fuel moisture, and
    environmental factors to produce a risk score from 0-100.

    Args:
        latitude: Location latitude
        longitude: Location longitude
        temperature_celsius: Current temperature
        humidity_percent: Current relative humidity
        wind_speed_kmh: Current wind speed
        days_without_rain: Days since last significant rainfall
        vegetation_dryness: Vegetation dryness index (0-1)
        biome: Brazilian biome name

    Returns:
        FireRiskAssessment object
    """
    factors = []

    # Factor 1: Temperature (weight: 0.20)
    temp_risk = _calculate_temperature_risk(temperature_celsius)
    factors.append(RiskFactor(
        name="Temperature",
        value=temperature_celsius,
        weight=0.20,
        risk_level=_index_to_level(temp_risk),
        description=f"{temperature_celsius}°C - {_get_temp_description(temperature_celsius)}"
    ))

    # Factor 2: Humidity (weight: 0.25)
    humidity_risk = _calculate_humidity_risk(humidity_percent)
    factors.append(RiskFactor(
        name="Humidity",
        value=humidity_percent,
        weight=0.25,
        risk_level=_index_to_level(humidity_risk),
        description=f"{humidity_percent}% - {_get_humidity_description(humidity_percent)}"
    ))

    # Factor 3: Wind (weight: 0.20)
    wind_risk = _calculate_wind_risk(wind_speed_kmh)
    factors.append(RiskFactor(
        name="Wind Speed",
        value=wind_speed_kmh,
        weight=0.20,
        risk_level=_index_to_level(wind_risk),
        description=f"{wind_speed_kmh} km/h - {_get_wind_description(wind_speed_kmh)}"
    ))

    # Factor 4: Drought (weight: 0.20)
    drought_risk = _calculate_drought_risk(days_without_rain)
    factors.append(RiskFactor(
        name="Drought",
        value=days_without_rain,
        weight=0.20,
        risk_level=_index_to_level(drought_risk),
        description=f"{days_without_rain} days without rain"
    ))

    # Factor 5: Vegetation (weight: 0.15)
    veg_risk = vegetation_dryness * 100
    factors.append(RiskFactor(
        name="Vegetation Dryness",
        value=vegetation_dryness,
        weight=0.15,
        risk_level=_index_to_level(veg_risk),
        description=f"{vegetation_dryness:.0%} dry"
    ))

    # Calculate weighted overall risk
    overall_risk = (
        temp_risk * 0.20 +
        humidity_risk * 0.25 +
        wind_risk * 0.20 +
        drought_risk * 0.20 +
        veg_risk * 0.15
    )

    # Biome adjustment (some biomes are more fire-prone)
    biome_factors = {
        "Cerrado": 1.1,
        "Caatinga": 1.0,
        "Pantanal": 0.9,
        "Amazônia": 0.8,
        "Mata Atlântica": 0.85,
        "Pampa": 0.95,
    }
    overall_risk *= biome_factors.get(biome, 1.0)
    overall_risk = min(100, overall_risk)

    risk_level = _index_to_level(overall_risk)
    recommendations = _get_recommendations(risk_level)

    return FireRiskAssessment(
        latitude=latitude,
        longitude=longitude,
        assessment_timestamp=datetime.now(),
        overall_risk_index=overall_risk,
        overall_risk_level=risk_level,
        factors=factors,
        recommendations=recommendations,
        temperature_celsius=temperature_celsius,
        humidity_percent=humidity_percent,
        wind_speed_kmh=wind_speed_kmh,
        days_without_rain=days_without_rain,
        vegetation_dryness=vegetation_dryness,
    )


def get_risk_forecast(
    latitude: float,
    longitude: float,
    forecast_days: int = 7,
    base_conditions: Optional[Dict[str, float]] = None
) -> List[DailyRiskForecast]:
    """
    Generate fire risk forecast for upcoming days.

    Args:
        latitude: Location latitude
        longitude: Location longitude
        forecast_days: Number of days to forecast
        base_conditions: Current weather conditions

    Returns:
        List of DailyRiskForecast objects
    """
    if base_conditions is None:
        base_conditions = {
            "temperature": 30,
            "humidity": 40,
            "wind": 15,
            "days_dry": 5,
        }

    forecasts = []
    today = datetime.now()

    for day in range(forecast_days):
        date = today + timedelta(days=day)

        # Simulate weather variation (would use actual forecast in production)
        # Add some random-like variation based on day
        temp_var = 3 * math.sin(day * 0.5)
        humidity_var = -5 * math.cos(day * 0.7)
        wind_var = 5 * math.sin(day * 0.3)

        max_temp = base_conditions["temperature"] + temp_var
        min_humidity = max(10, base_conditions["humidity"] + humidity_var)
        max_wind = max(5, base_conditions["wind"] + wind_var)

        # Precipitation probability
        precip_prob = max(0, min(80, 20 - day * 3 + 10 * math.sin(day)))

        # Calculate risk for this day
        risk = calculate_fire_risk(
            latitude=latitude,
            longitude=longitude,
            temperature_celsius=max_temp,
            humidity_percent=min_humidity,
            wind_speed_kmh=max_wind,
            days_without_rain=base_conditions["days_dry"] + day,
        )

        forecasts.append(DailyRiskForecast(
            date=date,
            risk_index=risk.overall_risk_index,
            risk_level=risk.overall_risk_level,
            max_temperature=round(max_temp, 1),
            min_humidity=round(min_humidity, 1),
            max_wind_speed=round(max_wind, 1),
            precipitation_probability=round(precip_prob, 1),
        ))

    return forecasts


def _calculate_temperature_risk(temp: float) -> float:
    """Calculate risk from temperature (0-100)."""
    if temp <= 20:
        return 10
    elif temp <= 25:
        return 20 + (temp - 20) * 4
    elif temp <= 30:
        return 40 + (temp - 25) * 6
    elif temp <= 35:
        return 70 + (temp - 30) * 4
    elif temp <= 40:
        return 90 + (temp - 35) * 2
    else:
        return 100


def _calculate_humidity_risk(humidity: float) -> float:
    """Calculate risk from humidity (0-100). Lower humidity = higher risk."""
    if humidity >= 70:
        return 10
    elif humidity >= 50:
        return 10 + (70 - humidity) * 1.5
    elif humidity >= 30:
        return 40 + (50 - humidity) * 2
    elif humidity >= 20:
        return 80 + (30 - humidity) * 1
    elif humidity >= 10:
        return 90 + (20 - humidity) * 1
    else:
        return 100


def _calculate_wind_risk(wind: float) -> float:
    """Calculate risk from wind speed (0-100)."""
    if wind <= 10:
        return 10 + wind * 2
    elif wind <= 20:
        return 30 + (wind - 10) * 3
    elif wind <= 35:
        return 60 + (wind - 20) * 2
    elif wind <= 50:
        return 90 + (wind - 35) * 0.67
    else:
        return 100


def _calculate_drought_risk(days: int) -> float:
    """Calculate risk from days without rain (0-100)."""
    if days <= 3:
        return 10 + days * 5
    elif days <= 7:
        return 25 + (days - 3) * 7.5
    elif days <= 15:
        return 55 + (days - 7) * 3.75
    elif days <= 30:
        return 85 + (days - 15) * 1
    else:
        return 100


def _index_to_level(index: float) -> str:
    """Convert numeric index to risk level."""
    if index < 20:
        return "low"
    elif index < 40:
        return "moderate"
    elif index < 60:
        return "high"
    elif index < 80:
        return "very_high"
    else:
        return "extreme"


def _get_temp_description(temp: float) -> str:
    if temp < 25:
        return "Cool conditions"
    elif temp < 30:
        return "Warm conditions"
    elif temp < 35:
        return "Hot conditions"
    else:
        return "Extreme heat"


def _get_humidity_description(humidity: float) -> str:
    if humidity > 60:
        return "Humid conditions"
    elif humidity > 40:
        return "Moderate humidity"
    elif humidity > 25:
        return "Dry conditions"
    else:
        return "Very dry conditions"


def _get_wind_description(wind: float) -> str:
    if wind < 10:
        return "Light winds"
    elif wind < 25:
        return "Moderate winds"
    elif wind < 40:
        return "Strong winds"
    else:
        return "Dangerous winds"


def _get_recommendations(risk_level: str) -> List[str]:
    """Get recommendations based on risk level."""
    recommendations = {
        "low": [
            "Normal fire precautions apply",
            "Monitor weather conditions",
        ],
        "moderate": [
            "Exercise caution with fire activities",
            "Ensure firefighting equipment is ready",
            "Clear dry vegetation around structures",
        ],
        "high": [
            "Avoid all outdoor burning",
            "Increase vigilance for fire starts",
            "Review evacuation plans",
            "Keep vehicles fueled and ready",
        ],
        "very_high": [
            "No open fires permitted",
            "Restrict access to high-risk areas",
            "Pre-position firefighting resources",
            "Alert communities in vulnerable areas",
            "Prepare for possible evacuations",
        ],
        "extreme": [
            "Maximum alert status",
            "Evacuate vulnerable populations",
            "Close forests and parks",
            "All firefighting resources on standby",
            "Emergency services on high alert",
            "Consider preemptive evacuations",
        ],
    }
    return recommendations.get(risk_level, recommendations["moderate"])
