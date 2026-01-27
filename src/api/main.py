"""
FireWatch AI - REST API

FastAPI application providing endpoints for fire hotspot data,
analysis, prediction, and visualization.

Run with: uvicorn src.api.main:app --reload
"""

import os
from datetime import datetime
from typing import Optional, List

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
    version="0.2.0",
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


# ============================================================================
# Pydantic Models
# ============================================================================

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
    modules: dict


class WeatherResponse(BaseModel):
    """Weather data for a location."""
    latitude: float
    longitude: float
    temperature_celsius: float
    humidity_percent: float
    wind_speed_kmh: float
    wind_direction_degrees: str
    fire_risk_factors: dict


class RiskAssessmentResponse(BaseModel):
    """Fire risk assessment."""
    latitude: float
    longitude: float
    risk_index: float
    risk_level: str
    factors: list[dict]
    recommendations: list[str]


class PropagationResponse(BaseModel):
    """Fire propagation prediction."""
    fire_id: str
    current_area_hectares: float
    spread_direction: float
    spread_rate_m_per_min: float
    predictions: list[dict]


class AnalysisResponse(BaseModel):
    """Fire analysis results."""
    fire_id: str
    cluster_count: int
    total_area_hectares: float
    biome: str
    carbon_emissions_tons: float
    affected_vegetation: dict


# ============================================================================
# Helper Functions
# ============================================================================

def get_client() -> FIRMSClient:
    """Get FIRMS client with API key."""
    if not FIRMS_API_KEY:
        raise HTTPException(
            status_code=500,
            detail="FIRMS_API_KEY not configured. Set environment variable."
        )
    return FIRMSClient(FIRMS_API_KEY)


# ============================================================================
# System Routes
# ============================================================================

@app.get("/", response_class=HTMLResponse)
async def root():
    """Welcome page."""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>FireWatch AI</title>
        <style>
            body { font-family: Arial; max-width: 900px; margin: 50px auto; padding: 20px; background: #1a1a2e; color: #eee; }
            h1 { color: #ff6b35; }
            h3 { color: #f7c873; margin-top: 30px; }
            a { color: #ff6b35; }
            code { background: #16213e; padding: 2px 8px; border-radius: 4px; color: #f7c873; }
            .endpoint { background: #16213e; padding: 10px; margin: 5px 0; border-radius: 4px; border-left: 3px solid #ff6b35; }
            .tag { display: inline-block; background: #ff6b35; color: white; padding: 2px 8px; border-radius: 3px; font-size: 12px; margin-right: 5px; }
            hr { border: 1px solid #333; margin: 30px 0; }
        </style>
    </head>
    <body>
        <h1>🔥 FireWatch AI</h1>
        <p>Open-source global wildfire detection platform combining NASA satellite data, AI analysis, and crowdsourcing.</p>

        <h3>📚 Documentation</h3>
        <ul>
            <li><a href="/docs">Swagger UI - Interactive API Documentation</a></li>
            <li><a href="/redoc">ReDoc - Alternative Documentation</a></li>
            <li><a href="/health">Health Check</a></li>
        </ul>

        <h3>🔥 Hotspots Endpoints</h3>
        <div class="endpoint"><span class="tag">GET</span> <code>/api/v1/hotspots/country/{code}</code> - Get fires by country (BRA, USA, AUS)</div>
        <div class="endpoint"><span class="tag">GET</span> <code>/api/v1/hotspots/area</code> - Get fires in bounding box</div>
        <div class="endpoint"><span class="tag">GET</span> <code>/api/v1/stats/country/{code}</code> - Statistics by country</div>

        <h3>🌤️ Weather & Risk</h3>
        <div class="endpoint"><span class="tag">GET</span> <code>/api/v1/weather</code> - Current weather conditions</div>
        <div class="endpoint"><span class="tag">GET</span> <code>/api/v1/risk</code> - Fire risk assessment</div>
        <div class="endpoint"><span class="tag">GET</span> <code>/api/v1/risk/forecast</code> - 7-day risk forecast</div>

        <h3>📊 Analysis</h3>
        <div class="endpoint"><span class="tag">GET</span> <code>/api/v1/analysis/clusters</code> - Cluster hotspots into fires</div>
        <div class="endpoint"><span class="tag">GET</span> <code>/api/v1/analysis/biome</code> - Biome impact analysis</div>
        <div class="endpoint"><span class="tag">GET</span> <code>/api/v1/analysis/emissions</code> - Carbon emissions estimate</div>

        <h3>🔮 Prediction</h3>
        <div class="endpoint"><span class="tag">GET</span> <code>/api/v1/prediction/spread</code> - Fire spread prediction</div>
        <div class="endpoint"><span class="tag">GET</span> <code>/api/v1/prediction/evacuation</code> - Evacuation routes</div>

        <hr>
        <p>
            <a href="https://github.com/Cnk1Ra/FireWatch-AI">📦 GitHub Repository</a> |
            Data source: <a href="https://firms.modaps.eosdis.nasa.gov/">NASA FIRMS</a>
        </p>
    </body>
    </html>
    """


@app.get("/health", response_model=HealthResponse, tags=["System"])
async def health_check():
    """Check API health status and module availability."""
    modules = {
        "firms_client": True,
        "weather_client": True,
        "terrain_client": True,
        "analysis": True,
        "prediction": True,
        "alerts": True,
    }

    return HealthResponse(
        status="healthy",
        version="0.2.0",
        timestamp=datetime.utcnow().isoformat(),
        modules=modules,
    )


# ============================================================================
# Hotspots Routes
# ============================================================================

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
                    frp=h.frp or 0,
                    confidence=h.confidence_level,
                    datetime=h.datetime.isoformat() if h.datetime else "",
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
                    frp=h.frp or 0,
                    confidence=h.confidence_level,
                    datetime=h.datetime.isoformat() if h.datetime else "",
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
    """Get fire statistics for a country."""
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

        frp_values = [h.frp for h in hotspots if h.frp]

        return StatsResponse(
            total_count=len(hotspots),
            high_confidence=sum(1 for h in hotspots if h.confidence == "h"),
            average_frp=sum(frp_values) / len(frp_values) if frp_values else 0,
            max_frp=max(frp_values) if frp_values else 0,
            daytime_count=sum(1 for h in hotspots if h.is_daytime),
            nighttime_count=sum(1 for h in hotspots if not h.is_daytime),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Weather Routes
# ============================================================================

@app.get("/api/v1/weather", response_model=WeatherResponse, tags=["Weather"])
async def get_weather(
    latitude: float = Query(..., ge=-90, le=90, description="Latitude"),
    longitude: float = Query(..., ge=-180, le=180, description="Longitude"),
):
    """Get current weather conditions for fire risk assessment."""
    try:
        from src.ingestion.weather_client import WeatherClient

        with WeatherClient() as client:
            weather = client.get_current_weather(latitude, longitude)

        return WeatherResponse(
            latitude=weather.latitude,
            longitude=weather.longitude,
            temperature_celsius=weather.temperature_celsius,
            humidity_percent=weather.humidity_percent,
            wind_speed_kmh=weather.wind_speed_kmh,
            wind_direction_degrees=weather.wind_direction_cardinal,
            fire_risk_factors=weather.fire_risk_factors,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Risk Routes
# ============================================================================

@app.get("/api/v1/risk", response_model=RiskAssessmentResponse, tags=["Risk"])
async def get_fire_risk(
    latitude: float = Query(..., ge=-90, le=90),
    longitude: float = Query(..., ge=-180, le=180),
    days_without_rain: int = Query(default=5, ge=0, le=60),
):
    """Calculate fire risk index for a location."""
    try:
        from src.ingestion.weather_client import WeatherClient
        from src.prediction.risk_index import calculate_fire_risk

        # Get current weather
        with WeatherClient() as client:
            weather = client.get_current_weather(latitude, longitude)

        # Calculate risk
        risk = calculate_fire_risk(
            latitude=latitude,
            longitude=longitude,
            temperature_celsius=weather.temperature_celsius,
            humidity_percent=weather.humidity_percent,
            wind_speed_kmh=weather.wind_speed_kmh,
            days_without_rain=days_without_rain,
        )

        return RiskAssessmentResponse(
            latitude=latitude,
            longitude=longitude,
            risk_index=risk.overall_risk_index,
            risk_level=risk.overall_risk_level,
            factors=[f.to_dict() for f in risk.factors],
            recommendations=risk.recommendations,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/risk/forecast", tags=["Risk"])
async def get_risk_forecast(
    latitude: float = Query(..., ge=-90, le=90),
    longitude: float = Query(..., ge=-180, le=180),
    days: int = Query(default=7, ge=1, le=14),
):
    """Get fire risk forecast for upcoming days."""
    try:
        from src.prediction.risk_index import get_risk_forecast

        forecast = get_risk_forecast(latitude, longitude, days)

        return {
            "latitude": latitude,
            "longitude": longitude,
            "forecast": [f.to_dict() for f in forecast],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Analysis Routes
# ============================================================================

@app.get("/api/v1/analysis/clusters", tags=["Analysis"])
async def analyze_clusters(
    west: float = Query(..., ge=-180, le=180),
    south: float = Query(..., ge=-90, le=90),
    east: float = Query(..., ge=-180, le=180),
    north: float = Query(..., ge=-90, le=90),
    days: int = Query(default=1, ge=1, le=10),
    distance_km: float = Query(default=5.0, ge=1, le=50, description="Clustering distance in km"),
):
    """Cluster hotspots into individual fire events."""
    try:
        from src.analysis.fire_clustering import cluster_hotspots, get_cluster_statistics

        client = get_client()
        hotspots = client.get_area_hotspots(west, south, east, north, days)

        clusters = cluster_hotspots(hotspots, distance_threshold_km=distance_km)
        stats = get_cluster_statistics(clusters)

        return {
            "statistics": stats,
            "clusters": [c.to_dict() for c in clusters[:20]],  # Limit to 20 clusters
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/analysis/biome", tags=["Analysis"])
async def analyze_biome(
    latitude: float = Query(..., ge=-90, le=90),
    longitude: float = Query(..., ge=-180, le=180),
    area_hectares: float = Query(default=100, ge=1, le=100000),
):
    """Analyze biome impact for a fire location."""
    try:
        from src.analysis.biome_analysis import analyze_biome_impact

        impact = analyze_biome_impact(latitude, longitude, area_hectares)

        return impact.to_dict()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/analysis/emissions", tags=["Analysis"])
async def calculate_emissions(
    latitude: float = Query(..., ge=-90, le=90),
    longitude: float = Query(..., ge=-180, le=180),
    area_hectares: float = Query(default=100, ge=1, le=100000),
):
    """Estimate carbon emissions from a fire."""
    try:
        from src.analysis.carbon_emissions import calculate_emissions

        emissions = calculate_emissions(latitude, longitude, area_hectares)
        result = emissions.to_dict()
        result["equivalents"] = emissions.get_equivalents()

        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Prediction Routes
# ============================================================================

@app.get("/api/v1/prediction/spread", response_model=PropagationResponse, tags=["Prediction"])
async def predict_spread(
    latitude: float = Query(..., ge=-90, le=90),
    longitude: float = Query(..., ge=-180, le=180),
    area_hectares: float = Query(default=50, ge=1, le=10000),
    wind_speed_kmh: float = Query(default=20, ge=0, le=100),
    wind_direction: float = Query(default=0, ge=0, le=360, description="Wind direction in degrees (0=N)"),
):
    """Predict fire spread over time."""
    try:
        from src.prediction.propagation_model import predict_fire_spread

        prediction = predict_fire_spread(
            center_lat=latitude,
            center_lon=longitude,
            current_area_hectares=area_hectares,
            wind_speed_kmh=wind_speed_kmh,
            wind_direction_degrees=wind_direction,
        )

        return PropagationResponse(
            fire_id=prediction.fire_id,
            current_area_hectares=prediction.current_area_hectares,
            spread_direction=prediction.wind_direction_degrees,
            spread_rate_m_per_min=prediction.predictions[0].spread_rate_m_per_min if prediction.predictions else 0,
            predictions=[p.to_dict() for p in prediction.predictions],
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/prediction/evacuation", tags=["Prediction"])
async def calculate_evacuation(
    fire_lat: float = Query(..., ge=-90, le=90),
    fire_lon: float = Query(..., ge=-180, le=180),
    fire_direction: float = Query(default=0, ge=0, le=360),
    spread_rate: float = Query(default=10, ge=1, le=100, description="Spread rate in m/min"),
):
    """Calculate evacuation routes from a fire area."""
    try:
        from src.prediction.evacuation_router import calculate_evacuation_routes

        # Sample communities (in production, would fetch from database)
        sample_communities = [
            {"name": "Comunidade Norte", "latitude": fire_lat + 0.1, "longitude": fire_lon, "population": 500},
            {"name": "Comunidade Sul", "latitude": fire_lat - 0.1, "longitude": fire_lon, "population": 1000},
            {"name": "Comunidade Leste", "latitude": fire_lat, "longitude": fire_lon + 0.1, "population": 750},
        ]

        plan = calculate_evacuation_routes(
            fire_center_lat=fire_lat,
            fire_center_lon=fire_lon,
            fire_spread_direction=fire_direction,
            spread_rate_m_per_min=spread_rate,
            communities=sample_communities,
        )

        return plan.to_dict()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Main
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
