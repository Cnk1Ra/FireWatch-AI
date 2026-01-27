"""
FireWatch AI - REST API

FastAPI application providing endpoints for fire hotspot data
and visualization.

Run with: uvicorn src.api.main:app --reload
"""

import os
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from src.ingestion.firms_client import FIRMSClient, DataSource

# Configuration
FIRMS_API_KEY = os.getenv("FIRMS_API_KEY", "")

# FastAPI app
app = FastAPI(
    title="FireWatch AI",
    description="Open-source global wildfire detection API combining NASA satellite data, crowdsourcing, and AI",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Pydantic Models
class HotspotResponse(BaseModel):
    """Single fire hotspot."""
    
    latitude: float
    longitude: float
    brightness: float
    frp: float = Field(description="Fire Radiative Power in MW")
    confidence: str
    datetime: str
    satellite: str
    instrument: str
    daynight: str


class HotspotsListResponse(BaseModel):
    """List of fire hotspots."""
    
    count: int
    source: str
    query_time: str
    hotspots: list[HotspotResponse]


class StatsResponse(BaseModel):
    """Statistics for hotspots."""
    
    total_count: int
    high_confidence: int
    average_frp: float
    max_frp: float
    daytime_count: int
    nighttime_count: int


class HealthResponse(BaseModel):
    """API health check response."""
    
    status: str
    version: str
    timestamp: str


# Helper function
def get_client() -> FIRMSClient:
    """Get FIRMS client with API key."""
    if not FIRMS_API_KEY:
        raise HTTPException(
            status_code=500,
            detail="FIRMS_API_KEY not configured. Set environment variable."
        )
    return FIRMSClient(FIRMS_API_KEY)


# Routes
@app.get("/", response_class=HTMLResponse)
async def root():
    """Welcome page."""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>FireWatch AI</title>
        <style>
            body { font-family: Arial; max-width: 800px; margin: 50px auto; padding: 20px; }
            h1 { color: #ff4444; }
            a { color: #ff6666; }
            code { background: #f0f0f0; padding: 2px 6px; border-radius: 3px; }
        </style>
    </head>
    <body>
        <h1>🔥 FireWatch AI</h1>
        <p>Open-source global wildfire detection platform</p>
        <h3>Quick Links</h3>
        <ul>
            <li><a href="/docs">📚 API Documentation (Swagger)</a></li>
            <li><a href="/redoc">📖 API Documentation (ReDoc)</a></li>
            <li><a href="/health">💚 Health Check</a></li>
        </ul>
        <h3>Example Endpoints</h3>
        <ul>
            <li><code>GET /api/v1/hotspots/country/BRA</code> - Brazil fires</li>
            <li><code>GET /api/v1/hotspots/area?west=-73&south=-33&east=-35&north=5</code> - Area query</li>
            <li><code>GET /api/v1/stats/country/BRA</code> - Brazil statistics</li>
        </ul>
        <hr>
        <p><a href="https://github.com/Cnk1Ra/FireWatch-AI">GitHub Repository</a></p>
    </body>
    </html>
    """


@app.get("/health", response_model=HealthResponse, tags=["System"])
async def health_check():
    """Check API health status."""
    return HealthResponse(
        status="healthy",
        version="0.1.0",
        timestamp=datetime.utcnow().isoformat(),
    )


@app.get("/api/v1/hotspots/country/{country_code}", response_model=HotspotsListResponse, tags=["Hotspots"])
async def get_country_hotspots(
    country_code: str,
    days: int = Query(default=1, ge=1, le=10, description="Number of days (1-10)"),
    source: DataSource = Query(default=DataSource.VIIRS_NOAA20_NRT, description="Satellite source"),
):
    """
    Get fire hotspots for a specific country.
    
    - **country_code**: ISO 3166-1 alpha-3 code (e.g., BRA, USA, AUS)
    - **days**: Number of days of data (1-10)
    - **source**: Satellite data source
    """
    try:
        client = get_client()
        hotspots = client.get_country_hotspots(country_code.upper(), days, source)
        
        return HotspotsListResponse(
            count=len(hotspots),
            source=source.value,
            query_time=datetime.utcnow().isoformat(),
            hotspots=[
                HotspotResponse(
                    latitude=h.latitude,
                    longitude=h.longitude,
                    brightness=h.brightness,
                    frp=h.frp,
                    confidence=h.confidence_level,
                    datetime=h.datetime.isoformat(),
                    satellite=h.satellite,
                    instrument=h.instrument,
                    daynight="day" if h.is_daytime else "night",
                )
                for h in hotspots
            ],
        )
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
    
    Coordinates are in decimal degrees.
    """
    try:
        client = get_client()
        hotspots = client.get_area_hotspots(west, south, east, north, days, source)
        
        return HotspotsListResponse(
            count=len(hotspots),
            source=source.value,
            query_time=datetime.utcnow().isoformat(),
            hotspots=[
                HotspotResponse(
                    latitude=h.latitude,
                    longitude=h.longitude,
                    brightness=h.brightness,
                    frp=h.frp,
                    confidence=h.confidence_level,
                    datetime=h.datetime.isoformat(),
                    satellite=h.satellite,
                    instrument=h.instrument,
                    daynight="day" if h.is_daytime else "night",
                )
                for h in hotspots
            ],
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/stats/country/{country_code}", response_model=StatsResponse, tags=["Statistics"])
async def get_country_stats(
    country_code: str,
    days: int = Query(default=1, ge=1, le=10),
    source: DataSource = Query(default=DataSource.VIIRS_NOAA20_NRT),
):
    """
    Get fire statistics for a country.
    """
    try:
        client = get_client()
        hotspots = client.get_country_hotspots(country_code.upper(), days, source)
        
        if not hotspots:
            return StatsResponse(
                total_count=0,
                high_confidence=0,
                average_frp=0,
                max_frp=0,
                daytime_count=0,
                nighttime_count=0,
            )
        
        frp_values = [h.frp for h in hotspots]
        
        return StatsResponse(
            total_count=len(hotspots),
            high_confidence=sum(1 for h in hotspots if h.confidence == "h"),
            average_frp=sum(frp_values) / len(frp_values),
            max_frp=max(frp_values),
            daytime_count=sum(1 for h in hotspots if h.is_daytime),
            nighttime_count=sum(1 for h in hotspots if not h.is_daytime),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
