"""
Fire ignition risk prediction using ML
Predicts where fires are likely to start based on conditions
"""

import logging
import os
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import math

logger = logging.getLogger(__name__)


@dataclass
class IgnitionRisk:
    """Fire ignition risk prediction."""
    latitude: float
    longitude: float
    risk_score: float  # 0-100

    # Risk level
    risk_level: str  # low, moderate, high, very_high, extreme

    # Contributing factors
    factors: Dict[str, float] = field(default_factory=dict)

    # Temporal prediction
    peak_risk_hour: Optional[int] = None  # Hour of day
    risk_duration_hours: int = 24

    # Spatial details
    risk_radius_km: float = 5.0
    biome: Optional[str] = None
    vegetation_type: Optional[str] = None

    # Historical context
    historical_fires_count: int = 0
    last_fire_days_ago: Optional[int] = None

    # Confidence
    confidence: float = 0.5
    model_version: str = "1.0"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "latitude": self.latitude,
            "longitude": self.longitude,
            "risk_score": self.risk_score,
            "risk_level": self.risk_level,
            "factors": self.factors,
            "peak_risk_hour": self.peak_risk_hour,
            "risk_duration_hours": self.risk_duration_hours,
            "risk_radius_km": self.risk_radius_km,
            "biome": self.biome,
            "vegetation_type": self.vegetation_type,
            "historical_fires_count": self.historical_fires_count,
            "confidence": self.confidence
        }


class IgnitionPredictor:
    """
    Predicts fire ignition risk for locations.

    Uses weather, vegetation, topography, and historical data.
    """

    # Factor weights
    WEIGHTS = {
        "temperature": 0.20,
        "humidity": 0.20,
        "wind": 0.10,
        "drought": 0.15,
        "vegetation": 0.15,
        "historical": 0.10,
        "human_activity": 0.10
    }

    # Risk thresholds
    RISK_LEVELS = {
        (0, 20): "low",
        (20, 40): "moderate",
        (40, 60): "high",
        (60, 80): "very_high",
        (80, 100): "extreme"
    }

    def __init__(
        self,
        model_path: Optional[str] = None,
        use_historical: bool = True
    ):
        """
        Initialize predictor.

        Args:
            model_path: Path to trained model
            use_historical: Include historical fire data
        """
        self.model_path = model_path
        self.use_historical = use_historical

        self._model = None
        self._scaler = None

        if model_path:
            self._load_model()

    def _load_model(self) -> None:
        """Load trained prediction model."""
        try:
            import joblib
            self._model = joblib.load(self.model_path)
            logger.info(f"Loaded ignition model: {self.model_path}")
        except Exception as e:
            logger.warning(f"Could not load model: {e}")

    def predict(
        self,
        latitude: float,
        longitude: float,
        weather: Dict[str, float],
        vegetation_data: Optional[Dict] = None,
        historical_fires: Optional[List[Dict]] = None
    ) -> IgnitionRisk:
        """
        Predict ignition risk for a location.

        Args:
            latitude: Location latitude
            longitude: Location longitude
            weather: Weather conditions
            vegetation_data: Vegetation information
            historical_fires: Historical fire data

        Returns:
            IgnitionRisk prediction
        """
        factors = {}

        # Calculate individual risk factors
        factors["temperature"] = self._temperature_risk(
            weather.get("temperature", 25)
        )

        factors["humidity"] = self._humidity_risk(
            weather.get("humidity", 50)
        )

        factors["wind"] = self._wind_risk(
            weather.get("wind_speed", 10)
        )

        factors["drought"] = self._drought_risk(
            weather.get("days_without_rain", 0),
            weather.get("precipitation", 0)
        )

        # Vegetation risk
        if vegetation_data:
            factors["vegetation"] = self._vegetation_risk(vegetation_data)
        else:
            factors["vegetation"] = self._estimate_vegetation_risk(latitude, longitude)

        # Historical risk
        if historical_fires and self.use_historical:
            factors["historical"] = self._historical_risk(
                historical_fires, latitude, longitude
            )
        else:
            factors["historical"] = self._estimate_historical_risk(latitude, longitude)

        # Human activity risk
        factors["human_activity"] = self._human_activity_risk(latitude, longitude)

        # Calculate weighted risk score
        risk_score = sum(
            factors[f] * self.WEIGHTS[f]
            for f in factors
        )

        # Normalize to 0-100
        risk_score = min(100, max(0, risk_score))

        # Determine risk level
        risk_level = self._get_risk_level(risk_score)

        # Determine peak risk hour (typically afternoon)
        peak_hour = self._calculate_peak_hour(weather)

        # Estimate biome
        biome = self._estimate_biome(latitude, longitude)

        result = IgnitionRisk(
            latitude=latitude,
            longitude=longitude,
            risk_score=round(risk_score, 1),
            risk_level=risk_level,
            factors={k: round(v, 1) for k, v in factors.items()},
            peak_risk_hour=peak_hour,
            biome=biome,
            confidence=self._calculate_confidence(factors)
        )

        # Use ML model if available
        if self._model is not None:
            ml_score = self._ml_predict(factors)
            result.risk_score = (result.risk_score + ml_score) / 2
            result.risk_level = self._get_risk_level(result.risk_score)

        return result

    def predict_grid(
        self,
        bounds: Dict[str, float],
        resolution_km: float,
        weather: Dict[str, float]
    ) -> List[IgnitionRisk]:
        """
        Predict risk for a grid of points.

        Args:
            bounds: {west, south, east, north}
            resolution_km: Grid cell size in km
            weather: Weather conditions for region

        Returns:
            List of IgnitionRisk for each grid cell
        """
        predictions = []

        # Calculate grid
        lat_step = resolution_km / 111  # ~111 km per degree
        lon_step = resolution_km / (111 * math.cos(math.radians(
            (bounds["south"] + bounds["north"]) / 2
        )))

        lat = bounds["south"]
        while lat <= bounds["north"]:
            lon = bounds["west"]
            while lon <= bounds["east"]:
                prediction = self.predict(lat, lon, weather)
                predictions.append(prediction)
                lon += lon_step
            lat += lat_step

        return predictions

    def _temperature_risk(self, temperature: float) -> float:
        """Calculate temperature risk factor (0-100)."""
        if temperature < 20:
            return 10
        elif temperature < 25:
            return 20 + (temperature - 20) * 4
        elif temperature < 30:
            return 40 + (temperature - 25) * 6
        elif temperature < 35:
            return 70 + (temperature - 30) * 4
        elif temperature < 40:
            return 90 + (temperature - 35) * 2
        else:
            return 100

    def _humidity_risk(self, humidity: float) -> float:
        """Calculate humidity risk factor (0-100). Lower = higher risk."""
        if humidity >= 80:
            return 10
        elif humidity >= 60:
            return 30 - (humidity - 60) * 1
        elif humidity >= 40:
            return 50 - (humidity - 40) * 1
        elif humidity >= 20:
            return 70 + (40 - humidity) * 1
        else:
            return 90 + (20 - humidity) * 0.5

    def _wind_risk(self, wind_speed: float) -> float:
        """Calculate wind risk factor (0-100)."""
        if wind_speed < 5:
            return 20
        elif wind_speed < 15:
            return 20 + wind_speed * 2
        elif wind_speed < 30:
            return 50 + (wind_speed - 15) * 2
        elif wind_speed < 50:
            return 80 + (wind_speed - 30) * 0.5
        else:
            return 90

    def _drought_risk(
        self,
        days_without_rain: int,
        recent_precipitation: float
    ) -> float:
        """Calculate drought risk factor (0-100)."""
        base_risk = min(100, days_without_rain * 5)

        # Recent rain reduces risk
        if recent_precipitation > 10:
            base_risk *= 0.5
        elif recent_precipitation > 5:
            base_risk *= 0.7
        elif recent_precipitation > 0:
            base_risk *= 0.9

        return min(100, base_risk)

    def _vegetation_risk(self, vegetation_data: Dict) -> float:
        """Calculate vegetation risk factor."""
        veg_type = vegetation_data.get("type", "unknown")
        moisture = vegetation_data.get("moisture", 0.5)
        density = vegetation_data.get("density", 0.5)

        # Base risk by vegetation type
        type_risks = {
            "cerrado": 80,
            "savanna": 75,
            "grassland": 70,
            "dry_forest": 65,
            "tropical_forest": 40,
            "wetland": 20,
            "agricultural": 50
        }

        base_risk = type_risks.get(veg_type, 50)

        # Adjust for moisture
        moisture_factor = 1 - moisture
        base_risk *= (0.5 + moisture_factor * 0.5)

        return min(100, base_risk)

    def _estimate_vegetation_risk(
        self,
        latitude: float,
        longitude: float
    ) -> float:
        """Estimate vegetation risk based on location."""
        # Brazilian biome approximations
        if -10 <= latitude <= 5 and -74 <= longitude <= -44:
            return 45  # Amazon - lower risk
        elif -24 <= latitude <= -2 and -60 <= longitude <= -41:
            return 75  # Cerrado - high risk
        elif -22 <= latitude <= -15 and -59 <= longitude <= -54:
            return 60  # Pantanal - moderate
        else:
            return 50  # Default

    def _historical_risk(
        self,
        historical_fires: List[Dict],
        latitude: float,
        longitude: float
    ) -> float:
        """Calculate risk from historical fire data."""
        nearby_fires = 0
        recent_fires = 0
        now = datetime.utcnow()

        for fire in historical_fires:
            # Check distance
            fire_lat = fire.get("latitude", 0)
            fire_lon = fire.get("longitude", 0)
            distance = math.sqrt(
                (latitude - fire_lat)**2 +
                (longitude - fire_lon)**2
            ) * 111  # Approximate km

            if distance <= 10:
                nearby_fires += 1

                # Check recency
                fire_date = fire.get("date")
                if fire_date:
                    if isinstance(fire_date, str):
                        fire_date = datetime.fromisoformat(fire_date)
                    days_ago = (now - fire_date).days
                    if days_ago <= 365:
                        recent_fires += 1

        # More historical fires = higher risk
        return min(100, nearby_fires * 5 + recent_fires * 10)

    def _estimate_historical_risk(
        self,
        latitude: float,
        longitude: float
    ) -> float:
        """Estimate historical risk without data."""
        # Known fire-prone areas
        if -18 <= latitude <= -7 and -62 <= longitude <= -50:
            return 70  # Mato Grosso - high historical fire activity
        elif -12 <= latitude <= -5 and -50 <= longitude <= -44:
            return 65  # Tocantins/Maranhao
        else:
            return 40

    def _human_activity_risk(
        self,
        latitude: float,
        longitude: float
    ) -> float:
        """Estimate risk from human activity."""
        # Agricultural frontiers have higher risk
        if -18 <= latitude <= -5 and -62 <= longitude <= -45:
            return 70  # Agricultural frontier
        elif -25 <= latitude <= -19 and -55 <= longitude <= -48:
            return 50  # Established agricultural area
        else:
            return 30

    def _get_risk_level(self, score: float) -> str:
        """Convert score to risk level."""
        for (low, high), level in self.RISK_LEVELS.items():
            if low <= score < high:
                return level
        return "extreme"

    def _calculate_peak_hour(self, weather: Dict) -> int:
        """Calculate peak risk hour of day."""
        # Peak risk typically in afternoon (14:00-16:00)
        base_hour = 14

        # Adjust for wind patterns
        if weather.get("wind_speed", 0) > 20:
            base_hour = 15  # Higher wind = later peak

        return base_hour

    def _estimate_biome(
        self,
        latitude: float,
        longitude: float
    ) -> str:
        """Estimate biome from coordinates."""
        biomes = [
            ("Amazonia", -10, -74, 5, -44),
            ("Cerrado", -24, -60, -2, -41),
            ("Pantanal", -22, -59, -15, -54),
            ("Caatinga", -17, -46, -2, -35),
            ("Mata Atlantica", -30, -55, -3, -34),
            ("Pampa", -34, -58, -28, -49)
        ]

        for name, south, west, north, east in biomes:
            if south <= latitude <= north and west <= longitude <= east:
                return name

        return "Desconhecido"

    def _calculate_confidence(self, factors: Dict[str, float]) -> float:
        """Calculate prediction confidence."""
        # More extreme values = higher confidence
        extremes = sum(1 for v in factors.values() if v < 20 or v > 80)
        return 0.5 + (extremes / len(factors)) * 0.3

    def _ml_predict(self, factors: Dict[str, float]) -> float:
        """Use ML model for prediction."""
        try:
            features = [factors.get(f, 50) for f in self.WEIGHTS.keys()]
            prediction = self._model.predict([features])[0]
            return float(prediction)
        except Exception:
            return 50


def predict_ignition_risk(
    latitude: float,
    longitude: float,
    weather: Dict[str, float]
) -> IgnitionRisk:
    """
    Convenience function to predict ignition risk.

    Args:
        latitude: Location latitude
        longitude: Location longitude
        weather: Weather conditions

    Returns:
        IgnitionRisk
    """
    predictor = IgnitionPredictor()
    return predictor.predict(latitude, longitude, weather)
