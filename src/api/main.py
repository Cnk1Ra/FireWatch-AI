"""
FireWatch AI - REST API

FastAPI application providing endpoints for fire hotspot data,
analysis, prediction, and visualization.

Run with: uvicorn src.api.main:app --reload
"""

import os
from datetime import datetime
from typing import Optional, List

from fastapi import FastAPI, HTTPException, Query, File, UploadFile, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from src.ingestion.firms_client import FIRMSClient, DataSource
from src.crowdsource.report_handler import ReportHandler, FireReport, ReportStatus
from src.crowdsource.validation import ReportValidator, validate_report
from src.alerts.alert_manager import AlertManager, AlertLevel, AlertChannel, create_fire_alert
from src.visualization.map_generator import create_fire_map

# Configuration
FIRMS_API_KEY = os.getenv("FIRMS_API_KEY", "")

# FastAPI app
app = FastAPI(
    title="FireWatch AI",
    description="Open-source global wildfire detection API combining NASA satellite data, crowdsourcing, and AI",
    version="0.3.0",
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


# Crowdsource Models
class ReportCreateRequest(BaseModel):
    """Request to create a fire report."""
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    description: Optional[str] = None
    has_flames: bool = True
    has_smoke: bool = True
    estimated_size: str = Field(default="medium", pattern="^(small|medium|large|very_large)$")
    fire_type: str = Field(default="vegetation", pattern="^(vegetation|structure|vehicle|other)$")
    reporter_name: Optional[str] = None
    reporter_phone: Optional[str] = None
    reporter_email: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    reference_point: Optional[str] = None


class ReportResponse(BaseModel):
    """Fire report response."""
    id: str
    latitude: float
    longitude: float
    description: Optional[str]
    status: str
    priority: str
    has_flames: bool
    has_smoke: bool
    estimated_size: str
    fire_type: str
    ml_confidence: Optional[float]
    validated_by_satellite: bool
    reported_at: str
    address: Optional[str]
    city: Optional[str]
    state: Optional[str]


class ReportListResponse(BaseModel):
    """List of fire reports."""
    count: int
    pending_count: int
    reports: List[ReportResponse]


class ReportStatsResponse(BaseModel):
    """Report statistics."""
    total_reports: int
    pending_count: int
    by_status: dict
    by_priority: dict
    validated_by_satellite: int
    with_photo: int
    validation_rate: float


# Alert Models
class AlertCreateRequest(BaseModel):
    """Request to create an alert."""
    fire_id: str
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    area_hectares: float = Field(default=100, ge=1)
    region: str
    risk_level: str = Field(default="high", pattern="^(low|moderate|high|very_high|extreme)$")
    population: int = Field(default=0, ge=0)
    custom_message: Optional[str] = None


class AlertResponse(BaseModel):
    """Alert response."""
    alert_id: str
    fire_id: str
    level: str
    title: str
    message: str
    created_at: str
    fire_latitude: float
    fire_longitude: float
    fire_area_hectares: float
    affected_region: str
    affected_population: int
    evacuation_recommended: bool
    delivery_status: str


class AlertSendRequest(BaseModel):
    """Request to send an alert."""
    channels: List[str] = Field(default=["email", "dashboard"])


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


# Global instances for stateful services
_report_handler = ReportHandler()
_alert_manager = AlertManager()


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

        <h3>👥 Crowdsource</h3>
        <div class="endpoint"><span class="tag">POST</span> <code>/api/v1/reports</code> - Submit fire report</div>
        <div class="endpoint"><span class="tag">POST</span> <code>/api/v1/reports/with-photo</code> - Submit report with photo</div>
        <div class="endpoint"><span class="tag">GET</span> <code>/api/v1/reports</code> - List all reports</div>
        <div class="endpoint"><span class="tag">GET</span> <code>/api/v1/reports/{id}</code> - Get report details</div>
        <div class="endpoint"><span class="tag">PUT</span> <code>/api/v1/reports/{id}/status</code> - Update report status</div>

        <h3>🚨 Alerts</h3>
        <div class="endpoint"><span class="tag">POST</span> <code>/api/v1/alerts</code> - Create fire alert</div>
        <div class="endpoint"><span class="tag">GET</span> <code>/api/v1/alerts</code> - List active alerts</div>
        <div class="endpoint"><span class="tag">POST</span> <code>/api/v1/alerts/{id}/send</code> - Send alert (email/SMS)</div>

        <h3>🗺️ Interactive Maps</h3>
        <div class="endpoint"><span class="tag">GET</span> <code>/api/v1/map/country/{code}</code> - Country fire map</div>
        <div class="endpoint"><span class="tag">GET</span> <code>/api/v1/map/area</code> - Area fire map</div>
        <div class="endpoint"><span class="tag">GET</span> <code>/api/v1/map/reports</code> - Crowdsourced reports map</div>

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
        version="0.3.0",
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
# Crowdsource Routes
# ============================================================================

@app.post("/api/v1/reports", response_model=ReportResponse, tags=["Crowdsource"])
async def create_report(request: ReportCreateRequest):
    """
    Create a new fire report from citizen.

    Submit a fire sighting with location, description, and fire characteristics.
    The report will be validated against satellite data and other reports.
    """
    try:
        reporter_info = None
        if request.reporter_name or request.reporter_phone or request.reporter_email:
            reporter_info = {
                "name": request.reporter_name,
                "phone": request.reporter_phone,
                "email": request.reporter_email,
                "anonymous": not request.reporter_name,
            }

        report = _report_handler.create_report(
            latitude=request.latitude,
            longitude=request.longitude,
            description=request.description,
            has_flames=request.has_flames,
            has_smoke=request.has_smoke,
            estimated_size=request.estimated_size,
            fire_type=request.fire_type,
            address=request.address,
            city=request.city,
            state=request.state,
            reference_point=request.reference_point,
            reporter_info=reporter_info,
        )

        # Auto-validate with satellite data
        validation = validate_report(
            latitude=report.latitude,
            longitude=report.longitude,
            reported_at=report.reported_at,
        )

        if validation.satellite_match:
            _report_handler.link_to_hotspot(report.id, validation.matched_hotspot_id or 0)

        if validation.confidence:
            _report_handler.set_ml_confidence(report.id, validation.confidence)

        return ReportResponse(
            id=report.id,
            latitude=report.latitude,
            longitude=report.longitude,
            description=report.description,
            status=report.status.value,
            priority=report.priority.value,
            has_flames=report.has_flames,
            has_smoke=report.has_smoke,
            estimated_size=report.estimated_size,
            fire_type=report.fire_type,
            ml_confidence=report.ml_confidence,
            validated_by_satellite=report.validated_by_satellite,
            reported_at=report.reported_at.isoformat(),
            address=report.address,
            city=report.city,
            state=report.state,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/reports/with-photo", response_model=ReportResponse, tags=["Crowdsource"])
async def create_report_with_photo(
    latitude: float = Form(...),
    longitude: float = Form(...),
    description: Optional[str] = Form(None),
    has_flames: bool = Form(True),
    has_smoke: bool = Form(True),
    estimated_size: str = Form("medium"),
    fire_type: str = Form("vegetation"),
    photo: UploadFile = File(...),
):
    """
    Create a fire report with photo attachment.

    The photo will be analyzed using computer vision to validate fire/smoke presence.
    """
    try:
        photo_data = await photo.read()

        report = _report_handler.create_report(
            latitude=latitude,
            longitude=longitude,
            description=description,
            has_flames=has_flames,
            has_smoke=has_smoke,
            estimated_size=estimated_size,
            fire_type=fire_type,
            photo_data=photo_data,
        )

        # Analyze photo
        from src.crowdsource.photo_analyzer import analyze_fire_photo
        analysis = analyze_fire_photo(photo_data)

        # Update report with photo analysis
        if analysis.confidence:
            _report_handler.set_ml_confidence(report.id, analysis.confidence)

        # Validate with satellite
        validation = validate_report(
            latitude=report.latitude,
            longitude=report.longitude,
            reported_at=report.reported_at,
            photo_data=photo_data,
        )

        if validation.satellite_match:
            _report_handler.link_to_hotspot(report.id, validation.matched_hotspot_id or 0)

        return ReportResponse(
            id=report.id,
            latitude=report.latitude,
            longitude=report.longitude,
            description=report.description,
            status=report.status.value,
            priority=report.priority.value,
            has_flames=report.has_flames or analysis.has_fire,
            has_smoke=report.has_smoke or analysis.has_smoke,
            estimated_size=report.estimated_size,
            fire_type=report.fire_type,
            ml_confidence=report.ml_confidence,
            validated_by_satellite=report.validated_by_satellite,
            reported_at=report.reported_at.isoformat(),
            address=report.address,
            city=report.city,
            state=report.state,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/reports", response_model=ReportListResponse, tags=["Crowdsource"])
async def list_reports(
    status: Optional[str] = Query(None, description="Filter by status"),
    west: Optional[float] = Query(None, ge=-180, le=180),
    south: Optional[float] = Query(None, ge=-90, le=90),
    east: Optional[float] = Query(None, ge=-180, le=180),
    north: Optional[float] = Query(None, ge=-90, le=90),
    limit: int = Query(default=50, ge=1, le=200),
):
    """
    List fire reports with optional filters.

    Filter by status (pending, validated, rejected) or geographic area.
    """
    try:
        if west is not None and south is not None and east is not None and north is not None:
            reports = _report_handler.get_reports_in_area(west, south, east, north)
        elif status == "pending":
            reports = _report_handler.get_pending_reports()
        else:
            reports = list(_report_handler._reports.values())

        # Apply limit
        reports = reports[:limit]

        return ReportListResponse(
            count=len(reports),
            pending_count=_report_handler._pending_count,
            reports=[
                ReportResponse(
                    id=r.id,
                    latitude=r.latitude,
                    longitude=r.longitude,
                    description=r.description,
                    status=r.status.value,
                    priority=r.priority.value,
                    has_flames=r.has_flames,
                    has_smoke=r.has_smoke,
                    estimated_size=r.estimated_size,
                    fire_type=r.fire_type,
                    ml_confidence=r.ml_confidence,
                    validated_by_satellite=r.validated_by_satellite,
                    reported_at=r.reported_at.isoformat(),
                    address=r.address,
                    city=r.city,
                    state=r.state,
                )
                for r in reports
            ],
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/reports/{report_id}", response_model=ReportResponse, tags=["Crowdsource"])
async def get_report(report_id: str):
    """Get a specific fire report by ID."""
    report = _report_handler.get_report(report_id)

    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    return ReportResponse(
        id=report.id,
        latitude=report.latitude,
        longitude=report.longitude,
        description=report.description,
        status=report.status.value,
        priority=report.priority.value,
        has_flames=report.has_flames,
        has_smoke=report.has_smoke,
        estimated_size=report.estimated_size,
        fire_type=report.fire_type,
        ml_confidence=report.ml_confidence,
        validated_by_satellite=report.validated_by_satellite,
        reported_at=report.reported_at.isoformat(),
        address=report.address,
        city=report.city,
        state=report.state,
    )


@app.put("/api/v1/reports/{report_id}/status", response_model=ReportResponse, tags=["Crowdsource"])
async def update_report_status(
    report_id: str,
    status: str = Query(..., description="New status: pending, validated, rejected, duplicate"),
    notes: Optional[str] = Query(None, description="Validation notes"),
):
    """Update the status of a fire report."""
    try:
        status_enum = ReportStatus(status)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid status: {status}")

    report = _report_handler.update_status(report_id, status_enum, notes=notes)

    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    return ReportResponse(
        id=report.id,
        latitude=report.latitude,
        longitude=report.longitude,
        description=report.description,
        status=report.status.value,
        priority=report.priority.value,
        has_flames=report.has_flames,
        has_smoke=report.has_smoke,
        estimated_size=report.estimated_size,
        fire_type=report.fire_type,
        ml_confidence=report.ml_confidence,
        validated_by_satellite=report.validated_by_satellite,
        reported_at=report.reported_at.isoformat(),
        address=report.address,
        city=report.city,
        state=report.state,
    )


@app.get("/api/v1/reports/stats/summary", response_model=ReportStatsResponse, tags=["Crowdsource"])
async def get_report_stats():
    """Get statistics for all fire reports."""
    stats = _report_handler.get_statistics()

    return ReportStatsResponse(
        total_reports=stats["total_reports"],
        pending_count=stats["pending_count"],
        by_status=stats["by_status"],
        by_priority=stats["by_priority"],
        validated_by_satellite=stats["validated_by_satellite"],
        with_photo=stats["with_photo"],
        validation_rate=stats["validation_rate"],
    )


# ============================================================================
# Alert Routes
# ============================================================================

@app.post("/api/v1/alerts", response_model=AlertResponse, tags=["Alerts"])
async def create_alert(request: AlertCreateRequest):
    """
    Create a new fire alert.

    Creates an alert based on fire location and risk level.
    The alert can then be sent through various channels.
    """
    try:
        # Map risk level to alert level
        level_map = {
            "low": AlertLevel.INFO,
            "moderate": AlertLevel.WARNING,
            "high": AlertLevel.ALERT,
            "very_high": AlertLevel.CRITICAL,
            "extreme": AlertLevel.EMERGENCY,
        }
        alert_level = level_map.get(request.risk_level, AlertLevel.ALERT)

        alert = _alert_manager.create_alert(
            fire_id=request.fire_id,
            level=alert_level,
            fire_lat=request.latitude,
            fire_lon=request.longitude,
            fire_area=request.area_hectares,
            region=request.region,
            population=request.population,
            evacuation=request.risk_level in ["very_high", "extreme"],
            custom_message=request.custom_message,
        )

        return AlertResponse(
            alert_id=alert.alert_id,
            fire_id=alert.fire_id,
            level=alert.level.value,
            title=alert.title,
            message=alert.message,
            created_at=alert.created_at.isoformat(),
            fire_latitude=alert.fire_latitude,
            fire_longitude=alert.fire_longitude,
            fire_area_hectares=alert.fire_area_hectares,
            affected_region=alert.affected_region,
            affected_population=alert.affected_population,
            evacuation_recommended=alert.evacuation_recommended,
            delivery_status=alert.delivery_status,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/alerts", tags=["Alerts"])
async def list_alerts(
    active_only: bool = Query(default=True, description="Only show active alerts"),
):
    """List all alerts."""
    try:
        if active_only:
            alerts = _alert_manager.get_active_alerts()
        else:
            alerts = list(_alert_manager.alerts.values())

        return {
            "count": len(alerts),
            "alerts": [
                AlertResponse(
                    alert_id=a.alert_id,
                    fire_id=a.fire_id,
                    level=a.level.value,
                    title=a.title,
                    message=a.message,
                    created_at=a.created_at.isoformat(),
                    fire_latitude=a.fire_latitude,
                    fire_longitude=a.fire_longitude,
                    fire_area_hectares=a.fire_area_hectares,
                    affected_region=a.affected_region,
                    affected_population=a.affected_population,
                    evacuation_recommended=a.evacuation_recommended,
                    delivery_status=a.delivery_status,
                )
                for a in alerts
            ],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/alerts/{alert_id}", response_model=AlertResponse, tags=["Alerts"])
async def get_alert(alert_id: str):
    """Get a specific alert by ID."""
    alert = _alert_manager.get_alert(alert_id)

    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    return AlertResponse(
        alert_id=alert.alert_id,
        fire_id=alert.fire_id,
        level=alert.level.value,
        title=alert.title,
        message=alert.message,
        created_at=alert.created_at.isoformat(),
        fire_latitude=alert.fire_latitude,
        fire_longitude=alert.fire_longitude,
        fire_area_hectares=alert.fire_area_hectares,
        affected_region=alert.affected_region,
        affected_population=alert.affected_population,
        evacuation_recommended=alert.evacuation_recommended,
        delivery_status=alert.delivery_status,
    )


@app.post("/api/v1/alerts/{alert_id}/send", tags=["Alerts"])
async def send_alert(alert_id: str, request: AlertSendRequest):
    """
    Send an alert through specified channels.

    Available channels: email, sms, push, webhook, dashboard
    """
    alert = _alert_manager.get_alert(alert_id)

    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    try:
        channels = [AlertChannel(c) for c in request.channels]
        results = _alert_manager.send_alert(alert, channels)

        return {
            "alert_id": alert_id,
            "results": results,
            "message": f"Alert sent to {results['total_sent']} recipients",
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid channel: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Map Routes
# ============================================================================

@app.get("/api/v1/map/country/{country_code}", response_class=HTMLResponse, tags=["Map"])
async def get_country_map(
    country_code: str,
    days: int = Query(default=1, ge=1, le=10),
    show_heatmap: bool = Query(default=True),
    show_markers: bool = Query(default=True),
):
    """
    Generate an interactive fire map for a country.

    Returns an HTML page with a Leaflet map showing fire hotspots.
    """
    try:
        client = get_client()
        hotspots = client.get_country_hotspots(country_code.upper(), days)

        fire_map = create_fire_map(
            hotspots=hotspots,
            title=f"FireWatch AI - {country_code.upper()} Active Fires ({len(hotspots)} hotspots)",
            show_heatmap=show_heatmap,
            show_markers=show_markers,
        )

        return fire_map._repr_html_()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/map/area", response_class=HTMLResponse, tags=["Map"])
async def get_area_map(
    west: float = Query(..., ge=-180, le=180),
    south: float = Query(..., ge=-90, le=90),
    east: float = Query(..., ge=-180, le=180),
    north: float = Query(..., ge=-90, le=90),
    days: int = Query(default=1, ge=1, le=10),
    show_heatmap: bool = Query(default=True),
    show_markers: bool = Query(default=True),
):
    """
    Generate an interactive fire map for a geographic area.

    Returns an HTML page with a Leaflet map showing fire hotspots.
    """
    try:
        client = get_client()
        hotspots = client.get_area_hotspots(west, south, east, north, days)

        center = ((south + north) / 2, (west + east) / 2)

        fire_map = create_fire_map(
            hotspots=hotspots,
            center=center,
            title=f"FireWatch AI - Area Map ({len(hotspots)} hotspots)",
            show_heatmap=show_heatmap,
            show_markers=show_markers,
        )

        return fire_map._repr_html_()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/map/reports", response_class=HTMLResponse, tags=["Map"])
async def get_reports_map():
    """
    Generate a map showing all crowdsourced fire reports.

    Shows both validated and pending reports with different colors.
    """
    try:
        import folium
        from folium.plugins import MarkerCluster

        reports = list(_report_handler._reports.values())

        if not reports:
            # Empty map centered on Brazil
            return folium.Map(location=[-14.235, -51.925], zoom_start=4)._repr_html_()

        # Calculate center
        lats = [r.latitude for r in reports]
        lons = [r.longitude for r in reports]
        center = (sum(lats) / len(lats), sum(lons) / len(lons))

        # Create map
        report_map = folium.Map(
            location=center,
            zoom_start=5,
            tiles="CartoDB dark_matter",
        )

        # Add markers
        marker_cluster = MarkerCluster(name="Fire Reports")

        status_colors = {
            "pending": "orange",
            "validated": "green",
            "rejected": "red",
            "duplicate": "gray",
        }

        for report in reports:
            color = status_colors.get(report.status.value, "blue")

            popup_html = f"""
            <div style="font-family: Arial; min-width: 200px;">
                <h4 style="margin: 0;">Report #{report.id}</h4>
                <hr style="margin: 5px 0;">
                <b>Status:</b> {report.status.value}<br>
                <b>Priority:</b> {report.priority.value}<br>
                <b>Type:</b> {report.fire_type}<br>
                <b>Size:</b> {report.estimated_size}<br>
                <b>Location:</b> {report.latitude:.4f}, {report.longitude:.4f}<br>
                <b>Time:</b> {report.reported_at.strftime("%Y-%m-%d %H:%M")}<br>
                {f"<b>Description:</b> {report.description}<br>" if report.description else ""}
            </div>
            """

            folium.CircleMarker(
                location=[report.latitude, report.longitude],
                radius=10,
                popup=folium.Popup(popup_html, max_width=300),
                color=color,
                fill=True,
                fill_color=color,
                fill_opacity=0.7,
            ).add_to(marker_cluster)

        marker_cluster.add_to(report_map)

        # Add legend
        legend_html = '''
        <div style="position: fixed; bottom: 30px; right: 30px;
                    background-color: rgba(0,0,0,0.8); padding: 10px;
                    border-radius: 5px; z-index: 9999; color: white;">
            <b>Report Status</b><br>
            <span style="color: orange;">●</span> Pending<br>
            <span style="color: green;">●</span> Validated<br>
            <span style="color: red;">●</span> Rejected<br>
            <span style="color: gray;">●</span> Duplicate
        </div>
        '''
        report_map.get_root().html.add_child(folium.Element(legend_html))

        return report_map._repr_html_()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Main
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
