"""
FireWatch AI - Biome Impact Analysis
Analyzes environmental impact of fires on different biomes.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Any, Optional

from src.ingestion.mapbiomas_client import (
    MapBiomasClient,
    BIOME_BOUNDARIES,
    FUEL_CHARACTERISTICS,
)


@dataclass
class VegetationType:
    """Information about a vegetation type affected by fire."""
    name: str
    area_hectares: float
    percentage: float
    biomass_ton_per_ha: float
    carbon_stock_tons: float
    conservation_status: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "area_hectares": round(self.area_hectares, 2),
            "percentage": round(self.percentage, 2),
            "biomass_ton_per_ha": round(self.biomass_ton_per_ha, 2),
            "carbon_stock_tons": round(self.carbon_stock_tons, 2),
            "conservation_status": self.conservation_status,
        }


@dataclass
class BiomeImpact:
    """Environmental impact assessment for a fire."""
    fire_id: str
    analysis_timestamp: datetime
    center_latitude: float
    center_longitude: float
    primary_biome: str
    total_area_hectares: float
    vegetation_types: List[VegetationType]

    # Carbon and emissions
    total_carbon_stock_tons: float
    estimated_carbon_released_tons: float
    estimated_co2_emissions_tons: float

    # Ecological impact
    recovery_time_years: int
    endemic_species_at_risk: List[str]
    protected_areas_affected: List[Dict[str, Any]]
    conservation_impact_level: str  # minor, moderate, significant, severe

    # Additional metrics
    estimated_trees_affected: int = 0
    water_resources_at_risk: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "fire_id": self.fire_id,
            "analysis_timestamp": self.analysis_timestamp.isoformat(),
            "location": {
                "latitude": self.center_latitude,
                "longitude": self.center_longitude,
            },
            "biome": self.primary_biome,
            "area": {
                "total_hectares": round(self.total_area_hectares, 2),
                "total_km2": round(self.total_area_hectares / 100, 4),
            },
            "vegetation_types": [v.to_dict() for v in self.vegetation_types],
            "carbon_impact": {
                "total_stock_tons": round(self.total_carbon_stock_tons, 2),
                "released_tons": round(self.estimated_carbon_released_tons, 2),
                "co2_emissions_tons": round(self.estimated_co2_emissions_tons, 2),
            },
            "ecological_impact": {
                "recovery_time_years": self.recovery_time_years,
                "endemic_species_at_risk": self.endemic_species_at_risk,
                "protected_areas_affected": self.protected_areas_affected,
                "conservation_impact_level": self.conservation_impact_level,
                "estimated_trees_affected": self.estimated_trees_affected,
                "water_resources_at_risk": self.water_resources_at_risk,
            },
        }


# Biomass content by vegetation type (tons C/ha)
BIOMASS_BY_VEGETATION: Dict[str, float] = {
    "Floresta Densa": 250,
    "Floresta Aberta": 180,
    "Floresta Estacional": 150,
    "Cerrado Típico": 55,
    "Cerrado Campo": 30,
    "Caatinga": 25,
    "Campo Nativo": 15,
    "Área Úmida": 80,
    "Pastagem": 8,
    "Agricultura": 5,
}

# Recovery time by biome (years to full recovery)
RECOVERY_TIMES: Dict[str, int] = {
    "Amazônia": 50,
    "Mata Atlântica": 40,
    "Cerrado": 15,
    "Caatinga": 20,
    "Pampa": 5,
    "Pantanal": 10,
}

# Endemic species by biome
ENDEMIC_SPECIES: Dict[str, List[str]] = {
    "Amazônia": [
        "Castanheira (Bertholletia excelsa)",
        "Seringueira (Hevea brasiliensis)",
        "Mogno (Swietenia macrophylla)",
        "Açaí (Euterpe oleracea)",
        "Cupuaçu (Theobroma grandiflorum)",
    ],
    "Mata Atlântica": [
        "Pau-brasil (Paubrasilia echinata)",
        "Ipê-amarelo (Handroanthus albus)",
        "Peroba-rosa (Aspidosperma polyneuron)",
        "Palmito-juçara (Euterpe edulis)",
        "Araucária (Araucaria angustifolia)",
    ],
    "Cerrado": [
        "Pequi (Caryocar brasiliense)",
        "Buriti (Mauritia flexuosa)",
        "Cagaita (Eugenia dysenterica)",
        "Baru (Dipteryx alata)",
        "Mangaba (Hancornia speciosa)",
    ],
    "Caatinga": [
        "Mandacaru (Cereus jamacaru)",
        "Juazeiro (Ziziphus joazeiro)",
        "Umbuzeiro (Spondias tuberosa)",
        "Catingueira (Poincianella pyramidalis)",
        "Aroeira (Myracrodruon urundeuva)",
    ],
    "Pampa": [
        "Capim-barba-de-bode (Aristida spp.)",
        "Espinilho (Vachellia caven)",
        "Butiá (Butia spp.)",
        "Coronilha (Scutia buxifolia)",
    ],
    "Pantanal": [
        "Carandá (Copernicia alba)",
        "Piúva (Handroanthus impetiginosus)",
        "Paratudo (Tabebuia aurea)",
        "Cambará (Vochysia divergens)",
    ],
}

# Trees per hectare by vegetation type
TREES_PER_HECTARE: Dict[str, int] = {
    "Floresta Densa": 500,
    "Floresta Aberta": 350,
    "Floresta Estacional": 400,
    "Cerrado Típico": 200,
    "Cerrado Campo": 50,
    "Caatinga": 150,
    "Campo Nativo": 10,
    "Área Úmida": 100,
}


def analyze_biome_impact(
    latitude: float,
    longitude: float,
    area_hectares: float,
    fire_id: str = "FIRE-001"
) -> BiomeImpact:
    """
    Analyze environmental impact of a fire.

    Args:
        latitude: Fire center latitude
        longitude: Fire center longitude
        area_hectares: Burned area in hectares
        fire_id: Fire identifier

    Returns:
        BiomeImpact object with comprehensive analysis
    """
    client = MapBiomasClient()
    vegetation = client.get_vegetation_data(latitude, longitude)
    biome = vegetation.biome

    # Determine vegetation type
    veg_type_name = vegetation.land_use_class
    biomass_per_ha = BIOMASS_BY_VEGETATION.get(veg_type_name, 50)

    # Calculate carbon stock and emissions
    total_carbon = area_hectares * biomass_per_ha
    combustion_factor = 0.5  # Approximately 50% of biomass burns
    carbon_released = total_carbon * combustion_factor
    co2_emissions = carbon_released * 3.67  # C to CO2 conversion

    # Create vegetation type info
    veg_type = VegetationType(
        name=veg_type_name,
        area_hectares=area_hectares,
        percentage=100.0,
        biomass_ton_per_ha=biomass_per_ha,
        carbon_stock_tons=total_carbon,
        conservation_status=vegetation.conservation_status,
    )

    # Get recovery time and species at risk
    recovery_years = RECOVERY_TIMES.get(biome, 20)
    species_at_risk = ENDEMIC_SPECIES.get(biome, [])[:5]

    # Estimate trees affected
    trees_per_ha = TREES_PER_HECTARE.get(veg_type_name, 100)
    trees_affected = int(area_hectares * trees_per_ha)

    # Determine conservation impact level
    if area_hectares > 1000 and biome in ["Amazônia", "Mata Atlântica"]:
        impact_level = "severe"
    elif area_hectares > 500 or (area_hectares > 100 and biome in ["Amazônia", "Mata Atlântica"]):
        impact_level = "significant"
    elif area_hectares > 100:
        impact_level = "moderate"
    else:
        impact_level = "minor"

    # Check for protected areas (simplified check)
    protected_areas = _check_protected_areas(latitude, longitude, area_hectares, biome)

    # Check water resources
    water_at_risk = biome in ["Pantanal", "Amazônia"] or veg_type_name == "Área Úmida"

    return BiomeImpact(
        fire_id=fire_id,
        analysis_timestamp=datetime.now(),
        center_latitude=latitude,
        center_longitude=longitude,
        primary_biome=biome,
        total_area_hectares=area_hectares,
        vegetation_types=[veg_type],
        total_carbon_stock_tons=total_carbon,
        estimated_carbon_released_tons=carbon_released,
        estimated_co2_emissions_tons=co2_emissions,
        recovery_time_years=recovery_years,
        endemic_species_at_risk=species_at_risk,
        protected_areas_affected=protected_areas,
        conservation_impact_level=impact_level,
        estimated_trees_affected=trees_affected,
        water_resources_at_risk=water_at_risk,
    )


def _check_protected_areas(
    latitude: float,
    longitude: float,
    area_hectares: float,
    biome: str
) -> List[Dict[str, Any]]:
    """
    Check if fire location intersects with protected areas.
    Simplified implementation - would use actual protected area database in production.
    """
    # Sample protected areas near major biomes
    protected_areas = []

    # Check if in high-conservation biomes
    if biome == "Amazônia":
        protected_areas.append({
            "name": "Reserva Florestal",
            "type": "Reserva Biológica",
            "area_affected_hectares": min(area_hectares * 0.3, 100),
            "protection_level": "strict",
        })
    elif biome == "Mata Atlântica":
        protected_areas.append({
            "name": "Área de Proteção Ambiental",
            "type": "APA",
            "area_affected_hectares": min(area_hectares * 0.2, 50),
            "protection_level": "sustainable_use",
        })
    elif biome == "Pantanal":
        protected_areas.append({
            "name": "Reserva da Biosfera do Pantanal",
            "type": "Reserva da Biosfera",
            "area_affected_hectares": min(area_hectares * 0.5, 200),
            "protection_level": "biosphere_reserve",
        })

    return protected_areas


def get_affected_vegetation(
    latitude: float,
    longitude: float
) -> Dict[str, Any]:
    """
    Get vegetation information for a location.

    Args:
        latitude: Location latitude
        longitude: Location longitude

    Returns:
        Dictionary with vegetation details
    """
    client = MapBiomasClient()
    vegetation = client.get_vegetation_data(latitude, longitude)

    return {
        "biome": vegetation.biome,
        "vegetation_type": vegetation.land_use_class,
        "fuel_type": vegetation.fuel_type,
        "biomass_ton_c_ha": vegetation.biomass_ton_c_ha,
        "conservation_status": vegetation.conservation_status,
        "fire_spread_factor": vegetation.spread_rate_factor,
    }


def calculate_carbon_equivalents(co2_tons: float) -> Dict[str, Any]:
    """
    Convert CO2 emissions to relatable equivalents.

    Args:
        co2_tons: CO2 emissions in tons

    Returns:
        Dictionary with various equivalents
    """
    # Average values for comparison
    CAR_ANNUAL_EMISSIONS = 4.6  # tons CO2 per year (average car)
    FLIGHT_SP_NY = 2.0  # tons CO2 per passenger (round trip)
    HOUSEHOLD_ANNUAL = 3.2  # tons CO2 per household energy use
    TREE_ANNUAL_SEQUESTRATION = 0.022  # tons CO2 per tree per year

    return {
        "cars_annual_emissions": int(co2_tons / CAR_ANNUAL_EMISSIONS),
        "flights_sao_paulo_new_york": int(co2_tons / FLIGHT_SP_NY),
        "households_annual_energy": int(co2_tons / HOUSEHOLD_ANNUAL),
        "trees_needed_to_offset_one_year": int(co2_tons / TREE_ANNUAL_SEQUESTRATION),
    }
