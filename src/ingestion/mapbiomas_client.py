"""
FireWatch AI - MapBiomas Client
Provides vegetation and land use classification data for Brazil.
Uses pre-processed static data and classification mappings.
"""

from dataclasses import dataclass
from typing import Dict, Any, List, Optional, Tuple
from enum import IntEnum


class LandUseClass(IntEnum):
    """MapBiomas land use classification codes."""
    # Forest
    FOREST = 3
    NATURAL_FOREST = 1
    FOREST_FORMATION = 3
    SAVANNA_FORMATION = 4
    MANGROVE = 5
    FLOODED_FOREST = 6

    # Non-Forest Natural
    NON_FOREST = 10
    WETLAND = 11
    GRASSLAND = 12
    OTHER_NON_FOREST = 13

    # Farming
    FARMING = 14
    PASTURE = 15
    AGRICULTURE = 18
    TEMPORARY_CROP = 19
    SUGAR_CANE = 20
    MOSAIC = 21
    PERMANENT_CROP = 36
    SOYBEAN = 39
    RICE = 40
    COTTON = 62
    COFFEE = 46

    # Non-Vegetated
    NON_VEGETATED = 22
    BEACH_DUNE = 23
    URBAN = 24
    MINING = 30
    OTHER_NON_VEGETATED = 25

    # Water
    WATER = 26
    RIVER_LAKE = 33
    AQUACULTURE = 31

    # Not Observed
    NOT_OBSERVED = 27


# Mapping of land use classes to biomes
LAND_USE_TO_BIOME: Dict[int, str] = {
    1: "Floresta",
    3: "Floresta",
    4: "Cerrado",
    5: "Manguezal",
    6: "Floresta Alagada",
    11: "Área Úmida",
    12: "Campo",
    15: "Pastagem",
    18: "Agricultura",
    19: "Agricultura",
    20: "Cana-de-Açúcar",
    21: "Mosaico",
    24: "Área Urbana",
    26: "Água",
}

# Fuel characteristics by land use type
FUEL_CHARACTERISTICS: Dict[str, Dict[str, Any]] = {
    "floresta_densa": {
        "classes": [1, 3, 5, 6],
        "fuel_load_ton_ha": 25.0,
        "fuel_depth_m": 0.5,
        "moisture_content": 0.20,
        "spread_rate_factor": 0.6,
        "flame_length_factor": 1.2,
        "description": "Dense forest with high canopy closure",
    },
    "floresta_aberta": {
        "classes": [4],
        "fuel_load_ton_ha": 15.0,
        "fuel_depth_m": 0.4,
        "moisture_content": 0.15,
        "spread_rate_factor": 0.8,
        "flame_length_factor": 1.0,
        "description": "Open woodland or savanna forest",
    },
    "cerrado": {
        "classes": [4, 12],
        "fuel_load_ton_ha": 8.0,
        "fuel_depth_m": 0.6,
        "moisture_content": 0.10,
        "spread_rate_factor": 1.2,
        "flame_length_factor": 0.8,
        "description": "Brazilian savanna with mixed grass and shrubs",
    },
    "campo": {
        "classes": [12, 13],
        "fuel_load_ton_ha": 4.0,
        "fuel_depth_m": 0.8,
        "moisture_content": 0.08,
        "spread_rate_factor": 1.5,
        "flame_length_factor": 0.6,
        "description": "Grassland and open fields",
    },
    "pastagem": {
        "classes": [15],
        "fuel_load_ton_ha": 3.0,
        "fuel_depth_m": 0.4,
        "moisture_content": 0.10,
        "spread_rate_factor": 1.8,
        "flame_length_factor": 0.5,
        "description": "Pasture for cattle",
    },
    "agricultura": {
        "classes": [18, 19, 20, 21, 36, 39, 40, 46, 62],
        "fuel_load_ton_ha": 6.0,
        "fuel_depth_m": 0.5,
        "moisture_content": 0.12,
        "spread_rate_factor": 1.3,
        "flame_length_factor": 0.7,
        "description": "Agricultural areas",
    },
    "area_umida": {
        "classes": [11, 6],
        "fuel_load_ton_ha": 10.0,
        "fuel_depth_m": 0.3,
        "moisture_content": 0.40,
        "spread_rate_factor": 0.3,
        "flame_length_factor": 0.4,
        "description": "Wetlands and flooded areas",
    },
    "urbano": {
        "classes": [24, 30],
        "fuel_load_ton_ha": 0.5,
        "fuel_depth_m": 0.1,
        "moisture_content": 0.05,
        "spread_rate_factor": 0.1,
        "flame_length_factor": 0.2,
        "description": "Urban and built-up areas",
    },
}

# Brazilian biomes boundaries (simplified polygons)
BIOME_BOUNDARIES: Dict[str, Dict[str, Any]] = {
    "Amazônia": {
        "center": (-3.4653, -62.2159),
        "approximate_bounds": (-9.0, -73.0, 5.0, -44.0),
        "area_km2": 4196943,
        "states": ["AM", "PA", "MT", "AC", "RO", "RR", "AP", "TO", "MA"],
    },
    "Cerrado": {
        "center": (-15.7801, -47.9292),
        "approximate_bounds": (-24.0, -60.0, -2.0, -41.0),
        "area_km2": 2036448,
        "states": ["GO", "TO", "MT", "MS", "MG", "BA", "PI", "MA", "DF"],
    },
    "Mata Atlântica": {
        "center": (-23.5505, -46.6333),
        "approximate_bounds": (-30.0, -55.0, -3.0, -35.0),
        "area_km2": 1110182,
        "states": ["SP", "RJ", "MG", "ES", "PR", "SC", "RS", "BA", "SE", "AL", "PE", "PB", "RN"],
    },
    "Caatinga": {
        "center": (-9.0, -40.0),
        "approximate_bounds": (-17.0, -45.0, -3.0, -35.0),
        "area_km2": 844453,
        "states": ["BA", "PE", "PI", "CE", "RN", "PB", "SE", "AL", "MG"],
    },
    "Pampa": {
        "center": (-30.0, -54.0),
        "approximate_bounds": (-34.0, -58.0, -28.0, -50.0),
        "area_km2": 176496,
        "states": ["RS"],
    },
    "Pantanal": {
        "center": (-19.0, -57.0),
        "approximate_bounds": (-22.0, -59.0, -16.0, -55.0),
        "area_km2": 150355,
        "states": ["MT", "MS"],
    },
}


@dataclass
class VegetationData:
    """Vegetation and land use information for a location."""
    latitude: float
    longitude: float
    biome: str
    land_use_class: str
    land_use_code: int
    fuel_type: str
    fuel_load_ton_ha: float
    fuel_depth_m: float
    moisture_content: float
    spread_rate_factor: float
    biomass_ton_c_ha: float  # Tons of carbon per hectare
    conservation_status: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "latitude": self.latitude,
            "longitude": self.longitude,
            "biome": self.biome,
            "land_use_class": self.land_use_class,
            "land_use_code": self.land_use_code,
            "fuel_type": self.fuel_type,
            "fuel_load_ton_ha": self.fuel_load_ton_ha,
            "fuel_depth_m": self.fuel_depth_m,
            "moisture_content": self.moisture_content,
            "spread_rate_factor": self.spread_rate_factor,
            "biomass_ton_c_ha": self.biomass_ton_c_ha,
            "conservation_status": self.conservation_status,
        }


@dataclass
class BiomeAnalysis:
    """Analysis of fire impact on a biome."""
    biome: str
    total_area_affected_ha: float
    vegetation_types: List[Dict[str, Any]]
    estimated_biomass_lost_ton: float
    estimated_co2_emissions_ton: float
    recovery_time_years: int
    endemic_species_at_risk: List[str]
    conservation_impact: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "biome": self.biome,
            "total_area_affected_ha": self.total_area_affected_ha,
            "vegetation_types": self.vegetation_types,
            "estimated_biomass_lost_ton": self.estimated_biomass_lost_ton,
            "estimated_co2_emissions_ton": self.estimated_co2_emissions_ton,
            "recovery_time_years": self.recovery_time_years,
            "endemic_species_at_risk": self.endemic_species_at_risk,
            "conservation_impact": self.conservation_impact,
        }


class MapBiomasClient:
    """
    Client for vegetation and biome data.
    Uses static data and heuristics since MapBiomas doesn't have a public API.
    """

    # Biomass estimates by biome (tons C/ha)
    BIOMASS_BY_BIOME: Dict[str, Dict[str, float]] = {
        "Amazônia": {"min": 150, "avg": 225, "max": 300},
        "Mata Atlântica": {"min": 100, "avg": 150, "max": 200},
        "Cerrado": {"min": 30, "avg": 55, "max": 80},
        "Caatinga": {"min": 20, "avg": 30, "max": 40},
        "Pampa": {"min": 10, "avg": 20, "max": 30},
        "Pantanal": {"min": 40, "avg": 70, "max": 100},
    }

    # Recovery time by biome (years)
    RECOVERY_TIME: Dict[str, int] = {
        "Amazônia": 50,
        "Mata Atlântica": 40,
        "Cerrado": 15,
        "Caatinga": 20,
        "Pampa": 5,
        "Pantanal": 10,
    }

    # Endemic species by biome (sample list)
    ENDEMIC_SPECIES: Dict[str, List[str]] = {
        "Amazônia": [
            "Castanheira", "Seringueira", "Mogno", "Vitória-régia",
            "Açaí", "Cupuaçu", "Guaraná", "Andiroba"
        ],
        "Mata Atlântica": [
            "Pau-brasil", "Ipê-amarelo", "Peroba-rosa", "Jequitibá",
            "Jacarandá", "Cedro", "Palmito-juçara", "Araucária"
        ],
        "Cerrado": [
            "Pequi", "Buriti", "Cagaita", "Mangaba",
            "Baru", "Jatobá", "Ipê-do-cerrado", "Lobeira"
        ],
        "Caatinga": [
            "Mandacaru", "Xique-xique", "Juazeiro", "Umbuzeiro",
            "Catingueira", "Aroeira", "Baraúna", "Imburana"
        ],
        "Pampa": [
            "Capim-barba-de-bode", "Algarrobo", "Espinilho",
            "Coronilha", "Butiá", "Timbó"
        ],
        "Pantanal": [
            "Carandá", "Acuri", "Piúva", "Paratudo",
            "Cambará", "Embaúba", "Tarumã"
        ],
    }

    def __init__(self):
        """Initialize the MapBiomas client."""
        pass

    def identify_biome(
        self,
        latitude: float,
        longitude: float
    ) -> str:
        """
        Identify the biome for a given location using approximate boundaries.

        Args:
            latitude: Location latitude
            longitude: Location longitude

        Returns:
            Biome name
        """
        # Check each biome's approximate bounds
        for biome, info in BIOME_BOUNDARIES.items():
            bounds = info["approximate_bounds"]
            south, west, north, east = bounds

            if south <= latitude <= north and west <= longitude <= east:
                # Additional distance check from center
                center = info["center"]
                # Simple heuristic - could be improved with actual boundaries
                return biome

        # Default to Cerrado if no match (largest biome in central Brazil)
        return "Cerrado"

    def get_vegetation_data(
        self,
        latitude: float,
        longitude: float
    ) -> VegetationData:
        """
        Get vegetation and land use data for a location.

        Args:
            latitude: Location latitude
            longitude: Location longitude

        Returns:
            VegetationData object
        """
        biome = self.identify_biome(latitude, longitude)

        # Determine likely vegetation type based on biome
        if biome == "Amazônia":
            fuel_type = "floresta_densa"
            land_use = "Floresta Densa"
            land_use_code = 3
        elif biome == "Cerrado":
            fuel_type = "cerrado"
            land_use = "Cerrado Típico"
            land_use_code = 4
        elif biome == "Mata Atlântica":
            fuel_type = "floresta_aberta"
            land_use = "Floresta Estacional"
            land_use_code = 3
        elif biome == "Caatinga":
            fuel_type = "campo"
            land_use = "Caatinga"
            land_use_code = 12
        elif biome == "Pampa":
            fuel_type = "campo"
            land_use = "Campo Nativo"
            land_use_code = 12
        elif biome == "Pantanal":
            fuel_type = "area_umida"
            land_use = "Área Úmida"
            land_use_code = 11
        else:
            fuel_type = "cerrado"
            land_use = "Vegetação Mista"
            land_use_code = 4

        fuel_chars = FUEL_CHARACTERISTICS.get(fuel_type, FUEL_CHARACTERISTICS["cerrado"])
        biomass = self.BIOMASS_BY_BIOME.get(biome, {"avg": 50})["avg"]

        # Determine conservation status
        if biome in ["Amazônia", "Mata Atlântica"]:
            conservation = "critical"
        elif biome in ["Cerrado", "Caatinga"]:
            conservation = "vulnerable"
        else:
            conservation = "stable"

        return VegetationData(
            latitude=latitude,
            longitude=longitude,
            biome=biome,
            land_use_class=land_use,
            land_use_code=land_use_code,
            fuel_type=fuel_type,
            fuel_load_ton_ha=fuel_chars["fuel_load_ton_ha"],
            fuel_depth_m=fuel_chars["fuel_depth_m"],
            moisture_content=fuel_chars["moisture_content"],
            spread_rate_factor=fuel_chars["spread_rate_factor"],
            biomass_ton_c_ha=biomass,
            conservation_status=conservation,
        )

    def analyze_fire_impact(
        self,
        latitude: float,
        longitude: float,
        area_hectares: float
    ) -> BiomeAnalysis:
        """
        Analyze the environmental impact of a fire.

        Args:
            latitude: Fire center latitude
            longitude: Fire center longitude
            area_hectares: Burned area in hectares

        Returns:
            BiomeAnalysis object with impact assessment
        """
        vegetation = self.get_vegetation_data(latitude, longitude)
        biome = vegetation.biome

        # Calculate biomass and emissions
        biomass_lost = area_hectares * vegetation.biomass_ton_c_ha
        co2_emissions = biomass_lost * 3.67  # Carbon to CO2 conversion

        # Get recovery time and species at risk
        recovery_years = self.RECOVERY_TIME.get(biome, 20)
        species_at_risk = self.ENDEMIC_SPECIES.get(biome, [])[:5]

        # Determine conservation impact
        if area_hectares > 1000 and biome in ["Amazônia", "Mata Atlântica"]:
            impact = "severe"
        elif area_hectares > 500:
            impact = "significant"
        elif area_hectares > 100:
            impact = "moderate"
        else:
            impact = "minor"

        return BiomeAnalysis(
            biome=biome,
            total_area_affected_ha=area_hectares,
            vegetation_types=[{
                "type": vegetation.land_use_class,
                "percentage": 100,
                "fuel_type": vegetation.fuel_type,
            }],
            estimated_biomass_lost_ton=biomass_lost,
            estimated_co2_emissions_ton=co2_emissions,
            recovery_time_years=recovery_years,
            endemic_species_at_risk=species_at_risk,
            conservation_impact=impact,
        )

    def get_fuel_model(
        self,
        latitude: float,
        longitude: float
    ) -> Dict[str, Any]:
        """
        Get fuel model parameters for fire spread calculation.

        Args:
            latitude: Location latitude
            longitude: Location longitude

        Returns:
            Dictionary with fuel model parameters
        """
        vegetation = self.get_vegetation_data(latitude, longitude)
        fuel_chars = FUEL_CHARACTERISTICS.get(
            vegetation.fuel_type,
            FUEL_CHARACTERISTICS["cerrado"]
        )

        return {
            "fuel_type": vegetation.fuel_type,
            "fuel_load_kg_m2": fuel_chars["fuel_load_ton_ha"] / 10,  # Convert to kg/m2
            "fuel_depth_m": fuel_chars["fuel_depth_m"],
            "moisture_extinction": fuel_chars["moisture_content"] * 100,
            "spread_rate_factor": fuel_chars["spread_rate_factor"],
            "flame_length_factor": fuel_chars["flame_length_factor"],
            "description": fuel_chars["description"],
            "biome": vegetation.biome,
        }


def get_vegetation_for_hotspot(
    latitude: float,
    longitude: float
) -> VegetationData:
    """
    Convenience function to get vegetation data for a fire hotspot.

    Args:
        latitude: Hotspot latitude
        longitude: Hotspot longitude

    Returns:
        VegetationData object
    """
    client = MapBiomasClient()
    return client.get_vegetation_data(latitude, longitude)
