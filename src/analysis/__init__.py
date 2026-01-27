"""
FireWatch AI - Analysis Module
Tools for analyzing fire data, calculating affected areas, and estimating impacts.
"""

from src.analysis.fire_clustering import (
    FireCluster,
    cluster_hotspots,
    get_cluster_statistics,
)
from src.analysis.burned_area import (
    BurnedAreaEstimate,
    calculate_burned_area,
    estimate_area_from_hotspots,
)
from src.analysis.biome_analysis import (
    BiomeImpact,
    analyze_biome_impact,
    get_affected_vegetation,
)
from src.analysis.carbon_emissions import (
    CarbonEmissions,
    calculate_emissions,
    estimate_co2_from_fire,
)
from src.analysis.fire_perimeter import (
    FirePerimeter,
    calculate_perimeter,
    create_fire_polygon,
)

__all__ = [
    # Clustering
    "FireCluster",
    "cluster_hotspots",
    "get_cluster_statistics",
    # Burned Area
    "BurnedAreaEstimate",
    "calculate_burned_area",
    "estimate_area_from_hotspots",
    # Biome Analysis
    "BiomeImpact",
    "analyze_biome_impact",
    "get_affected_vegetation",
    # Carbon Emissions
    "CarbonEmissions",
    "calculate_emissions",
    "estimate_co2_from_fire",
    # Fire Perimeter
    "FirePerimeter",
    "calculate_perimeter",
    "create_fire_polygon",
]
