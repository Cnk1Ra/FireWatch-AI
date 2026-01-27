"""
FireWatch AI - Constants and Reference Data
Static values used throughout the application.
"""

from typing import Dict, List, Tuple

# =============================================================================
# GEOGRAPHIC BOUNDARIES
# =============================================================================

# Brazil bounding box (west, south, east, north)
BRAZIL_BBOX: Tuple[float, float, float, float] = (-73.98, -33.75, -34.79, 5.27)

# Brazil center coordinates
BRAZIL_CENTER: Tuple[float, float] = (-14.235, -51.925)

# Brazilian states bounding boxes
BRAZILIAN_STATES: Dict[str, Tuple[float, float, float, float]] = {
    "AC": (-73.99, -11.15, -66.63, -7.11),  # Acre
    "AL": (-38.24, -10.50, -35.15, -8.81),  # Alagoas
    "AM": (-73.80, -9.82, -56.10, 2.25),    # Amazonas
    "AP": (-54.88, -1.23, -49.87, 4.44),    # Amapá
    "BA": (-46.62, -18.35, -37.34, -8.53),  # Bahia
    "CE": (-41.42, -7.86, -37.25, -2.78),   # Ceará
    "DF": (-48.29, -16.05, -47.31, -15.50), # Distrito Federal
    "ES": (-41.88, -21.30, -39.68, -17.89), # Espírito Santo
    "GO": (-53.25, -19.50, -45.91, -12.39), # Goiás
    "MA": (-48.76, -10.26, -41.79, -1.05),  # Maranhão
    "MG": (-51.05, -22.92, -39.86, -14.23), # Minas Gerais
    "MS": (-58.17, -24.07, -53.26, -17.17), # Mato Grosso do Sul
    "MT": (-61.63, -18.04, -50.22, -7.35),  # Mato Grosso
    "PA": (-58.90, -9.87, -46.06, 2.59),    # Pará
    "PB": (-38.77, -8.30, -34.79, -6.02),   # Paraíba
    "PE": (-41.36, -9.49, -34.86, -7.15),   # Pernambuco
    "PI": (-45.99, -10.93, -40.37, -2.74),  # Piauí
    "PR": (-54.62, -26.72, -48.02, -22.52), # Paraná
    "RJ": (-44.89, -23.37, -40.96, -20.76), # Rio de Janeiro
    "RN": (-38.58, -6.98, -34.96, -4.83),   # Rio Grande do Norte
    "RO": (-66.62, -13.69, -59.77, -7.97),  # Rondônia
    "RR": (-64.82, 0.63, -58.88, 5.27),     # Roraima
    "RS": (-57.65, -33.75, -49.69, -27.08), # Rio Grande do Sul
    "SC": (-53.84, -29.35, -48.36, -25.95), # Santa Catarina
    "SE": (-38.25, -11.57, -36.39, -9.51),  # Sergipe
    "SP": (-53.11, -25.31, -44.16, -19.78), # São Paulo
    "TO": (-50.73, -13.47, -45.73, -5.17),  # Tocantins
}

# =============================================================================
# BIOME DATA
# =============================================================================

# Brazilian biomes
BRAZILIAN_BIOMES: List[str] = [
    "Amazônia",
    "Mata Atlântica",
    "Cerrado",
    "Caatinga",
    "Pampa",
    "Pantanal",
]

# Biomass content by biome (tons of Carbon per hectare)
BIOME_BIOMASS: Dict[str, Dict[str, float]] = {
    "Amazônia": {"min": 150, "max": 300, "avg": 225},
    "Mata Atlântica": {"min": 100, "max": 200, "avg": 150},
    "Cerrado": {"min": 30, "max": 80, "avg": 55},
    "Caatinga": {"min": 20, "max": 40, "avg": 30},
    "Pampa": {"min": 10, "max": 30, "avg": 20},
    "Pantanal": {"min": 40, "max": 100, "avg": 70},
}

# CO2 conversion factor (Carbon to CO2)
CARBON_TO_CO2_FACTOR: float = 3.67

# Combustion factor by vegetation type
COMBUSTION_FACTORS: Dict[str, float] = {
    "forest": 0.50,
    "savanna": 0.75,
    "grassland": 0.90,
    "shrubland": 0.70,
    "wetland": 0.40,
}

# =============================================================================
# VEGETATION FUEL FACTORS (for fire spread calculation)
# =============================================================================

VEGETATION_FUEL_FACTORS: Dict[str, Dict[str, float]] = {
    "floresta_densa": {
        "fuel_load_kg_m2": 2.5,
        "fuel_depth_m": 0.5,
        "moisture_extinction": 30,
        "spread_rate_factor": 0.6,
    },
    "floresta_aberta": {
        "fuel_load_kg_m2": 1.8,
        "fuel_depth_m": 0.4,
        "moisture_extinction": 25,
        "spread_rate_factor": 0.8,
    },
    "cerrado_tipico": {
        "fuel_load_kg_m2": 0.8,
        "fuel_depth_m": 0.6,
        "moisture_extinction": 20,
        "spread_rate_factor": 1.2,
    },
    "cerrado_campo": {
        "fuel_load_kg_m2": 0.5,
        "fuel_depth_m": 0.8,
        "moisture_extinction": 15,
        "spread_rate_factor": 1.5,
    },
    "caatinga": {
        "fuel_load_kg_m2": 0.4,
        "fuel_depth_m": 0.3,
        "moisture_extinction": 12,
        "spread_rate_factor": 1.0,
    },
    "pastagem": {
        "fuel_load_kg_m2": 0.3,
        "fuel_depth_m": 0.4,
        "moisture_extinction": 15,
        "spread_rate_factor": 1.8,
    },
    "agricultura": {
        "fuel_load_kg_m2": 0.6,
        "fuel_depth_m": 0.5,
        "moisture_extinction": 20,
        "spread_rate_factor": 1.3,
    },
}

# =============================================================================
# FIRE DETECTION
# =============================================================================

# Confidence levels mapping
CONFIDENCE_LEVELS: Dict[str, str] = {
    "h": "high",
    "high": "high",
    "n": "nominal",
    "nominal": "nominal",
    "l": "low",
    "low": "low",
}

# FRP (Fire Radiative Power) classification (MW)
FRP_CLASSIFICATION: Dict[str, Tuple[float, float]] = {
    "low": (0, 10),
    "moderate": (10, 50),
    "high": (50, 100),
    "extreme": (100, float("inf")),
}

# Minimum FRP threshold for significant fire
MIN_SIGNIFICANT_FRP: float = 5.0

# =============================================================================
# WEATHER THRESHOLDS
# =============================================================================

# Fire danger index thresholds
FIRE_DANGER_THRESHOLDS: Dict[str, Dict[str, float]] = {
    "temperature_celsius": {"low": 25, "moderate": 30, "high": 35, "extreme": 40},
    "humidity_percent": {"low": 60, "moderate": 40, "high": 25, "extreme": 15},
    "wind_speed_kmh": {"low": 10, "moderate": 20, "high": 35, "extreme": 50},
    "days_without_rain": {"low": 3, "moderate": 7, "high": 15, "extreme": 30},
}

# =============================================================================
# CLUSTERING AND ANALYSIS
# =============================================================================

# Default clustering distance (km)
DEFAULT_CLUSTERING_DISTANCE_KM: float = 5.0

# Minimum hotspots to form a cluster
MIN_CLUSTER_SIZE: int = 3

# Maximum time difference for temporal clustering (hours)
MAX_TEMPORAL_CLUSTER_HOURS: int = 6

# =============================================================================
# API RATE LIMITS
# =============================================================================

API_RATE_LIMITS: Dict[str, Dict[str, int]] = {
    "nasa_firms": {"requests": 5000, "period_minutes": 10},
    "open_meteo": {"requests": 10000, "period_minutes": 60},
    "openstreetmap": {"requests": 1, "period_seconds": 1},
    "nominatim": {"requests": 1, "period_seconds": 1},
}

# =============================================================================
# DATA SOURCES
# =============================================================================

DATA_SOURCES: Dict[str, Dict[str, str]] = {
    "nasa_firms": {
        "name": "NASA FIRMS",
        "url": "https://firms.modaps.eosdis.nasa.gov",
        "delay": "3 hours",
        "cost": "Free",
    },
    "open_meteo": {
        "name": "Open-Meteo",
        "url": "https://open-meteo.com",
        "delay": "15 minutes",
        "cost": "Free",
    },
    "sentinel_hub": {
        "name": "Sentinel Hub",
        "url": "https://scihub.copernicus.eu",
        "delay": "5-7 days",
        "cost": "Free tier available",
    },
    "mapbiomas": {
        "name": "MapBiomas",
        "url": "https://mapbiomas.org",
        "delay": "Annual updates",
        "cost": "Free",
    },
}
