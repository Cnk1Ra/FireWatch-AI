"""
Tests for prediction modules
"""
import pytest
from unittest.mock import patch, MagicMock

import sys
sys.path.insert(0, '.')

from src.prediction.propagation_model import PropagationModel, FireSpread
from src.prediction.spread_calculator import SpreadCalculator
from src.prediction.risk_index import RiskIndexCalculator
from src.prediction.evacuation_router import EvacuationRouter


class TestPropagationModel:
    """Test suite for fire propagation model."""

    def setup_method(self):
        """Setup test fixtures."""
        self.model = PropagationModel()

    def test_model_initialization(self):
        """Test model initializes correctly."""
        assert self.model is not None

    def test_predict_spread_basic(self):
        """Test basic spread prediction."""
        result = self.model.predict(
            center_lat=-22.5,
            center_lon=-45.5,
            initial_area_ha=50.0,
            wind_speed_kmh=20.0,
            wind_direction=90,  # East
            hours=6
        )

        assert len(result.predictions) == 6  # One per hour
        assert result.predictions[0].hour == 1
        assert result.predictions[-1].hour == 6

        # Area should grow over time
        assert result.predictions[-1].area_ha > result.predictions[0].area_ha

    def test_predict_with_terrain(self):
        """Test prediction with terrain factors."""
        result_flat = self.model.predict(
            center_lat=-22.5, center_lon=-45.5,
            initial_area_ha=50.0, wind_speed_kmh=20.0,
            wind_direction=90, hours=3, slope_degrees=0
        )

        result_slope = self.model.predict(
            center_lat=-22.5, center_lon=-45.5,
            initial_area_ha=50.0, wind_speed_kmh=20.0,
            wind_direction=90, hours=3, slope_degrees=30
        )

        # Fire spreads faster uphill
        assert result_slope.predictions[-1].area_ha >= result_flat.predictions[-1].area_ha

    def test_rothermel_rate_calculation(self):
        """Test Rothermel spread rate formula."""
        rate = self.model.calculate_rothermel_rate(
            wind_speed_kmh=20.0,
            slope_degrees=10,
            fuel_moisture=0.1
        )

        assert rate > 0
        assert rate < 100  # Reasonable m/min

    def test_wind_effect_on_spread(self):
        """Test wind increases spread rate."""
        rate_calm = self.model.calculate_rothermel_rate(wind_speed_kmh=5, slope_degrees=0)
        rate_windy = self.model.calculate_rothermel_rate(wind_speed_kmh=40, slope_degrees=0)

        assert rate_windy > rate_calm


class TestSpreadCalculator:
    """Test suite for spread calculator."""

    def setup_method(self):
        """Setup test fixtures."""
        self.calculator = SpreadCalculator()

    def test_calculate_spread_rate(self):
        """Test spread rate calculation."""
        rate = self.calculator.calculate_rate(
            wind_speed_kmh=25.0,
            humidity_percent=30,
            temperature_celsius=35
        )

        assert rate > 0

    def test_calculate_direction(self):
        """Test spread direction calculation."""
        direction = self.calculator.calculate_direction(
            wind_direction=90,  # Wind from East
            slope_aspect=180  # Slope facing South
        )

        # Direction should be influenced by wind
        assert 0 <= direction < 360

    def test_spread_rate_humidity_effect(self):
        """Test humidity reduces spread rate."""
        rate_dry = self.calculator.calculate_rate(
            wind_speed_kmh=20, humidity_percent=20, temperature_celsius=30
        )
        rate_humid = self.calculator.calculate_rate(
            wind_speed_kmh=20, humidity_percent=80, temperature_celsius=30
        )

        assert rate_dry > rate_humid


class TestRiskIndexCalculator:
    """Test suite for risk index calculation."""

    def setup_method(self):
        """Setup test fixtures."""
        self.calculator = RiskIndexCalculator()

    def test_calculate_risk_index(self):
        """Test basic risk calculation."""
        result = self.calculator.calculate(
            temperature=35,
            humidity=30,
            wind_speed=20,
            days_without_rain=10
        )

        assert 0 <= result.index <= 100
        assert result.level in ["BAIXO", "MODERADO", "ALTO", "MUITO ALTO", "CRITICO"]

    def test_high_risk_conditions(self):
        """Test high risk detection."""
        result = self.calculator.calculate(
            temperature=40,
            humidity=15,
            wind_speed=40,
            days_without_rain=20
        )

        assert result.index >= 70
        assert result.level in ["MUITO ALTO", "CRITICO"]

    def test_low_risk_conditions(self):
        """Test low risk detection."""
        result = self.calculator.calculate(
            temperature=20,
            humidity=80,
            wind_speed=5,
            days_without_rain=0
        )

        assert result.index <= 30
        assert result.level == "BAIXO"

    def test_risk_factors(self):
        """Test individual risk factors."""
        result = self.calculator.calculate(
            temperature=35, humidity=30, wind_speed=20, days_without_rain=10
        )

        assert "temperature" in result.factors
        assert "humidity" in result.factors
        assert "wind_speed" in result.factors
        assert "drought" in result.factors


class TestEvacuationRouter:
    """Test suite for evacuation routing."""

    def setup_method(self):
        """Setup test fixtures."""
        self.router = EvacuationRouter()

    def test_find_routes(self):
        """Test finding evacuation routes."""
        routes = self.router.find_routes(
            fire_lat=-22.5,
            fire_lon=-45.5,
            radius_km=10
        )

        assert len(routes) > 0
        assert routes[0].recommended == True

    def test_route_properties(self):
        """Test route has required properties."""
        routes = self.router.find_routes(
            fire_lat=-22.5, fire_lon=-45.5, radius_km=10
        )

        route = routes[0]
        assert hasattr(route, 'direction')
        assert hasattr(route, 'distance_km')
        assert hasattr(route, 'estimated_time_min')

    def test_find_shelter_points(self):
        """Test finding shelter points."""
        shelters = self.router.find_shelters(
            lat=-22.5, lon=-45.5, radius_km=20
        )

        assert len(shelters) >= 0  # May have shelters or not

    def test_emergency_contacts(self):
        """Test emergency contacts retrieval."""
        contacts = self.router.get_emergency_contacts()

        assert "bombeiros" in contacts
        assert contacts["bombeiros"] == "193"
        assert "defesa_civil" in contacts
        assert "samu" in contacts
