"""
Tests for NASA FIRMS client
"""
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime

import sys
sys.path.insert(0, '.')

from src.ingestion.firms_client import FIRMSClient, Hotspot


class TestFIRMSClient:
    """Test suite for FIRMS client."""

    def setup_method(self):
        """Setup test fixtures."""
        self.client = FIRMSClient(api_key="test_api_key")

    def test_client_initialization(self):
        """Test client initializes with API key."""
        assert self.client.api_key == "test_api_key"
        assert self.client.base_url is not None

    def test_client_without_api_key(self):
        """Test client raises error without API key."""
        with pytest.raises(ValueError):
            FIRMSClient(api_key="")

    @patch('src.ingestion.firms_client.httpx.Client')
    def test_get_hotspots_brazil(self, mock_client):
        """Test fetching hotspots for Brazil."""
        # Mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = """latitude,longitude,bright_ti4,frp,confidence,acq_date,acq_time,satellite,daynight
-22.5,-45.5,350.5,50.0,nominal,2026-01-27,1430,NOAA-20,D
-23.0,-46.0,320.0,30.0,high,2026-01-27,1435,NOAA-20,D"""

        mock_client_instance = MagicMock()
        mock_client_instance.get.return_value = mock_response
        mock_client.return_value.__enter__ = MagicMock(return_value=mock_client_instance)
        mock_client.return_value.__exit__ = MagicMock(return_value=False)

        hotspots = self.client.get_hotspots(
            west=-74, south=-34, east=-34, north=5, days=1
        )

        assert len(hotspots) == 2
        assert hotspots[0].latitude == -22.5
        assert hotspots[0].longitude == -45.5
        assert hotspots[0].frp == 50.0

    def test_parse_csv_empty(self):
        """Test parsing empty CSV."""
        result = self.client._parse_csv("")
        assert result == []

    def test_parse_csv_valid(self):
        """Test parsing valid CSV data."""
        csv_data = """latitude,longitude,bright_ti4,frp,confidence,acq_date,acq_time,satellite,daynight
-22.5,-45.5,350.5,50.0,nominal,2026-01-27,1430,NOAA-20,D"""

        result = self.client._parse_csv(csv_data)

        assert len(result) == 1
        assert result[0].latitude == -22.5
        assert result[0].frp == 50.0

    def test_hotspot_dataclass(self):
        """Test Hotspot dataclass."""
        hotspot = Hotspot(
            latitude=-22.5,
            longitude=-45.5,
            brightness=350.5,
            frp=50.0,
            confidence="nominal",
            acq_datetime="2026-01-27 14:30",
            satellite="NOAA-20",
            daynight="D"
        )

        assert hotspot.latitude == -22.5
        assert hotspot.is_daytime == True


class TestHotspotModel:
    """Test Hotspot data model."""

    def test_hotspot_creation(self):
        """Test creating a hotspot."""
        hotspot = Hotspot(
            latitude=-15.5,
            longitude=-47.5,
            brightness=400.0,
            frp=75.5,
            confidence="high",
            acq_datetime="2026-01-27 12:00",
            satellite="NOAA-20",
            daynight="D"
        )

        assert hotspot.latitude == -15.5
        assert hotspot.longitude == -47.5
        assert hotspot.frp == 75.5

    def test_hotspot_is_daytime(self):
        """Test daytime detection."""
        day_hotspot = Hotspot(
            latitude=-15.5, longitude=-47.5, brightness=400.0,
            frp=75.5, confidence="high", acq_datetime="2026-01-27 12:00",
            satellite="NOAA-20", daynight="D"
        )

        night_hotspot = Hotspot(
            latitude=-15.5, longitude=-47.5, brightness=400.0,
            frp=75.5, confidence="high", acq_datetime="2026-01-27 00:00",
            satellite="NOAA-20", daynight="N"
        )

        assert day_hotspot.is_daytime == True
        assert night_hotspot.is_daytime == False
