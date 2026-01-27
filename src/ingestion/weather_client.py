"""
FireWatch AI - Weather Client
Fetches weather data from Open-Meteo API (free, no authentication required).
"""

import httpx
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from enum import Enum


class WeatherVariable(str, Enum):
    """Available weather variables from Open-Meteo."""
    TEMPERATURE = "temperature_2m"
    HUMIDITY = "relative_humidity_2m"
    WIND_SPEED = "wind_speed_10m"
    WIND_DIRECTION = "wind_direction_10m"
    WIND_GUSTS = "wind_gusts_10m"
    PRECIPITATION = "precipitation"
    RAIN = "rain"
    CLOUD_COVER = "cloud_cover"
    SURFACE_PRESSURE = "surface_pressure"
    DEW_POINT = "dew_point_2m"


@dataclass
class CurrentWeather:
    """Current weather conditions at a location."""
    latitude: float
    longitude: float
    timestamp: datetime
    temperature_celsius: float
    humidity_percent: float
    wind_speed_kmh: float
    wind_direction_degrees: float
    wind_gusts_kmh: Optional[float] = None
    precipitation_mm: float = 0.0
    cloud_cover_percent: float = 0.0
    surface_pressure_hpa: Optional[float] = None
    dew_point_celsius: Optional[float] = None

    @property
    def wind_direction_cardinal(self) -> str:
        """Get wind direction as cardinal direction."""
        directions = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
        index = round(self.wind_direction_degrees / 45) % 8
        return directions[index]

    @property
    def is_dry(self) -> bool:
        """Check if conditions are dry (no precipitation)."""
        return self.precipitation_mm == 0.0

    @property
    def fire_risk_factors(self) -> Dict[str, str]:
        """Assess fire risk based on weather conditions."""
        factors = {}

        # Temperature risk
        if self.temperature_celsius >= 40:
            factors["temperature"] = "extreme"
        elif self.temperature_celsius >= 35:
            factors["temperature"] = "high"
        elif self.temperature_celsius >= 30:
            factors["temperature"] = "moderate"
        else:
            factors["temperature"] = "low"

        # Humidity risk (inverted - low humidity = high risk)
        if self.humidity_percent <= 15:
            factors["humidity"] = "extreme"
        elif self.humidity_percent <= 25:
            factors["humidity"] = "high"
        elif self.humidity_percent <= 40:
            factors["humidity"] = "moderate"
        else:
            factors["humidity"] = "low"

        # Wind risk
        if self.wind_speed_kmh >= 50:
            factors["wind"] = "extreme"
        elif self.wind_speed_kmh >= 35:
            factors["wind"] = "high"
        elif self.wind_speed_kmh >= 20:
            factors["wind"] = "moderate"
        else:
            factors["wind"] = "low"

        return factors

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "latitude": self.latitude,
            "longitude": self.longitude,
            "timestamp": self.timestamp.isoformat(),
            "temperature_celsius": self.temperature_celsius,
            "humidity_percent": self.humidity_percent,
            "wind_speed_kmh": self.wind_speed_kmh,
            "wind_direction_degrees": self.wind_direction_degrees,
            "wind_direction_cardinal": self.wind_direction_cardinal,
            "wind_gusts_kmh": self.wind_gusts_kmh,
            "precipitation_mm": self.precipitation_mm,
            "cloud_cover_percent": self.cloud_cover_percent,
            "fire_risk_factors": self.fire_risk_factors,
        }


@dataclass
class HourlyForecast:
    """Hourly weather forecast."""
    timestamp: datetime
    temperature_celsius: float
    humidity_percent: float
    wind_speed_kmh: float
    wind_direction_degrees: float
    precipitation_probability: float = 0.0
    precipitation_mm: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "temperature_celsius": self.temperature_celsius,
            "humidity_percent": self.humidity_percent,
            "wind_speed_kmh": self.wind_speed_kmh,
            "wind_direction_degrees": self.wind_direction_degrees,
            "precipitation_probability": self.precipitation_probability,
            "precipitation_mm": self.precipitation_mm,
        }


@dataclass
class WeatherForecast:
    """Weather forecast for a location."""
    latitude: float
    longitude: float
    timezone: str
    hourly: List[HourlyForecast] = field(default_factory=list)

    @property
    def max_temperature(self) -> float:
        """Get maximum forecasted temperature."""
        if not self.hourly:
            return 0.0
        return max(h.temperature_celsius for h in self.hourly)

    @property
    def min_humidity(self) -> float:
        """Get minimum forecasted humidity."""
        if not self.hourly:
            return 100.0
        return min(h.humidity_percent for h in self.hourly)

    @property
    def max_wind_speed(self) -> float:
        """Get maximum forecasted wind speed."""
        if not self.hourly:
            return 0.0
        return max(h.wind_speed_kmh for h in self.hourly)

    @property
    def total_precipitation(self) -> float:
        """Get total forecasted precipitation."""
        return sum(h.precipitation_mm for h in self.hourly)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "latitude": self.latitude,
            "longitude": self.longitude,
            "timezone": self.timezone,
            "summary": {
                "max_temperature": self.max_temperature,
                "min_humidity": self.min_humidity,
                "max_wind_speed": self.max_wind_speed,
                "total_precipitation": self.total_precipitation,
            },
            "hourly": [h.to_dict() for h in self.hourly],
        }


class WeatherClient:
    """
    Client for Open-Meteo weather API.
    Free API with no authentication required.
    Documentation: https://open-meteo.com/en/docs
    """

    BASE_URL = "https://api.open-meteo.com/v1/forecast"

    def __init__(self, timeout: float = 30.0):
        """
        Initialize the weather client.

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

    def get_current_weather(
        self,
        latitude: float,
        longitude: float
    ) -> CurrentWeather:
        """
        Get current weather conditions for a location.

        Args:
            latitude: Location latitude (-90 to 90)
            longitude: Location longitude (-180 to 180)

        Returns:
            CurrentWeather object with current conditions
        """
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "current": [
                "temperature_2m",
                "relative_humidity_2m",
                "precipitation",
                "cloud_cover",
                "surface_pressure",
                "wind_speed_10m",
                "wind_direction_10m",
                "wind_gusts_10m",
            ],
            "timezone": "auto",
        }

        response = self._get_client().get(self.BASE_URL, params=params)
        response.raise_for_status()
        data = response.json()

        current = data.get("current", {})

        return CurrentWeather(
            latitude=data["latitude"],
            longitude=data["longitude"],
            timestamp=datetime.fromisoformat(
                current.get("time", datetime.now(timezone.utc).isoformat())
            ),
            temperature_celsius=current.get("temperature_2m", 0),
            humidity_percent=current.get("relative_humidity_2m", 0),
            wind_speed_kmh=current.get("wind_speed_10m", 0),
            wind_direction_degrees=current.get("wind_direction_10m", 0),
            wind_gusts_kmh=current.get("wind_gusts_10m"),
            precipitation_mm=current.get("precipitation", 0),
            cloud_cover_percent=current.get("cloud_cover", 0),
            surface_pressure_hpa=current.get("surface_pressure"),
        )

    def get_forecast(
        self,
        latitude: float,
        longitude: float,
        hours: int = 24
    ) -> WeatherForecast:
        """
        Get hourly weather forecast for a location.

        Args:
            latitude: Location latitude (-90 to 90)
            longitude: Location longitude (-180 to 180)
            hours: Number of hours to forecast (1-168)

        Returns:
            WeatherForecast object with hourly predictions
        """
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "hourly": [
                "temperature_2m",
                "relative_humidity_2m",
                "precipitation_probability",
                "precipitation",
                "wind_speed_10m",
                "wind_direction_10m",
            ],
            "forecast_hours": min(hours, 168),
            "timezone": "auto",
        }

        response = self._get_client().get(self.BASE_URL, params=params)
        response.raise_for_status()
        data = response.json()

        hourly_data = data.get("hourly", {})
        times = hourly_data.get("time", [])

        hourly_forecasts = []
        for i, time_str in enumerate(times[:hours]):
            forecast = HourlyForecast(
                timestamp=datetime.fromisoformat(time_str),
                temperature_celsius=hourly_data.get("temperature_2m", [0])[i],
                humidity_percent=hourly_data.get("relative_humidity_2m", [0])[i],
                wind_speed_kmh=hourly_data.get("wind_speed_10m", [0])[i],
                wind_direction_degrees=hourly_data.get("wind_direction_10m", [0])[i],
                precipitation_probability=hourly_data.get("precipitation_probability", [0])[i],
                precipitation_mm=hourly_data.get("precipitation", [0])[i],
            )
            hourly_forecasts.append(forecast)

        return WeatherForecast(
            latitude=data["latitude"],
            longitude=data["longitude"],
            timezone=data.get("timezone", "UTC"),
            hourly=hourly_forecasts,
        )

    def get_wind_data(
        self,
        latitude: float,
        longitude: float
    ) -> Dict[str, Any]:
        """
        Get detailed wind data for fire spread calculations.

        Args:
            latitude: Location latitude
            longitude: Location longitude

        Returns:
            Dictionary with wind speed, direction, and gusts
        """
        weather = self.get_current_weather(latitude, longitude)

        return {
            "speed_kmh": weather.wind_speed_kmh,
            "speed_ms": weather.wind_speed_kmh / 3.6,
            "direction_degrees": weather.wind_direction_degrees,
            "direction_cardinal": weather.wind_direction_cardinal,
            "gusts_kmh": weather.wind_gusts_kmh,
            "gusts_ms": (weather.wind_gusts_kmh or 0) / 3.6,
        }

    def get_fire_weather_index(
        self,
        latitude: float,
        longitude: float
    ) -> Dict[str, Any]:
        """
        Calculate a simple fire weather index based on current conditions.

        Args:
            latitude: Location latitude
            longitude: Location longitude

        Returns:
            Dictionary with fire weather assessment
        """
        weather = self.get_current_weather(latitude, longitude)

        # Simple fire weather index calculation
        # Higher temperature = higher risk
        temp_factor = min(weather.temperature_celsius / 45, 1.0)

        # Lower humidity = higher risk
        humidity_factor = max(0, 1 - (weather.humidity_percent / 100))

        # Higher wind = higher risk
        wind_factor = min(weather.wind_speed_kmh / 60, 1.0)

        # Combined index (0-100)
        index = (temp_factor * 0.3 + humidity_factor * 0.4 + wind_factor * 0.3) * 100

        # Risk level
        if index >= 75:
            risk_level = "extreme"
        elif index >= 50:
            risk_level = "high"
        elif index >= 25:
            risk_level = "moderate"
        else:
            risk_level = "low"

        return {
            "index": round(index, 1),
            "risk_level": risk_level,
            "factors": weather.fire_risk_factors,
            "conditions": weather.to_dict(),
        }


def get_weather_for_hotspot(
    latitude: float,
    longitude: float,
    timeout: float = 30.0
) -> CurrentWeather:
    """
    Convenience function to get weather for a fire hotspot.

    Args:
        latitude: Hotspot latitude
        longitude: Hotspot longitude
        timeout: Request timeout

    Returns:
        CurrentWeather object
    """
    with WeatherClient(timeout=timeout) as client:
        return client.get_current_weather(latitude, longitude)


def get_forecast_for_region(
    latitude: float,
    longitude: float,
    hours: int = 24,
    timeout: float = 30.0
) -> WeatherForecast:
    """
    Convenience function to get forecast for a region.

    Args:
        latitude: Region center latitude
        longitude: Region center longitude
        hours: Forecast hours
        timeout: Request timeout

    Returns:
        WeatherForecast object
    """
    with WeatherClient(timeout=timeout) as client:
        return client.get_forecast(latitude, longitude, hours)
