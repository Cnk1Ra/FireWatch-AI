"""
FireWatch AI - Vercel Serverless API
Standalone version for serverless deployment
"""

import os
from datetime import datetime
from typing import List, Optional
from enum import Enum

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
import httpx

# ============================================================================
# Configuration
# ============================================================================

FIRMS_API_KEY = os.getenv("FIRMS_API_KEY", "")
FIRMS_BASE_URL = "https://firms.modaps.eosdis.nasa.gov/api"

# ============================================================================
# FastAPI App
# ============================================================================

app = FastAPI(
    title="FireWatch AI",
    description="Open-source global wildfire detection API combining NASA satellite data and AI",
    version="0.2.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Vercel handler
handler = app

# ============================================================================
# Enums & Models
# ============================================================================

class DataSource(str, Enum):
    VIIRS_NOAA20_NRT = "VIIRS_NOAA20_NRT"
    VIIRS_SNPP_NRT = "VIIRS_SNPP_NRT"
    MODIS_NRT = "MODIS_NRT"


class HotspotResponse(BaseModel):
    latitude: float
    longitude: float
    brightness: float
    frp: float = Field(description="Fire Radiative Power in MW")
    confidence: str
    acq_datetime: str
    satellite: str
    daynight: str


class HotspotsListResponse(BaseModel):
    count: int
    source: str
    query_time: str
    hotspots: List[HotspotResponse]


class HealthResponse(BaseModel):
    status: str
    version: str
    timestamp: str
    api_key_configured: bool


# ============================================================================
# FIRMS Client Functions
# ============================================================================

def parse_csv_hotspots(csv_text: str) -> List[dict]:
    """Parse FIRMS CSV response into hotspot dictionaries."""
    lines = csv_text.strip().split("\n")
    if len(lines) < 2:
        return []

    headers = lines[0].split(",")
    hotspots = []

    for line in lines[1:]:
        values = line.split(",")
        if len(values) >= len(headers):
            row = dict(zip(headers, values))
            try:
                hotspot = {
                    "latitude": float(row.get("latitude", 0)),
                    "longitude": float(row.get("longitude", 0)),
                    "brightness": float(row.get("bright_ti4", 0) or row.get("brightness", 0)),
                    "frp": float(row.get("frp", 0) or 0),
                    "confidence": row.get("confidence", "n"),
                    "acq_datetime": "{} {}".format(row.get("acq_date", ""), row.get("acq_time", "")),
                    "satellite": row.get("satellite", "Unknown"),
                    "daynight": row.get("daynight", "D"),
                }
                hotspots.append(hotspot)
            except (ValueError, KeyError):
                continue

    return hotspots


async def fetch_area_hotspots(
    west: float,
    south: float,
    east: float,
    north: float,
    days: int = 1,
    source: str = "VIIRS_NOAA20_NRT"
) -> List[dict]:
    """Fetch hotspots from FIRMS API for a bounding box."""
    if not FIRMS_API_KEY:
        raise HTTPException(status_code=500, detail="FIRMS_API_KEY not configured")

    url = "{}/area/csv/{}/{}/{},{},{},{}/{}".format(
        FIRMS_BASE_URL, FIRMS_API_KEY, source, west, south, east, north, days
    )

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(url)

        if response.status_code != 200:
            raise HTTPException(
                status_code=response.status_code,
                detail="FIRMS API error: {}".format(response.text[:200])
            )

        return parse_csv_hotspots(response.text)


async def fetch_country_hotspots(
    country_code: str,
    days: int = 1,
    source: str = "VIIRS_NOAA20_NRT"
) -> List[dict]:
    """Fetch hotspots from FIRMS API for a country."""
    if not FIRMS_API_KEY:
        raise HTTPException(status_code=500, detail="FIRMS_API_KEY not configured")

    url = "{}/country/csv/{}/{}/{}/{}".format(
        FIRMS_BASE_URL, FIRMS_API_KEY, source, country_code, days
    )

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(url)

        if response.status_code != 200:
            raise HTTPException(
                status_code=response.status_code,
                detail="FIRMS API error: {}".format(response.text[:200])
            )

        return parse_csv_hotspots(response.text)


# ============================================================================
# Routes
# ============================================================================

@app.get("/", response_class=HTMLResponse)
async def root():
    """Welcome page with API documentation."""
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>FireWatch AI</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            * { box-sizing: border-box; }
            body {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                max-width: 900px;
                margin: 0 auto;
                padding: 20px;
                background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
                color: #eee;
                min-height: 100vh;
            }
            h1 { color: #ff6b35; font-size: 2.5em; margin-bottom: 10px; }
            h3 { color: #f7c873; margin-top: 30px; border-bottom: 1px solid #333; padding-bottom: 10px; }
            a { color: #ff6b35; text-decoration: none; }
            a:hover { text-decoration: underline; }
            code {
                background: #0f0f23;
                padding: 3px 8px;
                border-radius: 4px;
                color: #f7c873;
                font-family: 'Monaco', 'Menlo', monospace;
            }
            .endpoint {
                background: #16213e;
                padding: 12px 15px;
                margin: 8px 0;
                border-radius: 6px;
                border-left: 4px solid #ff6b35;
            }
            .tag {
                background: #ff6b35;
                color: white;
                padding: 3px 10px;
                border-radius: 4px;
                font-size: 12px;
                font-weight: bold;
                margin-right: 10px;
            }
            .subtitle { color: #888; font-size: 1.1em; margin-bottom: 30px; }
            hr { border: none; border-top: 1px solid #333; margin: 40px 0; }
            .stats {
                display: grid;
                grid-template-columns: repeat(3, 1fr);
                gap: 15px;
                margin: 20px 0;
            }
            .stat {
                background: #16213e;
                padding: 15px;
                border-radius: 8px;
                text-align: center;
            }
            .stat-value { font-size: 2em; color: #ff6b35; font-weight: bold; }
            .stat-label { color: #888; font-size: 0.9em; }
            footer { text-align: center; color: #666; margin-top: 40px; }
        </style>
    </head>
    <body>
        <h1>FireWatch AI</h1>
        <p class="subtitle">Open-source global wildfire detection platform combining NASA satellite data and AI analysis.</p>

        <div class="stats">
            <div class="stat">
                <div class="stat-value">NASA</div>
                <div class="stat-label">FIRMS Data</div>
            </div>
            <div class="stat">
                <div class="stat-value">RT</div>
                <div class="stat-label">Real-time</div>
            </div>
            <div class="stat">
                <div class="stat-value">API</div>
                <div class="stat-label">REST + JSON</div>
            </div>
        </div>

        <h3>Documentation</h3>
        <div class="endpoint"><a href="/docs">Swagger UI - Interactive API Documentation</a></div>
        <div class="endpoint"><a href="/redoc">ReDoc - Alternative Documentation</a></div>
        <div class="endpoint"><a href="/health">Health Check</a></div>

        <h3>Fire Hotspots</h3>
        <div class="endpoint">
            <span class="tag">GET</span>
            <code>/api/v1/hotspots/country/{code}</code> - Get fires by country (BRA, USA, AUS)
        </div>
        <div class="endpoint">
            <span class="tag">GET</span>
            <code>/api/v1/hotspots/area</code> - Get fires in bounding box
        </div>

        <h3>Statistics</h3>
        <div class="endpoint">
            <span class="tag">GET</span>
            <code>/api/v1/stats/area</code> - Fire statistics for region
        </div>

        <h3>Example Queries</h3>
        <p>Get fires in Sao Paulo region:</p>
        <code>/api/v1/hotspots/area?west=-50&amp;south=-25&amp;east=-44&amp;north=-19&amp;days=2</code>

        <p style="margin-top:15px">Get fires in Brazil:</p>
        <code>/api/v1/hotspots/country/BRA?days=1</code>

        <hr>
        <footer>
            <p>
                <a href="https://github.com/Cnk1Ra/FireWatch-AI">GitHub Repository</a> |
                Data: <a href="https://firms.modaps.eosdis.nasa.gov/">NASA FIRMS</a>
            </p>
            <p>Version 0.2.0 | Deployed on Vercel</p>
        </footer>
    </body>
    </html>
    """
    return html


@app.get("/health", response_model=HealthResponse, tags=["System"])
async def health_check():
    """Check API health status."""
    return HealthResponse(
        status="healthy",
        version="0.2.0",
        timestamp=datetime.utcnow().isoformat(),
        api_key_configured=bool(FIRMS_API_KEY),
    )


@app.get("/api/v1/hotspots/country/{country_code}", response_model=HotspotsListResponse, tags=["Hotspots"])
async def get_country_hotspots(
    country_code: str,
    days: int = Query(default=1, ge=1, le=10, description="Number of days (1-10)"),
    source: DataSource = Query(default=DataSource.VIIRS_NOAA20_NRT, description="Satellite source"),
):
    """
    Get fire hotspots for a specific country.

    - **country_code**: ISO 3166-1 alpha-3 code (e.g., BRA, USA, AUS, PRT)
    - **days**: Number of days of data (1-10)
    - **source**: Satellite data source
    """
    try:
        hotspots = await fetch_country_hotspots(country_code.upper(), days, source.value)

        return HotspotsListResponse(
            count=len(hotspots),
            source=source.value,
            query_time=datetime.utcnow().isoformat(),
            hotspots=[HotspotResponse(**h) for h in hotspots],
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/hotspots/area", response_model=HotspotsListResponse, tags=["Hotspots"])
async def get_area_hotspots(
    west: float = Query(..., ge=-180, le=180, description="Western longitude"),
    south: float = Query(..., ge=-90, le=90, description="Southern latitude"),
    east: float = Query(..., ge=-180, le=180, description="Eastern longitude"),
    north: float = Query(..., ge=-90, le=90, description="Northern latitude"),
    days: int = Query(default=1, ge=1, le=10),
    source: DataSource = Query(default=DataSource.VIIRS_NOAA20_NRT),
):
    """
    Get fire hotspots within a bounding box.

    Example for Sao Paulo region: west=-50, south=-25, east=-44, north=-19
    """
    try:
        hotspots = await fetch_area_hotspots(west, south, east, north, days, source.value)

        return HotspotsListResponse(
            count=len(hotspots),
            source=source.value,
            query_time=datetime.utcnow().isoformat(),
            hotspots=[HotspotResponse(**h) for h in hotspots],
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/stats/area", tags=["Statistics"])
async def get_area_stats(
    west: float = Query(..., ge=-180, le=180),
    south: float = Query(..., ge=-90, le=90),
    east: float = Query(..., ge=-180, le=180),
    north: float = Query(..., ge=-90, le=90),
    days: int = Query(default=1, ge=1, le=10),
):
    """Get fire statistics for a bounding box."""
    try:
        hotspots = await fetch_area_hotspots(west, south, east, north, days)

        if not hotspots:
            return {
                "total_count": 0,
                "high_confidence": 0,
                "average_frp": 0,
                "max_frp": 0,
                "daytime_count": 0,
                "nighttime_count": 0,
            }

        frp_values = [h["frp"] for h in hotspots if h["frp"] > 0]

        return {
            "total_count": len(hotspots),
            "high_confidence": sum(1 for h in hotspots if h["confidence"] in ["high", "h", "8", "9"]),
            "average_frp": round(sum(frp_values) / len(frp_values), 2) if frp_values else 0,
            "max_frp": max(frp_values) if frp_values else 0,
            "daytime_count": sum(1 for h in hotspots if h["daynight"] == "D"),
            "nighttime_count": sum(1 for h in hotspots if h["daynight"] == "N"),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
