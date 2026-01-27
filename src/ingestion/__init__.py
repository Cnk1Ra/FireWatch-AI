"""
FireWatch AI - Data Ingestion Module
Clients for fetching data from external sources.
"""

from src.ingestion.firms_client import (
    FIRMSClient,
    FireHotspot,
    DataSource,
    get_brazil_hotspots,
)
from src.ingestion.weather_client import (
    WeatherClient,
    CurrentWeather,
    WeatherForecast,
    HourlyForecast,
    get_weather_for_hotspot,
    get_forecast_for_region,
)
from src.ingestion.terrain_client import (
    TerrainClient,
    TerrainData,
    TerrainProfile,
    get_elevation_for_hotspot,
)
from src.ingestion.mapbiomas_client import (
    MapBiomasClient,
    VegetationData,
    BiomeAnalysis,
    get_vegetation_for_hotspot,
)
from src.ingestion.osm_client import (
    OSMClient,
    Road,
    Place,
    EmergencyFacility,
    RoadNetwork,
    get_evacuation_roads,
)

__all__ = [
    # FIRMS
    "FIRMSClient",
    "FireHotspot",
    "DataSource",
    "get_brazil_hotspots",
    # Weather
    "WeatherClient",
    "CurrentWeather",
    "WeatherForecast",
    "HourlyForecast",
    "get_weather_for_hotspot",
    "get_forecast_for_region",
    # Terrain
    "TerrainClient",
    "TerrainData",
    "TerrainProfile",
    "get_elevation_for_hotspot",
    # MapBiomas
    "MapBiomasClient",
    "VegetationData",
    "BiomeAnalysis",
    "get_vegetation_for_hotspot",
    # OSM
    "OSMClient",
    "Road",
    "Place",
    "EmergencyFacility",
    "RoadNetwork",
    "get_evacuation_roads",
]
