"""
NASA FIRMS API Client for FireWatch AI

This module provides a client for fetching fire hotspot data from NASA's
Fire Information for Resource Management System (FIRMS).

Data sources:
- VIIRS (Visible Infrared Imaging Radiometer Suite) - NOAA-20, NOAA-21
- MODIS (Moderate Resolution Imaging Spectroradiometer) - Terra, Aqua

API Documentation: https://firms.modaps.eosdis.nasa.gov/api/
"""

import csv
import logging
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from io import StringIO
from typing import Optional

import httpx

logger = logging.getLogger(__name__)


class DataSource(str, Enum):
    """Available satellite data sources from NASA FIRMS."""
    
    VIIRS_NOAA20_NRT = "VIIRS_NOAA20_NRT"
    VIIRS_NOAA21_NRT = "VIIRS_NOAA21_NRT"
    VIIRS_SNPP_NRT = "VIIRS_SNPP_NRT"
    MODIS_NRT = "MODIS_NRT"
    LANDSAT_NRT = "LANDSAT_NRT"


@dataclass
class FireHotspot:
    """
    Represents a single fire hotspot detection from satellite data.
    
    Attributes:
        latitude: Latitude in decimal degrees
        longitude: Longitude in decimal degrees
        brightness: Brightness temperature in Kelvin (channel 4 for VIIRS)
        scan: Scan pixel size in km
        track: Track pixel size in km
        acq_date: Acquisition date (YYYY-MM-DD)
        acq_time: Acquisition time (HHMM UTC)
        satellite: Satellite identifier (e.g., "N20" for NOAA-20)
        instrument: Instrument name (e.g., "VIIRS")
        confidence: Detection confidence ("h"=high, "n"=nominal, "l"=low)
        version: Data version
        bright_t31: Brightness temperature channel 31/5 in Kelvin
        frp: Fire Radiative Power in MW
        daynight: Day/Night flag ("D" or "N")
    """
    
    latitude: float
    longitude: float
    brightness: float
    scan: float
    track: float
    acq_date: str
    acq_time: str
    satellite: str
    instrument: str
    confidence: str
    version: str
    bright_t31: float
    frp: float
    daynight: str
    
    @property
    def datetime(self) -> datetime:
        """Parse acquisition date and time into datetime object."""
        time_str = self.acq_time.zfill(4)
        dt_str = f"{self.acq_date} {time_str[:2]}:{time_str[2:]}"
        return datetime.strptime(dt_str, "%Y-%m-%d %H:%M")
    
    @property
    def confidence_level(self) -> str:
        """Human-readable confidence level."""
        mapping = {"h": "high", "n": "nominal", "l": "low"}
        return mapping.get(self.confidence, "unknown")
    
    @property
    def is_daytime(self) -> bool:
        """Check if detection was during daytime."""
        return self.daynight == "D"
    
    @property
    def pixel_area_km2(self) -> float:
        """Calculate approximate pixel area in square kilometers."""
        return self.scan * self.track
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "latitude": self.latitude,
            "longitude": self.longitude,
            "brightness": self.brightness,
            "frp": self.frp,
            "confidence": self.confidence_level,
            "datetime": self.datetime.isoformat(),
            "satellite": self.satellite,
            "instrument": self.instrument,
            "daynight": "day" if self.is_daytime else "night",
        }


class FIRMSClient:
    """
    Client for NASA FIRMS (Fire Information for Resource Management System) API.
    
    Usage:
        client = FIRMSClient(api_key="your_key")
        hotspots = client.get_country_hotspots("BRA", days=1)
        
    API Limits:
        - 5000 transactions per 10 minutes
        - Requests for >7 days count as multiple transactions
    """
    
    BASE_URL = "https://firms.modaps.eosdis.nasa.gov/api/area/csv"
    
    def __init__(self, api_key: str, timeout: float = 30.0):
        """
        Initialize FIRMS client.
        
        Args:
            api_key: NASA FIRMS MAP_KEY
            timeout: HTTP request timeout in seconds
        """
        self.api_key = api_key
        self.timeout = timeout
        self._client = httpx.Client(timeout=timeout)
    
    def __enter__(self):
        return self
    
    def __exit__(self, *args):
        self._client.close()
    
    def _parse_csv(self, csv_text: str) -> list[FireHotspot]:
        """Parse CSV response into FireHotspot objects."""
        hotspots = []
        reader = csv.DictReader(StringIO(csv_text))
        
        for row in reader:
            try:
                hotspot = FireHotspot(
                    latitude=float(row["latitude"]),
                    longitude=float(row["longitude"]),
                    brightness=float(row.get("bright_ti4", row.get("brightness", 0))),
                    scan=float(row["scan"]),
                    track=float(row["track"]),
                    acq_date=row["acq_date"],
                    acq_time=row["acq_time"],
                    satellite=row["satellite"],
                    instrument=row["instrument"],
                    confidence=row["confidence"],
                    version=row["version"],
                    bright_t31=float(row.get("bright_ti5", row.get("bright_t31", 0))),
                    frp=float(row["frp"]),
                    daynight=row["daynight"],
                )
                hotspots.append(hotspot)
            except (KeyError, ValueError) as e:
                logger.warning(f"Failed to parse hotspot row: {e}")
                continue
        
        return hotspots
    
    def get_area_hotspots(
        self,
        west: float,
        south: float,
        east: float,
        north: float,
        days: int = 1,
        source: DataSource = DataSource.VIIRS_NOAA20_NRT,
    ) -> list[FireHotspot]:
        """
        Get hotspots within a bounding box.
        
        Args:
            west: Western longitude (-180 to 180)
            south: Southern latitude (-90 to 90)
            east: Eastern longitude (-180 to 180)
            north: Northern latitude (-90 to 90)
            days: Number of days (1-10)
            source: Satellite data source
            
        Returns:
            List of FireHotspot objects
        """
        url = f"{self.BASE_URL}/{self.api_key}/{source.value}/{west},{south},{east},{north}/{days}"
        
        logger.info(f"Fetching hotspots for area: [{west},{south},{east},{north}], days={days}")
        response = self._client.get(url)
        response.raise_for_status()
        
        hotspots = self._parse_csv(response.text)
        logger.info(f"Retrieved {len(hotspots)} hotspots")
        
        return hotspots
    
    def get_country_hotspots(
        self,
        country_code: str,
        days: int = 1,
        source: DataSource = DataSource.VIIRS_NOAA20_NRT,
    ) -> list[FireHotspot]:
        """
        Get hotspots for a specific country.
        
        Args:
            country_code: ISO 3166-1 alpha-3 country code (e.g., "BRA", "USA")
            days: Number of days (1-10)
            source: Satellite data source
            
        Returns:
            List of FireHotspot objects
        """
        url = f"{self.BASE_URL}/{self.api_key}/{source.value}/{country_code}/{days}"
        
        logger.info(f"Fetching hotspots for country: {country_code}, days={days}")
        response = self._client.get(url)
        response.raise_for_status()
        
        hotspots = self._parse_csv(response.text)
        logger.info(f"Retrieved {len(hotspots)} hotspots for {country_code}")
        
        return hotspots
    
    def get_world_hotspots(
        self,
        days: int = 1,
        source: DataSource = DataSource.VIIRS_NOAA20_NRT,
    ) -> list[FireHotspot]:
        """
        Get global hotspots (warning: large dataset).
        
        Args:
            days: Number of days (1-10)
            source: Satellite data source
            
        Returns:
            List of FireHotspot objects
        """
        url = f"{self.BASE_URL}/{self.api_key}/{source.value}/world/{days}"
        
        logger.info(f"Fetching global hotspots, days={days}")
        response = self._client.get(url)
        response.raise_for_status()
        
        hotspots = self._parse_csv(response.text)
        logger.info(f"Retrieved {len(hotspots)} global hotspots")
        
        return hotspots


# Brazil bounding box for convenience
BRAZIL_BBOX = {
    "west": -73.98,
    "south": -33.75,
    "east": -34.79,
    "north": 5.27,
}


def get_brazil_hotspots(api_key: str, days: int = 1) -> list[FireHotspot]:
    """Convenience function to get hotspots for Brazil."""
    with FIRMSClient(api_key) as client:
        return client.get_area_hotspots(**BRAZIL_BBOX, days=days)
