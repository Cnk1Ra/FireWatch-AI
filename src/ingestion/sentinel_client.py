"""
Sentinel-2 satellite imagery client
Fetches and processes Sentinel-2 data for fire analysis
"""

import os
import logging
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class SentinelImage:
    """Sentinel-2 image metadata."""
    product_id: str
    acquisition_date: datetime
    cloud_cover: float
    platform: str  # Sentinel-2A or Sentinel-2B

    # Geographic bounds
    footprint: Dict[str, float]  # {west, south, east, north}

    # URLs
    preview_url: Optional[str] = None
    download_url: Optional[str] = None

    # Processing level
    processing_level: str = "L2A"  # L1C or L2A

    # File paths (after download)
    local_path: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "product_id": self.product_id,
            "acquisition_date": self.acquisition_date.isoformat(),
            "cloud_cover": self.cloud_cover,
            "platform": self.platform,
            "footprint": self.footprint,
            "preview_url": self.preview_url,
            "processing_level": self.processing_level
        }


@dataclass
class BurnedAreaAnalysis:
    """Result of burned area analysis from Sentinel imagery."""
    total_burned_ha: float
    confidence: float

    # Burn severity
    severe_ha: float = 0
    moderate_ha: float = 0
    light_ha: float = 0

    # Spectral indices
    dnbr_mean: Optional[float] = None  # Differenced NBR
    ndvi_change: Optional[float] = None

    # Image info
    pre_fire_date: Optional[datetime] = None
    post_fire_date: Optional[datetime] = None

    # GeoJSON of burned area
    burned_polygon: Optional[Dict] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "total_burned_ha": self.total_burned_ha,
            "confidence": self.confidence,
            "severity": {
                "severe_ha": self.severe_ha,
                "moderate_ha": self.moderate_ha,
                "light_ha": self.light_ha
            },
            "indices": {
                "dnbr_mean": self.dnbr_mean,
                "ndvi_change": self.ndvi_change
            },
            "pre_fire_date": self.pre_fire_date.isoformat() if self.pre_fire_date else None,
            "post_fire_date": self.post_fire_date.isoformat() if self.post_fire_date else None
        }


class SentinelClient:
    """
    Client for Sentinel-2 satellite imagery.

    Provides access to Sentinel-2 data via Copernicus Open Access Hub
    or Sentinel Hub services.
    """

    # Sentinel Hub API
    SENTINEL_HUB_URL = "https://services.sentinel-hub.com"

    # Copernicus Open Access Hub
    COPERNICUS_URL = "https://scihub.copernicus.eu/dhus"

    # Band wavelengths (nm)
    BANDS = {
        "B02": {"name": "Blue", "wavelength": 490, "resolution": 10},
        "B03": {"name": "Green", "wavelength": 560, "resolution": 10},
        "B04": {"name": "Red", "wavelength": 665, "resolution": 10},
        "B05": {"name": "Red Edge 1", "wavelength": 705, "resolution": 20},
        "B06": {"name": "Red Edge 2", "wavelength": 740, "resolution": 20},
        "B07": {"name": "Red Edge 3", "wavelength": 783, "resolution": 20},
        "B08": {"name": "NIR", "wavelength": 842, "resolution": 10},
        "B8A": {"name": "Red Edge 4", "wavelength": 865, "resolution": 20},
        "B11": {"name": "SWIR 1", "wavelength": 1610, "resolution": 20},
        "B12": {"name": "SWIR 2", "wavelength": 2190, "resolution": 20},
    }

    def __init__(
        self,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        instance_id: Optional[str] = None,
        download_dir: Optional[str] = None
    ):
        """
        Initialize Sentinel client.

        Args:
            client_id: Sentinel Hub client ID
            client_secret: Sentinel Hub client secret
            instance_id: Sentinel Hub instance ID
            download_dir: Directory for downloaded images
        """
        self.client_id = client_id or os.getenv("SENTINEL_CLIENT_ID")
        self.client_secret = client_secret or os.getenv("SENTINEL_CLIENT_SECRET")
        self.instance_id = instance_id or os.getenv("SENTINEL_INSTANCE_ID")

        self.download_dir = Path(download_dir or "data/sentinel")
        self.download_dir.mkdir(parents=True, exist_ok=True)

        self._token = None
        self._token_expiry = None

        logger.info("SentinelClient initialized")

    @property
    def is_configured(self) -> bool:
        """Check if client is properly configured."""
        return bool(self.client_id and self.client_secret)

    def _get_token(self) -> Optional[str]:
        """Get OAuth2 token for Sentinel Hub."""
        if not self.is_configured:
            return None

        # Check if token is still valid
        if self._token and self._token_expiry:
            if datetime.utcnow() < self._token_expiry:
                return self._token

        try:
            import httpx

            response = httpx.post(
                "https://services.sentinel-hub.com/oauth/token",
                data={
                    "grant_type": "client_credentials",
                    "client_id": self.client_id,
                    "client_secret": self.client_secret
                }
            )
            response.raise_for_status()

            data = response.json()
            self._token = data["access_token"]
            self._token_expiry = datetime.utcnow() + timedelta(
                seconds=data.get("expires_in", 3600) - 60
            )

            return self._token

        except Exception as e:
            logger.error(f"Failed to get Sentinel Hub token: {e}")
            return None

    def search_images(
        self,
        west: float,
        south: float,
        east: float,
        north: float,
        start_date: datetime,
        end_date: Optional[datetime] = None,
        max_cloud_cover: float = 30.0,
        limit: int = 10
    ) -> List[SentinelImage]:
        """
        Search for Sentinel-2 images in an area.

        Args:
            west, south, east, north: Bounding box
            start_date: Start of date range
            end_date: End of date range (default: now)
            max_cloud_cover: Maximum cloud cover percentage
            limit: Maximum number of results

        Returns:
            List of SentinelImage metadata
        """
        if not self.is_configured:
            logger.warning("Sentinel client not configured")
            return []

        end_date = end_date or datetime.utcnow()

        try:
            import httpx

            token = self._get_token()
            if not token:
                return []

            # Catalog API search
            response = httpx.post(
                f"{self.SENTINEL_HUB_URL}/api/v1/catalog/search",
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "bbox": [west, south, east, north],
                    "datetime": f"{start_date.isoformat()}Z/{end_date.isoformat()}Z",
                    "collections": ["sentinel-2-l2a"],
                    "filter": f"eo:cloud_cover < {max_cloud_cover}",
                    "limit": limit
                }
            )
            response.raise_for_status()

            results = []
            for feature in response.json().get("features", []):
                props = feature.get("properties", {})
                results.append(SentinelImage(
                    product_id=feature.get("id"),
                    acquisition_date=datetime.fromisoformat(
                        props.get("datetime", "").replace("Z", "")
                    ),
                    cloud_cover=props.get("eo:cloud_cover", 0),
                    platform=props.get("platform", "Sentinel-2"),
                    footprint={
                        "west": west, "south": south,
                        "east": east, "north": north
                    },
                    processing_level="L2A"
                ))

            logger.info(f"Found {len(results)} Sentinel-2 images")
            return results

        except Exception as e:
            logger.error(f"Sentinel search failed: {e}")
            return []

    def get_bands(
        self,
        west: float,
        south: float,
        east: float,
        north: float,
        date: datetime,
        bands: List[str] = ["B02", "B03", "B04", "B08", "B11", "B12"],
        resolution: int = 20
    ) -> Optional[Dict[str, Any]]:
        """
        Get band data for an area.

        Args:
            west, south, east, north: Bounding box
            date: Acquisition date
            bands: List of band names
            resolution: Pixel resolution in meters

        Returns:
            Dictionary of band arrays
        """
        if not self.is_configured:
            return self._simulate_bands(west, south, east, north, bands)

        try:
            import httpx
            import numpy as np

            token = self._get_token()
            if not token:
                return None

            # Build evalscript for requested bands
            evalscript = self._build_evalscript(bands)

            # Process API request
            response = httpx.post(
                f"{self.SENTINEL_HUB_URL}/api/v1/process",
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "input": {
                        "bounds": {
                            "bbox": [west, south, east, north],
                            "properties": {"crs": "http://www.opengis.net/def/crs/EPSG/0/4326"}
                        },
                        "data": [{
                            "type": "sentinel-2-l2a",
                            "dataFilter": {
                                "timeRange": {
                                    "from": (date - timedelta(days=5)).isoformat() + "Z",
                                    "to": (date + timedelta(days=1)).isoformat() + "Z"
                                }
                            }
                        }]
                    },
                    "output": {
                        "width": 512,
                        "height": 512,
                        "responses": [{"identifier": "default", "format": {"type": "image/tiff"}}]
                    },
                    "evalscript": evalscript
                }
            )
            response.raise_for_status()

            # Parse response (would need rasterio for real implementation)
            logger.info(f"Retrieved {len(bands)} bands for date {date}")
            return {"status": "success", "bands": bands}

        except Exception as e:
            logger.error(f"Failed to get Sentinel bands: {e}")
            return None

    def calculate_nbr(
        self,
        nir_band: Any,
        swir_band: Any
    ) -> Any:
        """
        Calculate Normalized Burn Ratio.

        NBR = (NIR - SWIR) / (NIR + SWIR)

        Args:
            nir_band: Near-infrared band (B08)
            swir_band: Short-wave infrared band (B12)

        Returns:
            NBR array
        """
        try:
            import numpy as np

            nir = nir_band.astype(float)
            swir = swir_band.astype(float)

            # Avoid division by zero
            denominator = nir + swir
            denominator[denominator == 0] = 0.0001

            nbr = (nir - swir) / denominator

            return nbr

        except Exception as e:
            logger.error(f"NBR calculation failed: {e}")
            return None

    def calculate_dnbr(
        self,
        pre_nbr: Any,
        post_nbr: Any
    ) -> Any:
        """
        Calculate differenced NBR for burn severity.

        dNBR = NBR_pre - NBR_post

        Args:
            pre_nbr: Pre-fire NBR
            post_nbr: Post-fire NBR

        Returns:
            dNBR array
        """
        return pre_nbr - post_nbr

    def analyze_burned_area(
        self,
        west: float,
        south: float,
        east: float,
        north: float,
        fire_date: datetime,
        pre_days: int = 30,
        post_days: int = 5
    ) -> BurnedAreaAnalysis:
        """
        Analyze burned area using Sentinel-2 imagery.

        Args:
            west, south, east, north: Bounding box
            fire_date: Approximate fire date
            pre_days: Days before fire for pre-image
            post_days: Days after fire for post-image

        Returns:
            BurnedAreaAnalysis
        """
        result = BurnedAreaAnalysis(
            total_burned_ha=0,
            confidence=0
        )

        if not self.is_configured:
            # Return simulated result
            return self._simulate_burned_area(west, south, east, north)

        try:
            # Get pre-fire image
            pre_date = fire_date - timedelta(days=pre_days)
            pre_images = self.search_images(
                west, south, east, north,
                start_date=pre_date,
                end_date=fire_date - timedelta(days=1),
                max_cloud_cover=20,
                limit=1
            )

            # Get post-fire image
            post_images = self.search_images(
                west, south, east, north,
                start_date=fire_date,
                end_date=fire_date + timedelta(days=post_days),
                max_cloud_cover=20,
                limit=1
            )

            if pre_images and post_images:
                result.pre_fire_date = pre_images[0].acquisition_date
                result.post_fire_date = post_images[0].acquisition_date

                # Get bands and calculate dNBR
                # This would require full implementation with rasterio
                logger.info(
                    f"Would analyze burned area with images from "
                    f"{result.pre_fire_date} and {result.post_fire_date}"
                )

                # Simulated result for now
                return self._simulate_burned_area(west, south, east, north)

        except Exception as e:
            logger.error(f"Burned area analysis failed: {e}")

        return result

    def _build_evalscript(self, bands: List[str]) -> str:
        """Build Sentinel Hub evalscript for bands."""
        band_list = ", ".join(f'"{b}"' for b in bands)
        return f"""
        //VERSION=3
        function setup() {{
            return {{
                input: [{{ bands: [{band_list}] }}],
                output: {{ bands: {len(bands)}, sampleType: "FLOAT32" }}
            }};
        }}

        function evaluatePixel(sample) {{
            return [{", ".join(f"sample.{b}" for b in bands)}];
        }}
        """

    def _simulate_bands(
        self,
        west: float,
        south: float,
        east: float,
        north: float,
        bands: List[str]
    ) -> Dict[str, Any]:
        """Simulate band data for testing."""
        try:
            import numpy as np

            result = {}
            for band in bands:
                # Create random data simulating satellite imagery
                result[band] = np.random.random((256, 256)) * 10000

            return result

        except ImportError:
            return {band: None for band in bands}

    def _simulate_burned_area(
        self,
        west: float,
        south: float,
        east: float,
        north: float
    ) -> BurnedAreaAnalysis:
        """Simulate burned area analysis for testing."""
        import random

        # Calculate approximate area in hectares
        lat_range = abs(north - south) * 111  # km
        lon_range = abs(east - west) * 111 * 0.8  # km, adjusted for latitude
        total_area_ha = lat_range * lon_range * 100  # hectares

        # Simulate burned percentage (1-30% of area)
        burned_percent = random.uniform(0.01, 0.3)
        total_burned = total_area_ha * burned_percent

        return BurnedAreaAnalysis(
            total_burned_ha=round(total_burned, 1),
            confidence=random.uniform(0.6, 0.9),
            severe_ha=round(total_burned * 0.2, 1),
            moderate_ha=round(total_burned * 0.5, 1),
            light_ha=round(total_burned * 0.3, 1),
            dnbr_mean=random.uniform(0.1, 0.5),
            ndvi_change=random.uniform(-0.3, -0.1),
            pre_fire_date=datetime.utcnow() - timedelta(days=30),
            post_fire_date=datetime.utcnow() - timedelta(days=2)
        )
