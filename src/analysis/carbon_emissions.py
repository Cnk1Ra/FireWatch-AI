"""
FireWatch AI - Carbon Emissions Calculator
Estimates greenhouse gas emissions from wildfires.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Any, Optional

from src.ingestion.mapbiomas_client import MapBiomasClient


# Emission factors by gas (kg per ton of biomass burned)
EMISSION_FACTORS: Dict[str, float] = {
    "co2": 1613,    # kg CO2 per ton dry matter
    "co": 107,      # kg CO per ton dry matter
    "ch4": 4.7,     # kg CH4 per ton dry matter
    "n2o": 0.26,    # kg N2O per ton dry matter
    "nox": 3.9,     # kg NOx per ton dry matter
    "pm25": 9.7,    # kg PM2.5 per ton dry matter
    "pm10": 12.4,   # kg PM10 per ton dry matter
}

# Global Warming Potential (100-year, IPCC AR5)
GWP: Dict[str, float] = {
    "co2": 1,
    "ch4": 28,
    "n2o": 265,
}

# Biomass content by biome (tons dry matter per hectare)
BIOMASS_BY_BIOME: Dict[str, Dict[str, float]] = {
    "Amazônia": {"above_ground": 300, "below_ground": 60, "litter": 15},
    "Mata Atlântica": {"above_ground": 200, "below_ground": 40, "litter": 12},
    "Cerrado": {"above_ground": 40, "below_ground": 30, "litter": 5},
    "Caatinga": {"above_ground": 25, "below_ground": 15, "litter": 3},
    "Pampa": {"above_ground": 10, "below_ground": 20, "litter": 2},
    "Pantanal": {"above_ground": 60, "below_ground": 25, "litter": 8},
}

# Combustion completeness by vegetation type (fraction burned)
COMBUSTION_COMPLETENESS: Dict[str, Dict[str, float]] = {
    "forest": {"above_ground": 0.40, "below_ground": 0.05, "litter": 0.90},
    "savanna": {"above_ground": 0.65, "below_ground": 0.10, "litter": 0.95},
    "grassland": {"above_ground": 0.85, "below_ground": 0.15, "litter": 0.98},
}


@dataclass
class CarbonEmissions:
    """Estimated carbon and GHG emissions from a fire."""
    fire_id: str
    calculation_timestamp: datetime
    area_hectares: float
    biome: str

    # Biomass
    total_biomass_tons: float
    biomass_burned_tons: float

    # Emissions by gas (tons)
    co2_tons: float
    co_tons: float
    ch4_tons: float
    n2o_tons: float
    nox_tons: float
    pm25_tons: float
    pm10_tons: float

    # CO2 equivalent
    co2_equivalent_tons: float

    # Carbon metrics
    carbon_released_tons: float
    carbon_stock_before_tons: float

    @property
    def emissions_per_hectare(self) -> Dict[str, float]:
        """Calculate emissions per hectare."""
        if self.area_hectares <= 0:
            return {}
        return {
            "co2_tons": self.co2_tons / self.area_hectares,
            "co2e_tons": self.co2_equivalent_tons / self.area_hectares,
            "pm25_kg": (self.pm25_tons * 1000) / self.area_hectares,
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "fire_id": self.fire_id,
            "calculation_timestamp": self.calculation_timestamp.isoformat(),
            "area_hectares": round(self.area_hectares, 2),
            "biome": self.biome,
            "biomass": {
                "total_tons": round(self.total_biomass_tons, 2),
                "burned_tons": round(self.biomass_burned_tons, 2),
                "combustion_percentage": round(
                    (self.biomass_burned_tons / self.total_biomass_tons * 100)
                    if self.total_biomass_tons > 0 else 0, 1
                ),
            },
            "emissions_tons": {
                "co2": round(self.co2_tons, 2),
                "co": round(self.co_tons, 2),
                "ch4": round(self.ch4_tons, 3),
                "n2o": round(self.n2o_tons, 4),
                "nox": round(self.nox_tons, 3),
                "pm25": round(self.pm25_tons, 3),
                "pm10": round(self.pm10_tons, 3),
            },
            "co2_equivalent_tons": round(self.co2_equivalent_tons, 2),
            "carbon": {
                "stock_before_tons": round(self.carbon_stock_before_tons, 2),
                "released_tons": round(self.carbon_released_tons, 2),
                "release_percentage": round(
                    (self.carbon_released_tons / self.carbon_stock_before_tons * 100)
                    if self.carbon_stock_before_tons > 0 else 0, 1
                ),
            },
            "emissions_per_hectare": {
                k: round(v, 3) for k, v in self.emissions_per_hectare.items()
            },
        }

    def get_equivalents(self) -> Dict[str, int]:
        """Get relatable equivalents for emissions."""
        return calculate_equivalents(self.co2_equivalent_tons)


def calculate_emissions(
    latitude: float,
    longitude: float,
    area_hectares: float,
    fire_id: str = "FIRE-001"
) -> CarbonEmissions:
    """
    Calculate greenhouse gas emissions from a fire.

    Args:
        latitude: Fire center latitude
        longitude: Fire center longitude
        area_hectares: Burned area in hectares
        fire_id: Fire identifier

    Returns:
        CarbonEmissions object
    """
    # Get biome information
    client = MapBiomasClient()
    vegetation = client.get_vegetation_data(latitude, longitude)
    biome = vegetation.biome

    # Get biomass values for biome
    biomass_data = BIOMASS_BY_BIOME.get(biome, BIOMASS_BY_BIOME["Cerrado"])

    # Determine vegetation type for combustion completeness
    if biome in ["Amazônia", "Mata Atlântica"]:
        veg_type = "forest"
    elif biome in ["Cerrado", "Caatinga"]:
        veg_type = "savanna"
    else:
        veg_type = "grassland"

    combustion = COMBUSTION_COMPLETENESS[veg_type]

    # Calculate total biomass
    total_above = biomass_data["above_ground"] * area_hectares
    total_below = biomass_data["below_ground"] * area_hectares
    total_litter = biomass_data["litter"] * area_hectares
    total_biomass = total_above + total_below + total_litter

    # Calculate burned biomass
    burned_above = total_above * combustion["above_ground"]
    burned_below = total_below * combustion["below_ground"]
    burned_litter = total_litter * combustion["litter"]
    biomass_burned = burned_above + burned_below + burned_litter

    # Calculate emissions for each gas
    co2_tons = (biomass_burned * EMISSION_FACTORS["co2"]) / 1000
    co_tons = (biomass_burned * EMISSION_FACTORS["co"]) / 1000
    ch4_tons = (biomass_burned * EMISSION_FACTORS["ch4"]) / 1000
    n2o_tons = (biomass_burned * EMISSION_FACTORS["n2o"]) / 1000
    nox_tons = (biomass_burned * EMISSION_FACTORS["nox"]) / 1000
    pm25_tons = (biomass_burned * EMISSION_FACTORS["pm25"]) / 1000
    pm10_tons = (biomass_burned * EMISSION_FACTORS["pm10"]) / 1000

    # Calculate CO2 equivalent (using GWP)
    co2e = co2_tons + (ch4_tons * GWP["ch4"]) + (n2o_tons * GWP["n2o"])

    # Calculate carbon metrics
    # Biomass is approximately 47% carbon
    carbon_stock = total_biomass * 0.47
    carbon_released = biomass_burned * 0.47

    return CarbonEmissions(
        fire_id=fire_id,
        calculation_timestamp=datetime.now(),
        area_hectares=area_hectares,
        biome=biome,
        total_biomass_tons=total_biomass,
        biomass_burned_tons=biomass_burned,
        co2_tons=co2_tons,
        co_tons=co_tons,
        ch4_tons=ch4_tons,
        n2o_tons=n2o_tons,
        nox_tons=nox_tons,
        pm25_tons=pm25_tons,
        pm10_tons=pm10_tons,
        co2_equivalent_tons=co2e,
        carbon_released_tons=carbon_released,
        carbon_stock_before_tons=carbon_stock,
    )


def estimate_co2_from_fire(
    area_hectares: float,
    biome: str = "Cerrado"
) -> float:
    """
    Quick estimate of CO2 emissions from fire area.

    Args:
        area_hectares: Burned area in hectares
        biome: Brazilian biome name

    Returns:
        Estimated CO2 emissions in tons
    """
    biomass_data = BIOMASS_BY_BIOME.get(biome, BIOMASS_BY_BIOME["Cerrado"])

    # Average combustion completeness
    avg_combustion = 0.5

    # Total above-ground biomass burned
    biomass_burned = biomass_data["above_ground"] * area_hectares * avg_combustion

    # CO2 emissions
    return (biomass_burned * EMISSION_FACTORS["co2"]) / 1000


def calculate_equivalents(co2e_tons: float) -> Dict[str, int]:
    """
    Convert CO2 equivalent emissions to relatable metrics.

    Args:
        co2e_tons: CO2 equivalent emissions in tons

    Returns:
        Dictionary with various equivalents
    """
    # Reference values
    CAR_ANNUAL = 4.6       # tons CO2e per car per year (average)
    FLIGHT_SP_NY = 2.0     # tons CO2e per passenger (round trip São Paulo-NYC)
    HOUSEHOLD = 3.2        # tons CO2e per household energy use per year
    TREE_ANNUAL = 0.022    # tons CO2 sequestered per tree per year
    GASOLINE_LITER = 0.0023  # tons CO2 per liter of gasoline

    return {
        "cars_one_year": int(co2e_tons / CAR_ANNUAL),
        "flights_sp_new_york": int(co2e_tons / FLIGHT_SP_NY),
        "households_one_year": int(co2e_tons / HOUSEHOLD),
        "trees_to_offset_one_year": int(co2e_tons / TREE_ANNUAL),
        "liters_gasoline": int(co2e_tons / GASOLINE_LITER),
    }


def calculate_air_quality_impact(
    pm25_tons: float,
    area_km2: float
) -> Dict[str, Any]:
    """
    Estimate air quality impact from particulate emissions.

    Args:
        pm25_tons: PM2.5 emissions in tons
        area_km2: Affected area in square kilometers

    Returns:
        Dictionary with air quality metrics
    """
    # Convert to micrograms and estimate concentration
    # Assuming emissions disperse over an airshed
    airshed_volume_m3 = area_km2 * 1e6 * 1000  # 1km mixing height
    pm25_ug = pm25_tons * 1e12  # tons to micrograms

    # Very rough concentration estimate
    concentration_ug_m3 = pm25_ug / airshed_volume_m3

    # Air Quality Index classification (US EPA)
    if concentration_ug_m3 <= 12:
        aqi_category = "Good"
        health_concern = "Air quality is satisfactory"
    elif concentration_ug_m3 <= 35.4:
        aqi_category = "Moderate"
        health_concern = "Sensitive groups may experience effects"
    elif concentration_ug_m3 <= 55.4:
        aqi_category = "Unhealthy for Sensitive Groups"
        health_concern = "Sensitive groups should reduce outdoor activities"
    elif concentration_ug_m3 <= 150.4:
        aqi_category = "Unhealthy"
        health_concern = "Everyone may experience health effects"
    elif concentration_ug_m3 <= 250.4:
        aqi_category = "Very Unhealthy"
        health_concern = "Health alert: significant risk"
    else:
        aqi_category = "Hazardous"
        health_concern = "Emergency conditions"

    return {
        "estimated_pm25_concentration_ug_m3": round(concentration_ug_m3, 1),
        "aqi_category": aqi_category,
        "health_concern": health_concern,
        "recommendations": _get_health_recommendations(aqi_category),
    }


def _get_health_recommendations(aqi_category: str) -> list:
    """Get health recommendations based on AQI category."""
    recommendations = {
        "Good": [
            "Air quality is good, enjoy outdoor activities"
        ],
        "Moderate": [
            "Sensitive individuals should consider limiting prolonged outdoor exposure"
        ],
        "Unhealthy for Sensitive Groups": [
            "Children, elderly, and those with respiratory conditions should limit outdoor activities",
            "Keep windows closed",
            "Consider using air purifiers indoors"
        ],
        "Unhealthy": [
            "Everyone should reduce prolonged outdoor activities",
            "Keep windows and doors closed",
            "Use air purifiers if available",
            "Wear N95 masks if going outside is necessary"
        ],
        "Very Unhealthy": [
            "Avoid all outdoor activities",
            "Stay indoors with windows closed",
            "Use air purifiers",
            "Seek medical attention if experiencing symptoms"
        ],
        "Hazardous": [
            "Stay indoors",
            "Evacuate if possible",
            "Seal doors and windows",
            "Seek medical attention immediately if experiencing symptoms",
            "Follow local emergency guidelines"
        ],
    }
    return recommendations.get(aqi_category, [])
