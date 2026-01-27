"""
Pytest configuration and fixtures
"""
import pytest
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


@pytest.fixture
def sample_hotspots():
    """Sample hotspot data for testing."""
    return [
        {
            "latitude": -22.5,
            "longitude": -45.5,
            "brightness": 350.5,
            "frp": 50.0,
            "confidence": "nominal",
            "acq_datetime": "2026-01-27 14:30",
            "satellite": "NOAA-20",
            "daynight": "D"
        },
        {
            "latitude": -22.51,
            "longitude": -45.51,
            "brightness": 320.0,
            "frp": 30.0,
            "confidence": "high",
            "acq_datetime": "2026-01-27 14:35",
            "satellite": "NOAA-20",
            "daynight": "D"
        },
        {
            "latitude": -23.5,
            "longitude": -46.5,
            "brightness": 400.0,
            "frp": 75.0,
            "confidence": "nominal",
            "acq_datetime": "2026-01-27 14:40",
            "satellite": "NOAA-20",
            "daynight": "D"
        }
    ]


@pytest.fixture
def sample_weather():
    """Sample weather data for testing."""
    return {
        "temperature": 32.5,
        "humidity": 35,
        "wind_speed": 20.0,
        "wind_direction": 90,
        "precipitation": 0
    }


@pytest.fixture
def sample_cluster():
    """Sample cluster data for testing."""
    return {
        "id": 1,
        "center_lat": -22.5,
        "center_lon": -45.5,
        "count": 10,
        "total_frp": 250.0,
        "avg_frp": 25.0,
        "max_frp": 75.0,
        "estimated_area_ha": 89.5,
        "state": "Sao Paulo",
        "biome": "Mata Atlantica"
    }


@pytest.fixture
def brazil_bounds():
    """Brazil bounding box."""
    return {
        "west": -74,
        "south": -34,
        "east": -34,
        "north": 5
    }


@pytest.fixture
def sao_paulo_bounds():
    """Sao Paulo state bounding box."""
    return {
        "west": -54,
        "south": -26,
        "east": -44,
        "north": -19.5
    }


@pytest.fixture
def biome_data():
    """Biome configuration data."""
    return {
        "Amazonia": {
            "carbon_tons_ha": 225,
            "recovery_years": 50,
            "spread_factor": 0.6
        },
        "Cerrado": {
            "carbon_tons_ha": 55,
            "recovery_years": 15,
            "spread_factor": 1.2
        },
        "Pantanal": {
            "carbon_tons_ha": 70,
            "recovery_years": 10,
            "spread_factor": 0.4
        },
        "Mata Atlantica": {
            "carbon_tons_ha": 150,
            "recovery_years": 40,
            "spread_factor": 0.8
        },
        "Caatinga": {
            "carbon_tons_ha": 30,
            "recovery_years": 20,
            "spread_factor": 1.0
        },
        "Pampa": {
            "carbon_tons_ha": 20,
            "recovery_years": 5,
            "spread_factor": 1.5
        }
    }
