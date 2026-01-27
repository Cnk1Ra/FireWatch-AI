"""
Tests for analysis modules
"""
import pytest
from unittest.mock import patch, MagicMock

import sys
sys.path.insert(0, '.')

from src.analysis.fire_clustering import FireClusterer, FireCluster
from src.analysis.burned_area import BurnedAreaCalculator
from src.analysis.carbon_emissions import CarbonEmissionsCalculator
from src.analysis.biome_analysis import BiomeAnalyzer


class TestFireClusterer:
    """Test suite for fire clustering."""

    def setup_method(self):
        """Setup test fixtures."""
        self.clusterer = FireClusterer(distance_threshold_km=5.0)

    def test_clusterer_initialization(self):
        """Test clusterer initializes correctly."""
        assert self.clusterer.distance_threshold_km == 5.0

    def test_cluster_single_hotspot(self):
        """Test clustering with single hotspot."""
        hotspots = [
            {"latitude": -22.5, "longitude": -45.5, "frp": 50.0}
        ]

        clusters = self.clusterer.cluster(hotspots)

        assert len(clusters) == 1
        assert clusters[0].hotspot_count == 1

    def test_cluster_nearby_hotspots(self):
        """Test clustering nearby hotspots."""
        hotspots = [
            {"latitude": -22.5, "longitude": -45.5, "frp": 50.0},
            {"latitude": -22.51, "longitude": -45.51, "frp": 30.0},  # ~1.5km away
            {"latitude": -22.52, "longitude": -45.52, "frp": 40.0},  # ~3km away
        ]

        clusters = self.clusterer.cluster(hotspots)

        # Should be grouped into 1 cluster (all within 5km)
        assert len(clusters) == 1
        assert clusters[0].hotspot_count == 3
        assert clusters[0].total_frp == 120.0

    def test_cluster_distant_hotspots(self):
        """Test clustering distant hotspots."""
        hotspots = [
            {"latitude": -22.5, "longitude": -45.5, "frp": 50.0},
            {"latitude": -23.5, "longitude": -46.5, "frp": 30.0},  # ~150km away
        ]

        clusters = self.clusterer.cluster(hotspots)

        # Should be 2 separate clusters
        assert len(clusters) == 2

    def test_cluster_empty_list(self):
        """Test clustering empty list."""
        clusters = self.clusterer.cluster([])
        assert clusters == []


class TestBurnedAreaCalculator:
    """Test suite for burned area calculation."""

    def setup_method(self):
        """Setup test fixtures."""
        self.calculator = BurnedAreaCalculator()

    def test_calculate_from_hotspots(self):
        """Test area calculation from hotspots."""
        hotspots = [
            {"latitude": -22.5, "longitude": -45.5, "frp": 50.0},
            {"latitude": -22.51, "longitude": -45.51, "frp": 30.0},
            {"latitude": -22.52, "longitude": -45.52, "frp": 40.0},
        ]

        result = self.calculator.calculate_from_hotspots(hotspots)

        assert result.total_area_ha > 0
        assert result.hotspot_count == 3

    def test_calculate_single_hotspot(self):
        """Test area for single hotspot."""
        hotspots = [
            {"latitude": -22.5, "longitude": -45.5, "frp": 50.0}
        ]

        result = self.calculator.calculate_from_hotspots(hotspots)

        # Single hotspot should have minimum area (1 pixel = ~1 ha)
        assert result.total_area_ha >= 1.0

    def test_estimate_severity(self):
        """Test burn severity estimation."""
        result = self.calculator.estimate_severity(total_area=100.0, avg_frp=50.0)

        assert "severe" in result
        assert "moderate" in result
        assert "light" in result
        assert result["severe"] + result["moderate"] + result["light"] == pytest.approx(100.0, rel=0.1)


class TestCarbonEmissionsCalculator:
    """Test suite for carbon emissions calculation."""

    def setup_method(self):
        """Setup test fixtures."""
        self.calculator = CarbonEmissionsCalculator()

    def test_calculate_emissions_cerrado(self):
        """Test emissions for Cerrado biome."""
        result = self.calculator.calculate(
            area_ha=100.0,
            biome="Cerrado"
        )

        assert result.co2_tons > 0
        assert result.ch4_tons > 0
        assert result.pm25_tons > 0
        assert result.cars_equivalent > 0

    def test_calculate_emissions_amazonia(self):
        """Test emissions for Amazonia biome."""
        result_amazon = self.calculator.calculate(area_ha=100.0, biome="Amazonia")
        result_cerrado = self.calculator.calculate(area_ha=100.0, biome="Cerrado")

        # Amazon should have higher emissions (more biomass)
        assert result_amazon.co2_tons > result_cerrado.co2_tons

    def test_emissions_zero_area(self):
        """Test emissions for zero area."""
        result = self.calculator.calculate(area_ha=0, biome="Cerrado")
        assert result.co2_tons == 0

    def test_get_biomass_factor(self):
        """Test biomass factor retrieval."""
        factor = self.calculator.get_biomass_factor("Amazonia")
        assert factor >= 150  # Amazon has high biomass

        factor = self.calculator.get_biomass_factor("Pampa")
        assert factor <= 30  # Pampa has low biomass


class TestBiomeAnalyzer:
    """Test suite for biome analysis."""

    def setup_method(self):
        """Setup test fixtures."""
        self.analyzer = BiomeAnalyzer()

    def test_identify_biome_amazonia(self):
        """Test identifying Amazonia biome."""
        # Coordinates in Amazon
        biome = self.analyzer.identify_biome(latitude=-3.0, longitude=-60.0)
        assert biome.name == "Amazonia"

    def test_identify_biome_cerrado(self):
        """Test identifying Cerrado biome."""
        # Coordinates in Cerrado
        biome = self.analyzer.identify_biome(latitude=-15.0, longitude=-47.0)
        assert biome.name in ["Cerrado", "Amazonia"]  # Border region

    def test_identify_biome_pantanal(self):
        """Test identifying Pantanal biome."""
        # Coordinates in Pantanal
        biome = self.analyzer.identify_biome(latitude=-19.0, longitude=-57.0)
        assert biome.name == "Pantanal"

    def test_get_biome_properties(self):
        """Test getting biome properties."""
        props = self.analyzer.get_biome_properties("Amazonia")

        assert "carbon_tons_ha" in props
        assert "recovery_years" in props
        assert props["carbon_tons_ha"] > 100  # High carbon in Amazon

    def test_unknown_location(self):
        """Test unknown location returns default."""
        biome = self.analyzer.identify_biome(latitude=0, longitude=0)  # Ocean
        assert biome.name == "Desconhecido"
