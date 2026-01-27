"""
FireWatch AI - Complete Dashboard API
All features: hotspots, weather, risk, spread prediction, emissions, evacuation
"""

import json
import os
import math
from urllib.request import urlopen, Request
from urllib.parse import parse_qs, urlparse
from http.server import BaseHTTPRequestHandler
from datetime import datetime

FIRMS_API_KEY = os.environ.get("FIRMS_API_KEY", "")
FIRMS_BASE_URL = "https://firms.modaps.eosdis.nasa.gov/api"
WEATHER_API_URL = "https://api.open-meteo.com/v1/forecast"

# ============================================================================
# Biome Data
# ============================================================================
BIOMES = {
    "Amazonia": {
        "bounds": {"west": -74, "south": -10, "east": -44, "north": 5},
        "carbon_tons_ha": 225,
        "recovery_years": 50,
        "fuel_model": "floresta_densa",
        "spread_factor": 0.6
    },
    "Cerrado": {
        "bounds": {"west": -60, "south": -24, "east": -41, "north": -2},
        "carbon_tons_ha": 55,
        "recovery_years": 15,
        "fuel_model": "cerrado_tipico",
        "spread_factor": 1.2
    },
    "Pantanal": {
        "bounds": {"west": -59, "south": -22, "east": -54, "north": -15},
        "carbon_tons_ha": 70,
        "recovery_years": 10,
        "fuel_model": "pantanal",
        "spread_factor": 0.4
    },
    "Mata Atlantica": {
        "bounds": {"west": -55, "south": -30, "east": -34, "north": -3},
        "carbon_tons_ha": 150,
        "recovery_years": 40,
        "fuel_model": "floresta_aberta",
        "spread_factor": 0.8
    },
    "Caatinga": {
        "bounds": {"west": -46, "south": -17, "east": -35, "north": -2},
        "carbon_tons_ha": 30,
        "recovery_years": 20,
        "fuel_model": "caatinga",
        "spread_factor": 1.0
    },
    "Pampa": {
        "bounds": {"west": -58, "south": -34, "east": -49, "north": -28},
        "carbon_tons_ha": 20,
        "recovery_years": 5,
        "fuel_model": "cerrado_campo",
        "spread_factor": 1.5
    }
}

# ============================================================================
# Helper Functions
# ============================================================================

def get_biome(lat, lon):
    """Determine biome based on coordinates."""
    for name, data in BIOMES.items():
        b = data["bounds"]
        if b["west"] <= lon <= b["east"] and b["south"] <= lat <= b["north"]:
            return name, data
    return "Desconhecido", {"carbon_tons_ha": 50, "recovery_years": 20, "spread_factor": 1.0}


def calculate_risk_index(temp, humidity, wind_speed, days_without_rain):
    """Calculate fire risk index (0-100)."""
    # Temperature factor (0-25 points)
    temp_factor = min(25, max(0, (temp - 20) * 1.25)) if temp > 20 else 0

    # Humidity factor (0-25 points) - lower humidity = higher risk
    humidity_factor = max(0, 25 - (humidity * 0.3))

    # Wind factor (0-25 points)
    wind_factor = min(25, wind_speed * 0.5)

    # Drought factor (0-25 points)
    drought_factor = min(25, days_without_rain * 1.5)

    risk = temp_factor + humidity_factor + wind_factor + drought_factor
    return round(min(100, max(0, risk)), 1)


def get_risk_level(risk_index):
    """Get risk level from index."""
    if risk_index >= 80:
        return "CRITICO"
    elif risk_index >= 60:
        return "MUITO ALTO"
    elif risk_index >= 40:
        return "ALTO"
    elif risk_index >= 20:
        return "MODERADO"
    return "BAIXO"


def calculate_spread_rate(wind_speed, slope=0, fuel_moisture=0.1, spread_factor=1.0):
    """Calculate fire spread rate in m/min using simplified Rothermel."""
    base_rate = 2.0  # Base spread rate m/min
    wind_factor = 1 + (wind_speed / 10) * 0.5
    slope_factor = 1 + (slope / 100) * 0.3
    moisture_factor = max(0.1, 1 - fuel_moisture)

    rate = base_rate * wind_factor * slope_factor * moisture_factor * spread_factor
    return round(rate, 2)


def calculate_emissions(area_ha, carbon_tons_ha, combustion_factor=0.5):
    """Calculate carbon emissions from fire."""
    carbon_burned = area_ha * carbon_tons_ha * combustion_factor
    co2 = carbon_burned * 3.67  # CO2 conversion factor
    ch4 = carbon_burned * 0.012  # CH4 factor
    pm25 = carbon_burned * 0.015  # PM2.5 factor

    return {
        "carbon_burned_tons": round(carbon_burned, 1),
        "co2_tons": round(co2, 1),
        "ch4_tons": round(ch4, 2),
        "pm25_tons": round(pm25, 2),
        "cars_equivalent": round(co2 / 4.6, 0),  # Average car emits 4.6 tons/year
        "trees_to_offset": round(co2 / 0.022, 0)  # Tree absorbs ~22kg CO2/year
    }


def predict_fire_perimeter(center_lat, center_lon, area_ha, wind_direction, hours=6):
    """Predict fire perimeter over time."""
    predictions = []
    current_area = area_ha

    for hour in range(1, hours + 1):
        # Area grows with time (simplified model)
        growth_rate = 1.15 + (hour * 0.02)  # Accelerating growth
        current_area *= growth_rate

        # Calculate approximate radius
        radius_m = math.sqrt(current_area * 10000 / math.pi)

        # Calculate spread direction (wind pushes fire)
        wind_rad = math.radians(wind_direction)
        offset_lat = (radius_m / 111000) * math.cos(wind_rad) * 0.7
        offset_lon = (radius_m / (111000 * math.cos(math.radians(center_lat)))) * math.sin(wind_rad) * 0.7

        predictions.append({
            "hour": hour,
            "area_ha": round(current_area, 1),
            "radius_m": round(radius_m, 0),
            "center_lat": round(center_lat + offset_lat, 6),
            "center_lon": round(center_lon + offset_lon, 6)
        })

    return predictions


def parse_csv_hotspots(csv_text):
    """Parse FIRMS CSV response into hotspot list."""
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
                    "brightness": float(row.get("bright_ti4", 0) or row.get("brightness", 0) or 0),
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


def fetch_hotspots(west, south, east, north, days=1):
    """Fetch hotspots from NASA FIRMS API."""
    if not FIRMS_API_KEY:
        return None, "FIRMS_API_KEY not configured"

    url = "{}/area/csv/{}/VIIRS_NOAA20_NRT/{},{},{},{}/{}".format(
        FIRMS_BASE_URL, FIRMS_API_KEY, west, south, east, north, days
    )

    try:
        req = Request(url, headers={"User-Agent": "FireWatch-AI/1.0"})
        with urlopen(req, timeout=30) as response:
            data = response.read().decode("utf-8")
            return parse_csv_hotspots(data), None
    except Exception as e:
        return None, str(e)


def fetch_weather(lat, lon):
    """Fetch weather data from Open-Meteo API."""
    url = "{}?latitude={}&longitude={}&current=temperature_2m,relative_humidity_2m,wind_speed_10m,wind_direction_10m,precipitation&timezone=auto".format(
        WEATHER_API_URL, lat, lon
    )

    try:
        req = Request(url, headers={"User-Agent": "FireWatch-AI/1.0"})
        with urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode("utf-8"))
            current = data.get("current", {})
            return {
                "temperature": current.get("temperature_2m", 25),
                "humidity": current.get("relative_humidity_2m", 50),
                "wind_speed": current.get("wind_speed_10m", 10),
                "wind_direction": current.get("wind_direction_10m", 0),
                "precipitation": current.get("precipitation", 0)
            }, None
    except Exception as e:
        # Return default values if API fails
        return {
            "temperature": 28,
            "humidity": 45,
            "wind_speed": 15,
            "wind_direction": 90,
            "precipitation": 0
        }, str(e)


def cluster_hotspots(hotspots, distance_km=5):
    """Simple clustering algorithm for hotspots."""
    if not hotspots:
        return []

    clusters = []
    used = set()

    for i, h1 in enumerate(hotspots):
        if i in used:
            continue

        cluster = {
            "id": len(clusters) + 1,
            "hotspots": [h1],
            "center_lat": h1["latitude"],
            "center_lon": h1["longitude"],
            "total_frp": h1["frp"],
            "max_frp": h1["frp"],
            "count": 1
        }
        used.add(i)

        for j, h2 in enumerate(hotspots):
            if j in used:
                continue

            # Calculate distance
            dlat = h2["latitude"] - h1["latitude"]
            dlon = h2["longitude"] - h1["longitude"]
            dist = math.sqrt(dlat**2 + dlon**2) * 111  # Approximate km

            if dist <= distance_km:
                cluster["hotspots"].append(h2)
                cluster["total_frp"] += h2["frp"]
                cluster["max_frp"] = max(cluster["max_frp"], h2["frp"])
                cluster["count"] += 1
                used.add(j)

        # Recalculate center
        cluster["center_lat"] = sum(h["latitude"] for h in cluster["hotspots"]) / cluster["count"]
        cluster["center_lon"] = sum(h["longitude"] for h in cluster["hotspots"]) / cluster["count"]
        cluster["avg_frp"] = cluster["total_frp"] / cluster["count"]

        # Estimate area (rough approximation)
        if cluster["count"] > 1:
            lats = [h["latitude"] for h in cluster["hotspots"]]
            lons = [h["longitude"] for h in cluster["hotspots"]]
            lat_range = (max(lats) - min(lats)) * 111
            lon_range = (max(lons) - min(lons)) * 111 * math.cos(math.radians(cluster["center_lat"]))
            cluster["estimated_area_ha"] = round(lat_range * lon_range * 100, 1)
        else:
            cluster["estimated_area_ha"] = 1.0

        # Remove hotspots list to reduce response size
        del cluster["hotspots"]

        clusters.append(cluster)

    return sorted(clusters, key=lambda x: x["total_frp"], reverse=True)


# ============================================================================
# Dashboard HTML
# ============================================================================

def get_dashboard_page():
    """Return complete dashboard HTML."""
    return """<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <title>FireWatch AI - Dashboard Completo</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <link rel="stylesheet" href="https://unpkg.com/leaflet.markercluster@1.4.1/dist/MarkerCluster.css" />
    <link rel="stylesheet" href="https://unpkg.com/leaflet.markercluster@1.4.1/dist/MarkerCluster.Default.css" />
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #0f0f1a;
            color: #fff;
            overflow-x: hidden;
        }

        /* Header */
        .header {
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            padding: 12px 20px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid #333;
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            z-index: 1001;
        }
        .logo { color: #ff6b35; font-size: 1.4em; font-weight: bold; }
        .logo span { color: #f7c873; }
        .header-info { display: flex; gap: 20px; align-items: center; }
        .header-stat {
            text-align: center;
            padding: 5px 15px;
            background: rgba(255,107,53,0.1);
            border-radius: 6px;
        }
        .header-stat-value { color: #ff6b35; font-weight: bold; font-size: 1.2em; }
        .header-stat-label { color: #888; font-size: 0.7em; }

        /* Main Layout */
        .main-container {
            display: flex;
            margin-top: 56px;
            height: calc(100vh - 56px);
        }

        /* Sidebar */
        .sidebar {
            width: 320px;
            background: #1a1a2e;
            overflow-y: auto;
            border-right: 1px solid #333;
            flex-shrink: 0;
        }

        /* Tabs */
        .tabs {
            display: flex;
            background: #0f0f1a;
            border-bottom: 1px solid #333;
        }
        .tab {
            flex: 1;
            padding: 12px;
            text-align: center;
            cursor: pointer;
            font-size: 0.8em;
            color: #888;
            border-bottom: 2px solid transparent;
            transition: all 0.2s;
        }
        .tab:hover { color: #fff; }
        .tab.active {
            color: #ff6b35;
            border-bottom-color: #ff6b35;
        }

        /* Tab Content */
        .tab-content { display: none; padding: 15px; }
        .tab-content.active { display: block; }

        /* Panel */
        .panel {
            background: #16213e;
            border-radius: 8px;
            padding: 15px;
            margin-bottom: 15px;
        }
        .panel h3 {
            color: #f7c873;
            font-size: 0.85em;
            margin-bottom: 12px;
            text-transform: uppercase;
            letter-spacing: 1px;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        .panel h3 .icon { font-size: 1.2em; }

        /* Stats Grid */
        .stat-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 10px;
        }
        .stat-box {
            background: #0f0f1a;
            padding: 12px;
            border-radius: 6px;
            text-align: center;
        }
        .stat-box.full { grid-column: span 2; }
        .stat-value {
            font-size: 1.6em;
            font-weight: bold;
            color: #ff6b35;
        }
        .stat-value.green { color: #4ade80; }
        .stat-value.yellow { color: #fbbf24; }
        .stat-value.red { color: #ef4444; }
        .stat-label {
            font-size: 0.7em;
            color: #888;
            margin-top: 4px;
        }

        /* Form Elements */
        .form-group {
            margin-bottom: 12px;
        }
        .form-group label {
            display: block;
            font-size: 0.8em;
            color: #aaa;
            margin-bottom: 5px;
        }
        .form-group select, .form-group input {
            width: 100%;
            padding: 10px;
            border: 1px solid #333;
            border-radius: 6px;
            background: #0f0f1a;
            color: #fff;
            font-size: 0.9em;
        }
        .form-row {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 10px;
        }

        /* Buttons */
        .btn {
            width: 100%;
            padding: 12px;
            border: none;
            border-radius: 6px;
            font-size: 0.9em;
            font-weight: bold;
            cursor: pointer;
            transition: all 0.2s;
            margin-top: 8px;
        }
        .btn-primary { background: #ff6b35; color: white; }
        .btn-primary:hover { background: #ff8555; }
        .btn-secondary { background: #333; color: white; }
        .btn-secondary:hover { background: #444; }
        .btn-danger { background: #dc2626; color: white; }
        .btn-danger:hover { background: #ef4444; }

        /* Risk Meter */
        .risk-meter {
            background: #0f0f1a;
            border-radius: 8px;
            padding: 15px;
            text-align: center;
        }
        .risk-value {
            font-size: 3em;
            font-weight: bold;
            margin: 10px 0;
        }
        .risk-bar {
            height: 8px;
            background: linear-gradient(to right, #4ade80, #fbbf24, #ef4444);
            border-radius: 4px;
            position: relative;
            margin: 15px 0;
        }
        .risk-indicator {
            position: absolute;
            top: -4px;
            width: 16px;
            height: 16px;
            background: white;
            border-radius: 50%;
            border: 2px solid #333;
            transform: translateX(-50%);
            transition: left 0.5s;
        }
        .risk-labels {
            display: flex;
            justify-content: space-between;
            font-size: 0.7em;
            color: #888;
        }

        /* Progress Bars */
        .progress-item {
            margin: 10px 0;
        }
        .progress-label {
            display: flex;
            justify-content: space-between;
            font-size: 0.8em;
            margin-bottom: 5px;
        }
        .progress-bar {
            height: 6px;
            background: #0f0f1a;
            border-radius: 3px;
            overflow: hidden;
        }
        .progress-fill {
            height: 100%;
            border-radius: 3px;
            transition: width 0.5s;
        }

        /* Cluster List */
        .cluster-list {
            max-height: 300px;
            overflow-y: auto;
        }
        .cluster-item {
            background: #0f0f1a;
            border-radius: 6px;
            padding: 10px;
            margin-bottom: 8px;
            cursor: pointer;
            transition: all 0.2s;
            border-left: 3px solid #ff6b35;
        }
        .cluster-item:hover {
            background: #1a1a3e;
        }
        .cluster-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .cluster-id {
            font-weight: bold;
            color: #ff6b35;
        }
        .cluster-count {
            background: #ff6b35;
            color: white;
            padding: 2px 8px;
            border-radius: 10px;
            font-size: 0.8em;
        }
        .cluster-details {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 5px;
            margin-top: 8px;
            font-size: 0.75em;
            color: #888;
        }

        /* Emissions Card */
        .emissions-card {
            background: #0f0f1a;
            border-radius: 6px;
            padding: 12px;
            margin-bottom: 10px;
        }
        .emissions-value {
            font-size: 1.8em;
            font-weight: bold;
            color: #ff6b35;
        }
        .emissions-unit {
            font-size: 0.8em;
            color: #888;
        }
        .emissions-equiv {
            font-size: 0.75em;
            color: #666;
            margin-top: 5px;
        }

        /* Prediction Timeline */
        .timeline {
            position: relative;
            padding-left: 20px;
        }
        .timeline::before {
            content: '';
            position: absolute;
            left: 6px;
            top: 0;
            bottom: 0;
            width: 2px;
            background: #333;
        }
        .timeline-item {
            position: relative;
            padding: 10px;
            margin-bottom: 10px;
            background: #0f0f1a;
            border-radius: 6px;
        }
        .timeline-item::before {
            content: '';
            position: absolute;
            left: -17px;
            top: 15px;
            width: 10px;
            height: 10px;
            background: #ff6b35;
            border-radius: 50%;
        }
        .timeline-hour {
            font-weight: bold;
            color: #f7c873;
        }
        .timeline-data {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 5px;
            margin-top: 5px;
            font-size: 0.8em;
            color: #aaa;
        }

        /* Legend */
        .legend-item {
            display: flex;
            align-items: center;
            margin: 5px 0;
            font-size: 0.8em;
        }
        .legend-color {
            width: 14px;
            height: 14px;
            border-radius: 50%;
            margin-right: 8px;
        }

        /* Map */
        .map-container {
            flex: 1;
            position: relative;
        }
        #map {
            width: 100%;
            height: 100%;
            background: #0a0a15;
        }

        /* Loading Overlay */
        .loading {
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            background: rgba(0,0,0,0.9);
            padding: 30px 50px;
            border-radius: 10px;
            z-index: 1000;
            display: none;
            text-align: center;
        }
        .loading.active { display: block; }
        .spinner {
            width: 50px;
            height: 50px;
            border: 4px solid #333;
            border-top-color: #ff6b35;
            border-radius: 50%;
            animation: spin 1s linear infinite;
            margin: 0 auto 15px;
        }
        @keyframes spin { to { transform: rotate(360deg); } }

        /* Map Controls */
        .map-overlay {
            position: absolute;
            top: 10px;
            right: 10px;
            z-index: 1000;
        }
        .map-card {
            background: rgba(26, 26, 46, 0.95);
            padding: 12px 15px;
            border-radius: 8px;
            margin-bottom: 10px;
            min-width: 200px;
        }
        .map-card h4 {
            color: #f7c873;
            font-size: 0.8em;
            margin-bottom: 8px;
        }
        .weather-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 8px;
            font-size: 0.85em;
        }
        .weather-item {
            display: flex;
            align-items: center;
            gap: 5px;
        }
        .weather-icon { font-size: 1.2em; }

        /* Bottom Panel */
        .bottom-panel {
            position: absolute;
            bottom: 10px;
            left: 10px;
            right: 330px;
            z-index: 1000;
            display: flex;
            gap: 10px;
        }
        .info-chip {
            background: rgba(26, 26, 46, 0.95);
            padding: 8px 15px;
            border-radius: 20px;
            font-size: 0.85em;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        .info-chip .value { color: #ff6b35; font-weight: bold; }

        /* Mobile */
        @media (max-width: 768px) {
            .sidebar { display: none; }
            .bottom-panel { right: 10px; flex-wrap: wrap; }
            .header-info { display: none; }
        }

        /* Scrollbar */
        ::-webkit-scrollbar { width: 6px; }
        ::-webkit-scrollbar-track { background: #0f0f1a; }
        ::-webkit-scrollbar-thumb { background: #333; border-radius: 3px; }
        ::-webkit-scrollbar-thumb:hover { background: #444; }
    </style>
</head>
<body>
    <div class="header">
        <div class="logo">FireWatch <span>AI</span></div>
        <div class="header-info">
            <div class="header-stat">
                <div class="header-stat-value" id="headerFires">-</div>
                <div class="header-stat-label">FOCOS ATIVOS</div>
            </div>
            <div class="header-stat">
                <div class="header-stat-value" id="headerRisk">-</div>
                <div class="header-stat-label">RISCO</div>
            </div>
            <div class="header-stat">
                <div class="header-stat-value" id="headerArea">-</div>
                <div class="header-stat-label">AREA (ha)</div>
            </div>
        </div>
    </div>

    <div class="main-container">
        <div class="sidebar">
            <div class="tabs">
                <div class="tab active" data-tab="monitor">Monitor</div>
                <div class="tab" data-tab="analysis">Analise</div>
                <div class="tab" data-tab="predict">Previsao</div>
            </div>

            <!-- Monitor Tab -->
            <div class="tab-content active" id="tab-monitor">
                <div class="panel">
                    <h3><span class="icon">📍</span> Filtros</h3>
                    <div class="form-group">
                        <label>Regiao</label>
                        <select id="regionSelect">
                            <option value="brazil">Brasil Completo</option>
                            <option value="amazon">Amazonia</option>
                            <option value="cerrado">Cerrado</option>
                            <option value="pantanal">Pantanal</option>
                            <option value="mataatlantica">Mata Atlantica</option>
                            <option value="caatinga">Caatinga</option>
                            <option value="saopaulo" selected>Sao Paulo</option>
                            <option value="nordeste">Nordeste</option>
                            <option value="sul">Sul</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label>Periodo</label>
                        <select id="daysSelect">
                            <option value="1">Ultimo dia</option>
                            <option value="2" selected>2 dias</option>
                            <option value="3">3 dias</option>
                            <option value="5">5 dias</option>
                            <option value="7">7 dias</option>
                        </select>
                    </div>
                    <button class="btn btn-primary" onclick="loadAllData()">Atualizar Dados</button>
                </div>

                <div class="panel">
                    <h3><span class="icon">📊</span> Estatisticas</h3>
                    <div class="stat-grid">
                        <div class="stat-box">
                            <div class="stat-value" id="totalFires">-</div>
                            <div class="stat-label">Focos</div>
                        </div>
                        <div class="stat-box">
                            <div class="stat-value" id="totalClusters">-</div>
                            <div class="stat-label">Incendios</div>
                        </div>
                        <div class="stat-box">
                            <div class="stat-value" id="avgFRP">-</div>
                            <div class="stat-label">FRP Medio</div>
                        </div>
                        <div class="stat-box">
                            <div class="stat-value" id="maxFRP">-</div>
                            <div class="stat-label">FRP Max</div>
                        </div>
                    </div>
                </div>

                <div class="panel">
                    <h3><span class="icon">🔥</span> Maiores Incendios</h3>
                    <div class="cluster-list" id="clusterList">
                        <div style="color: #666; text-align: center; padding: 20px;">
                            Carregue os dados para ver os incendios
                        </div>
                    </div>
                </div>
            </div>

            <!-- Analysis Tab -->
            <div class="tab-content" id="tab-analysis">
                <div class="panel">
                    <h3><span class="icon">⚠️</span> Indice de Risco</h3>
                    <div class="risk-meter">
                        <div class="risk-value" id="riskValue">-</div>
                        <div id="riskLevel" style="color: #888;">Carregando...</div>
                        <div class="risk-bar">
                            <div class="risk-indicator" id="riskIndicator" style="left: 0%;"></div>
                        </div>
                        <div class="risk-labels">
                            <span>Baixo</span>
                            <span>Moderado</span>
                            <span>Alto</span>
                            <span>Critico</span>
                        </div>
                    </div>
                </div>

                <div class="panel">
                    <h3><span class="icon">🌡️</span> Fatores de Risco</h3>
                    <div class="progress-item">
                        <div class="progress-label">
                            <span>Temperatura</span>
                            <span id="tempValue">-</span>
                        </div>
                        <div class="progress-bar">
                            <div class="progress-fill" id="tempBar" style="width: 0%; background: #ef4444;"></div>
                        </div>
                    </div>
                    <div class="progress-item">
                        <div class="progress-label">
                            <span>Umidade (inverso)</span>
                            <span id="humidValue">-</span>
                        </div>
                        <div class="progress-bar">
                            <div class="progress-fill" id="humidBar" style="width: 0%; background: #3b82f6;"></div>
                        </div>
                    </div>
                    <div class="progress-item">
                        <div class="progress-label">
                            <span>Vento</span>
                            <span id="windValue">-</span>
                        </div>
                        <div class="progress-bar">
                            <div class="progress-fill" id="windBar" style="width: 0%; background: #8b5cf6;"></div>
                        </div>
                    </div>
                    <div class="progress-item">
                        <div class="progress-label">
                            <span>Seca</span>
                            <span id="droughtValue">-</span>
                        </div>
                        <div class="progress-bar">
                            <div class="progress-fill" id="droughtBar" style="width: 0%; background: #f59e0b;"></div>
                        </div>
                    </div>
                </div>

                <div class="panel">
                    <h3><span class="icon">🌿</span> Bioma Afetado</h3>
                    <div class="stat-grid">
                        <div class="stat-box full">
                            <div class="stat-value" id="biomeName" style="font-size: 1.2em;">-</div>
                            <div class="stat-label">Bioma Predominante</div>
                        </div>
                        <div class="stat-box">
                            <div class="stat-value" id="biomeCarbon">-</div>
                            <div class="stat-label">Carbono (t/ha)</div>
                        </div>
                        <div class="stat-box">
                            <div class="stat-value" id="biomeRecovery">-</div>
                            <div class="stat-label">Recuperacao (anos)</div>
                        </div>
                    </div>
                </div>

                <div class="panel">
                    <h3><span class="icon">💨</span> Emissoes Estimadas</h3>
                    <div class="emissions-card">
                        <div class="emissions-value" id="emissionsCO2">-</div>
                        <div class="emissions-unit">toneladas de CO2</div>
                        <div class="emissions-equiv" id="emissionsEquiv">-</div>
                    </div>
                    <div class="stat-grid">
                        <div class="stat-box">
                            <div class="stat-value" style="font-size: 1.2em;" id="emissionsCH4">-</div>
                            <div class="stat-label">CH4 (ton)</div>
                        </div>
                        <div class="stat-box">
                            <div class="stat-value" style="font-size: 1.2em;" id="emissionsPM25">-</div>
                            <div class="stat-label">PM2.5 (ton)</div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Prediction Tab -->
            <div class="tab-content" id="tab-predict">
                <div class="panel">
                    <h3><span class="icon">🎯</span> Selecionar Foco</h3>
                    <p style="font-size: 0.8em; color: #888; margin-bottom: 10px;">
                        Clique em um foco no mapa ou selecione um incendio abaixo para ver a previsao de propagacao.
                    </p>
                    <div class="form-group">
                        <label>Incendio Selecionado</label>
                        <select id="fireSelect">
                            <option value="">Selecione um incendio...</option>
                        </select>
                    </div>
                    <div class="form-row">
                        <div class="form-group">
                            <label>Horas de Previsao</label>
                            <select id="hoursSelect">
                                <option value="3">3 horas</option>
                                <option value="6" selected>6 horas</option>
                                <option value="12">12 horas</option>
                                <option value="24">24 horas</option>
                            </select>
                        </div>
                        <div class="form-group">
                            <label>Dias sem Chuva</label>
                            <input type="number" id="droughtDays" value="5" min="0" max="60">
                        </div>
                    </div>
                    <button class="btn btn-primary" onclick="runPrediction()">Gerar Previsao</button>
                    <button class="btn btn-secondary" onclick="clearPrediction()">Limpar</button>
                </div>

                <div class="panel">
                    <h3><span class="icon">📈</span> Previsao de Propagacao</h3>
                    <div class="stat-grid">
                        <div class="stat-box">
                            <div class="stat-value" id="spreadRate">-</div>
                            <div class="stat-label">Velocidade (m/min)</div>
                        </div>
                        <div class="stat-box">
                            <div class="stat-value" id="spreadDir">-</div>
                            <div class="stat-label">Direcao</div>
                        </div>
                    </div>
                    <div class="timeline" id="predictionTimeline">
                        <div style="color: #666; text-align: center; padding: 20px; font-size: 0.85em;">
                            Selecione um incendio para ver a previsao
                        </div>
                    </div>
                </div>

                <div class="panel">
                    <h3><span class="icon">🚨</span> Evacuacao</h3>
                    <div class="stat-box full" style="margin-bottom: 10px;">
                        <div class="stat-value red" id="evacuationStatus">-</div>
                        <div class="stat-label">Status de Alerta</div>
                    </div>
                    <p style="font-size: 0.8em; color: #888;" id="evacuationMessage">
                        Execute uma previsao para ver recomendacoes de evacuacao.
                    </p>
                </div>
            </div>
        </div>

        <div class="map-container">
            <div id="map"></div>

            <div class="loading" id="loading">
                <div class="spinner"></div>
                <div>Carregando dados da NASA FIRMS...</div>
            </div>

            <div class="map-overlay">
                <div class="map-card">
                    <h4>Clima Atual</h4>
                    <div class="weather-grid">
                        <div class="weather-item">
                            <span class="weather-icon">🌡️</span>
                            <span id="weatherTemp">-</span>
                        </div>
                        <div class="weather-item">
                            <span class="weather-icon">💧</span>
                            <span id="weatherHumid">-</span>
                        </div>
                        <div class="weather-item">
                            <span class="weather-icon">💨</span>
                            <span id="weatherWind">-</span>
                        </div>
                        <div class="weather-item">
                            <span class="weather-icon">🧭</span>
                            <span id="weatherDir">-</span>
                        </div>
                    </div>
                </div>
                <div class="map-card">
                    <h4>Legenda</h4>
                    <div class="legend-item">
                        <div class="legend-color" style="background: #ff0000;"></div>
                        <span>Alta (FRP > 50)</span>
                    </div>
                    <div class="legend-item">
                        <div class="legend-color" style="background: #ff6b35;"></div>
                        <span>Media (FRP 10-50)</span>
                    </div>
                    <div class="legend-item">
                        <div class="legend-color" style="background: #f7c873;"></div>
                        <span>Baixa (FRP < 10)</span>
                    </div>
                    <div class="legend-item">
                        <div class="legend-color" style="background: rgba(255,0,0,0.3); border: 2px dashed #ff0000;"></div>
                        <span>Previsao</span>
                    </div>
                </div>
            </div>

            <div class="bottom-panel">
                <div class="info-chip">
                    <span>📡 Satelite:</span>
                    <span class="value">VIIRS NOAA-20</span>
                </div>
                <div class="info-chip">
                    <span>🕐 Atualizado:</span>
                    <span class="value" id="lastUpdate">-</span>
                </div>
                <div class="info-chip">
                    <span>🌍 Bioma:</span>
                    <span class="value" id="currentBiome">-</span>
                </div>
            </div>
        </div>
    </div>

    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <script src="https://unpkg.com/leaflet.markercluster@1.4.1/dist/leaflet.markercluster.js"></script>
    <script>
        // ========================================
        // Configuration
        // ========================================
        const regions = {
            brazil: { west: -74, south: -34, east: -34, north: 5, center: [-14, -52], zoom: 4 },
            amazon: { west: -74, south: -10, east: -44, north: 5, center: [-3, -60], zoom: 5 },
            cerrado: { west: -60, south: -24, east: -41, north: -2, center: [-15, -47], zoom: 5 },
            pantanal: { west: -59, south: -22, east: -54, north: -15, center: [-18, -56], zoom: 6 },
            mataatlantica: { west: -55, south: -30, east: -34, north: -3, center: [-20, -44], zoom: 5 },
            caatinga: { west: -46, south: -17, east: -35, north: -2, center: [-9, -40], zoom: 6 },
            saopaulo: { west: -53, south: -26, east: -44, north: -19, center: [-22, -48], zoom: 6 },
            nordeste: { west: -48, south: -18, east: -34, north: -2, center: [-9, -38], zoom: 5 },
            sul: { west: -58, south: -34, east: -48, north: -22, center: [-27, -51], zoom: 5 }
        };

        // State
        let currentHotspots = [];
        let currentClusters = [];
        let currentWeather = null;
        let selectedCluster = null;
        let predictionCircles = [];

        // ========================================
        // Initialize Map
        // ========================================
        const map = L.map('map').setView([-22, -48], 6);

        L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
            attribution: '&copy; OpenStreetMap, &copy; CartoDB',
            maxZoom: 19
        }).addTo(map);

        const markers = L.markerClusterGroup({
            maxClusterRadius: 50,
            spiderfyOnMaxZoom: true,
            showCoverageOnHover: false,
            iconCreateFunction: function(cluster) {
                const count = cluster.getChildCount();
                return L.divIcon({
                    html: '<div style="background: rgba(255,107,53,0.9); color: white; border-radius: 50%; width: 40px; height: 40px; display: flex; align-items: center; justify-content: center; font-weight: bold; border: 2px solid #fff; box-shadow: 0 0 10px rgba(255,107,53,0.5);">' + count + '</div>',
                    className: 'marker-cluster',
                    iconSize: L.point(40, 40)
                });
            }
        });
        map.addLayer(markers);

        // ========================================
        // Tab Navigation
        // ========================================
        document.querySelectorAll('.tab').forEach(tab => {
            tab.addEventListener('click', () => {
                document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
                document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
                tab.classList.add('active');
                document.getElementById('tab-' + tab.dataset.tab).classList.add('active');
            });
        });

        // ========================================
        // Helper Functions
        // ========================================
        function getMarkerColor(frp) {
            if (frp > 50) return '#ff0000';
            if (frp > 10) return '#ff6b35';
            return '#f7c873';
        }

        function createFireIcon(frp) {
            const color = getMarkerColor(frp);
            const size = frp > 50 ? 14 : (frp > 10 ? 11 : 8);
            return L.divIcon({
                html: '<div style="background: ' + color + '; width: ' + size + 'px; height: ' + size + 'px; border-radius: 50%; border: 2px solid rgba(255,255,255,0.8); box-shadow: 0 0 10px ' + color + ';"></div>',
                className: 'fire-marker',
                iconSize: [size, size]
            });
        }

        function getWindDirection(degrees) {
            const dirs = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW'];
            return dirs[Math.round(degrees / 45) % 8];
        }

        function showLoading() {
            document.getElementById('loading').classList.add('active');
        }

        function hideLoading() {
            document.getElementById('loading').classList.remove('active');
        }

        // ========================================
        // API Calls
        // ========================================
        async function fetchHotspots(coords, days) {
            const url = '/api/hotspots?west=' + coords.west + '&south=' + coords.south + '&east=' + coords.east + '&north=' + coords.north + '&days=' + days;
            const response = await fetch(url);
            return await response.json();
        }

        async function fetchWeather(lat, lon) {
            const url = '/api/weather?lat=' + lat + '&lon=' + lon;
            const response = await fetch(url);
            return await response.json();
        }

        async function fetchRisk(lat, lon, days_without_rain) {
            const url = '/api/risk?lat=' + lat + '&lon=' + lon + '&days_without_rain=' + days_without_rain;
            const response = await fetch(url);
            return await response.json();
        }

        async function fetchClusters(coords, days) {
            const url = '/api/clusters?west=' + coords.west + '&south=' + coords.south + '&east=' + coords.east + '&north=' + coords.north + '&days=' + days;
            const response = await fetch(url);
            return await response.json();
        }

        async function fetchPrediction(lat, lon, area, wind_dir, hours) {
            const url = '/api/predict?lat=' + lat + '&lon=' + lon + '&area=' + area + '&wind_dir=' + wind_dir + '&hours=' + hours;
            const response = await fetch(url);
            return await response.json();
        }

        async function fetchEmissions(lat, lon, area) {
            const url = '/api/emissions?lat=' + lat + '&lon=' + lon + '&area=' + area;
            const response = await fetch(url);
            return await response.json();
        }

        // ========================================
        // Load All Data
        // ========================================
        async function loadAllData() {
            const region = document.getElementById('regionSelect').value;
            const days = document.getElementById('daysSelect').value;
            const coords = regions[region];
            const droughtDays = parseInt(document.getElementById('droughtDays').value) || 5;

            showLoading();

            try {
                // Load hotspots
                const hotspotsData = await fetchHotspots(coords, days);
                if (hotspotsData.error) throw new Error(hotspotsData.error);
                currentHotspots = hotspotsData.hotspots || [];

                // Load clusters
                const clustersData = await fetchClusters(coords, days);
                currentClusters = clustersData.clusters || [];

                // Load weather for center of region
                const weatherData = await fetchWeather(coords.center[0], coords.center[1]);
                currentWeather = weatherData;

                // Load risk
                const riskData = await fetchRisk(coords.center[0], coords.center[1], droughtDays);

                // Update map
                updateMap();

                // Update statistics
                updateStatistics(hotspotsData, clustersData);

                // Update weather display
                updateWeatherDisplay(weatherData);

                // Update risk display
                updateRiskDisplay(riskData);

                // Update biome info
                updateBiomeInfo(coords.center[0], coords.center[1], clustersData.total_area || 100);

                // Update cluster list
                updateClusterList();

                // Update fire select
                updateFireSelect();

                // Update timestamp
                document.getElementById('lastUpdate').textContent = new Date().toLocaleTimeString('pt-BR');

                // Fit map
                if (currentHotspots.length > 0) {
                    map.fitBounds(markers.getBounds(), { padding: [50, 50] });
                } else {
                    map.setView(coords.center, coords.zoom);
                }

            } catch (error) {
                console.error('Error loading data:', error);
                alert('Erro ao carregar dados: ' + error.message);
            } finally {
                hideLoading();
            }
        }

        // ========================================
        // Update Functions
        // ========================================
        function updateMap() {
            markers.clearLayers();

            currentHotspots.forEach(h => {
                const marker = L.marker([h.latitude, h.longitude], {
                    icon: createFireIcon(h.frp)
                });

                marker.on('click', () => selectHotspot(h));

                const popup = '<div style="font-family: sans-serif;">' +
                    '<h4 style="color: #ff6b35; margin: 0 0 8px 0;">Foco de Incendio</h4>' +
                    '<p style="margin: 4px 0;"><strong>Coords:</strong> ' + h.latitude.toFixed(4) + ', ' + h.longitude.toFixed(4) + '</p>' +
                    '<p style="margin: 4px 0;"><strong>FRP:</strong> ' + h.frp.toFixed(1) + ' MW</p>' +
                    '<p style="margin: 4px 0;"><strong>Brilho:</strong> ' + h.brightness.toFixed(1) + ' K</p>' +
                    '<p style="margin: 4px 0;"><strong>Confianca:</strong> ' + h.confidence + '</p>' +
                    '<p style="margin: 4px 0;"><strong>Data:</strong> ' + h.acq_datetime + '</p>' +
                    '</div>';

                marker.bindPopup(popup);
                markers.addLayer(marker);
            });
        }

        function updateStatistics(hotspotsData, clustersData) {
            const count = hotspotsData.count || 0;
            const clusters = clustersData.clusters || [];

            document.getElementById('totalFires').textContent = count;
            document.getElementById('headerFires').textContent = count;
            document.getElementById('totalClusters').textContent = clusters.length;

            if (count > 0) {
                const frps = currentHotspots.map(h => h.frp).filter(f => f > 0);
                const avgFRP = frps.length > 0 ? (frps.reduce((a, b) => a + b, 0) / frps.length) : 0;
                const maxFRP = frps.length > 0 ? Math.max(...frps) : 0;

                document.getElementById('avgFRP').textContent = avgFRP.toFixed(1);
                document.getElementById('maxFRP').textContent = maxFRP.toFixed(1);

                const totalArea = clusters.reduce((sum, c) => sum + (c.estimated_area_ha || 0), 0);
                document.getElementById('headerArea').textContent = totalArea.toFixed(0);
            }
        }

        function updateWeatherDisplay(weather) {
            document.getElementById('weatherTemp').textContent = weather.temperature + '°C';
            document.getElementById('weatherHumid').textContent = weather.humidity + '%';
            document.getElementById('weatherWind').textContent = weather.wind_speed + ' km/h';
            document.getElementById('weatherDir').textContent = getWindDirection(weather.wind_direction);
        }

        function updateRiskDisplay(risk) {
            document.getElementById('riskValue').textContent = risk.risk_index;
            document.getElementById('riskLevel').textContent = risk.risk_level;
            document.getElementById('riskIndicator').style.left = risk.risk_index + '%';
            document.getElementById('headerRisk').textContent = risk.risk_level;

            // Color based on risk
            const riskEl = document.getElementById('riskValue');
            riskEl.className = 'risk-value';
            if (risk.risk_index >= 60) riskEl.classList.add('red');
            else if (risk.risk_index >= 40) riskEl.classList.add('yellow');
            else riskEl.classList.add('green');

            // Update factors
            document.getElementById('tempValue').textContent = risk.factors.temperature + '°C';
            document.getElementById('tempBar').style.width = Math.min(100, (risk.factors.temperature - 20) * 4) + '%';

            document.getElementById('humidValue').textContent = risk.factors.humidity + '%';
            document.getElementById('humidBar').style.width = (100 - risk.factors.humidity) + '%';

            document.getElementById('windValue').textContent = risk.factors.wind_speed + ' km/h';
            document.getElementById('windBar').style.width = Math.min(100, risk.factors.wind_speed * 2) + '%';

            document.getElementById('droughtValue').textContent = risk.factors.days_without_rain + ' dias';
            document.getElementById('droughtBar').style.width = Math.min(100, risk.factors.days_without_rain * 5) + '%';
        }

        function updateBiomeInfo(lat, lon, area) {
            fetchEmissions(lat, lon, area).then(data => {
                document.getElementById('biomeName').textContent = data.biome;
                document.getElementById('currentBiome').textContent = data.biome;
                document.getElementById('biomeCarbon').textContent = data.carbon_tons_ha;
                document.getElementById('biomeRecovery').textContent = data.recovery_years;

                document.getElementById('emissionsCO2').textContent = data.emissions.co2_tons.toLocaleString();
                document.getElementById('emissionsCH4').textContent = data.emissions.ch4_tons;
                document.getElementById('emissionsPM25').textContent = data.emissions.pm25_tons;
                document.getElementById('emissionsEquiv').textContent =
                    'Equivalente a ' + data.emissions.cars_equivalent.toLocaleString() + ' carros/ano';
            });
        }

        function updateClusterList() {
            const list = document.getElementById('clusterList');

            if (currentClusters.length === 0) {
                list.innerHTML = '<div style="color: #666; text-align: center; padding: 20px;">Nenhum incendio detectado</div>';
                return;
            }

            list.innerHTML = currentClusters.slice(0, 10).map(c =>
                '<div class="cluster-item" onclick="focusCluster(' + c.id + ')">' +
                    '<div class="cluster-header">' +
                        '<span class="cluster-id">Incendio #' + c.id + '</span>' +
                        '<span class="cluster-count">' + c.count + ' focos</span>' +
                    '</div>' +
                    '<div class="cluster-details">' +
                        '<span>FRP Total: ' + c.total_frp.toFixed(1) + '</span>' +
                        '<span>Area: ' + c.estimated_area_ha + ' ha</span>' +
                    '</div>' +
                '</div>'
            ).join('');
        }

        function updateFireSelect() {
            const select = document.getElementById('fireSelect');
            select.innerHTML = '<option value="">Selecione um incendio...</option>';

            currentClusters.slice(0, 20).forEach(c => {
                select.innerHTML += '<option value="' + c.id + '">Incendio #' + c.id + ' (' + c.count + ' focos, ' + c.estimated_area_ha + ' ha)</option>';
            });
        }

        // ========================================
        // Cluster Functions
        // ========================================
        function focusCluster(id) {
            const cluster = currentClusters.find(c => c.id === id);
            if (cluster) {
                map.setView([cluster.center_lat, cluster.center_lon], 10);
                selectCluster(cluster);
            }
        }

        function selectCluster(cluster) {
            selectedCluster = cluster;
            document.getElementById('fireSelect').value = cluster.id;
        }

        function selectHotspot(hotspot) {
            // Find cluster containing this hotspot
            const cluster = currentClusters.find(c => {
                const dist = Math.sqrt(
                    Math.pow(c.center_lat - hotspot.latitude, 2) +
                    Math.pow(c.center_lon - hotspot.longitude, 2)
                ) * 111;
                return dist < 10;
            });

            if (cluster) {
                selectCluster(cluster);
            }
        }

        // ========================================
        // Prediction Functions
        // ========================================
        async function runPrediction() {
            const fireId = document.getElementById('fireSelect').value;
            const hours = parseInt(document.getElementById('hoursSelect').value);

            if (!fireId) {
                alert('Selecione um incendio primeiro');
                return;
            }

            const cluster = currentClusters.find(c => c.id == fireId);
            if (!cluster) return;

            showLoading();

            try {
                const windDir = currentWeather ? currentWeather.wind_direction : 90;
                const prediction = await fetchPrediction(
                    cluster.center_lat,
                    cluster.center_lon,
                    cluster.estimated_area_ha,
                    windDir,
                    hours
                );

                displayPrediction(prediction, cluster);

            } catch (error) {
                alert('Erro ao gerar previsao: ' + error.message);
            } finally {
                hideLoading();
            }
        }

        function displayPrediction(prediction, cluster) {
            // Clear previous predictions
            clearPrediction();

            // Update spread stats
            document.getElementById('spreadRate').textContent = prediction.spread_rate;
            document.getElementById('spreadDir').textContent = getWindDirection(prediction.wind_direction);

            // Draw prediction circles on map
            prediction.predictions.forEach((p, i) => {
                const circle = L.circle([p.center_lat, p.center_lon], {
                    radius: p.radius_m,
                    color: '#ff0000',
                    fillColor: '#ff0000',
                    fillOpacity: 0.1 - (i * 0.015),
                    weight: 2,
                    dashArray: '5, 5'
                }).addTo(map);

                circle.bindPopup('<strong>+' + p.hour + 'h</strong><br>Area: ' + p.area_ha + ' ha<br>Raio: ' + p.radius_m + ' m');
                predictionCircles.push(circle);
            });

            // Update timeline
            const timeline = document.getElementById('predictionTimeline');
            timeline.innerHTML = prediction.predictions.map(p =>
                '<div class="timeline-item">' +
                    '<div class="timeline-hour">+' + p.hour + ' hora' + (p.hour > 1 ? 's' : '') + '</div>' +
                    '<div class="timeline-data">' +
                        '<span>Area: ' + p.area_ha + ' ha</span>' +
                        '<span>Raio: ' + p.radius_m + ' m</span>' +
                    '</div>' +
                '</div>'
            ).join('');

            // Update evacuation status
            const lastPred = prediction.predictions[prediction.predictions.length - 1];
            let status = 'MONITORAR';
            let message = 'Situacao sob controle. Mantenha monitoramento.';

            if (lastPred.area_ha > 500) {
                status = 'EVACUAR';
                message = 'Area critica! Iniciar evacuacao das comunidades proximas.';
            } else if (lastPred.area_ha > 100) {
                status = 'ALERTA';
                message = 'Preparar plano de evacuacao. Alertar comunidades.';
            }

            document.getElementById('evacuationStatus').textContent = status;
            document.getElementById('evacuationMessage').textContent = message;

            // Fit map to show predictions
            if (predictionCircles.length > 0) {
                const group = L.featureGroup(predictionCircles);
                map.fitBounds(group.getBounds(), { padding: [50, 50] });
            }
        }

        function clearPrediction() {
            predictionCircles.forEach(c => map.removeLayer(c));
            predictionCircles = [];
            document.getElementById('predictionTimeline').innerHTML =
                '<div style="color: #666; text-align: center; padding: 20px; font-size: 0.85em;">Selecione um incendio para ver a previsao</div>';
            document.getElementById('spreadRate').textContent = '-';
            document.getElementById('spreadDir').textContent = '-';
            document.getElementById('evacuationStatus').textContent = '-';
            document.getElementById('evacuationMessage').textContent = 'Execute uma previsao para ver recomendacoes de evacuacao.';
        }

        // ========================================
        // Event Listeners
        // ========================================
        document.getElementById('regionSelect').addEventListener('change', function() {
            const coords = regions[this.value];
            map.setView(coords.center, coords.zoom);
        });

        // ========================================
        // Initialize
        // ========================================
        loadAllData();
    </script>
</body>
</html>"""


def get_landing_page():
    """Return API documentation page."""
    return """<!DOCTYPE html>
<html>
<head>
    <title>FireWatch AI - API</title>
    <meta charset="utf-8">
    <style>
        body { font-family: sans-serif; max-width: 800px; margin: 50px auto; padding: 20px; background: #1a1a2e; color: #eee; }
        h1 { color: #ff6b35; }
        h3 { color: #f7c873; margin-top: 30px; }
        code { background: #0f0f1a; padding: 3px 8px; border-radius: 4px; color: #f7c873; }
        a { color: #ff6b35; }
        .endpoint { background: #16213e; padding: 12px; margin: 8px 0; border-radius: 6px; border-left: 4px solid #ff6b35; }
    </style>
</head>
<body>
    <h1>FireWatch AI - API</h1>
    <p><a href="/">Voltar ao Dashboard</a></p>

    <h3>Endpoints</h3>
    <div class="endpoint"><code>GET /api/health</code> - Health check</div>
    <div class="endpoint"><code>GET /api/hotspots?west=&south=&east=&north=&days=</code> - Fire hotspots</div>
    <div class="endpoint"><code>GET /api/weather?lat=&lon=</code> - Weather data</div>
    <div class="endpoint"><code>GET /api/risk?lat=&lon=&days_without_rain=</code> - Fire risk index</div>
    <div class="endpoint"><code>GET /api/clusters?west=&south=&east=&north=&days=</code> - Fire clusters</div>
    <div class="endpoint"><code>GET /api/emissions?lat=&lon=&area=</code> - Carbon emissions</div>
    <div class="endpoint"><code>GET /api/predict?lat=&lon=&area=&wind_dir=&hours=</code> - Spread prediction</div>

    <h3>Example</h3>
    <p><a href="/api/hotspots?west=-50&south=-25&east=-44&north=-19&days=2">Fires in Sao Paulo</a></p>
</body>
</html>"""


# ============================================================================
# HTTP Handler
# ============================================================================

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)

        # Dashboard
        if path == "/" or path == "" or path == "/dashboard":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(get_dashboard_page().encode("utf-8"))
            return

        # API docs
        if path == "/docs":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(get_landing_page().encode("utf-8"))
            return

        # Health check
        if path == "/api/health" or path == "/health":
            self.send_json(200, {
                "status": "healthy",
                "version": "0.3.0",
                "api_key_configured": bool(FIRMS_API_KEY),
                "features": ["hotspots", "weather", "risk", "clusters", "emissions", "prediction"]
            })
            return

        # Hotspots endpoint
        if path == "/api/hotspots":
            try:
                west = float(query.get("west", [-74])[0])
                south = float(query.get("south", [-34])[0])
                east = float(query.get("east", [-34])[0])
                north = float(query.get("north", [5])[0])
                days = int(query.get("days", [1])[0])

                hotspots, error = fetch_hotspots(west, south, east, north, days)
                if error:
                    self.send_json(500, {"error": error})
                    return

                self.send_json(200, {
                    "count": len(hotspots),
                    "source": "VIIRS_NOAA20_NRT",
                    "hotspots": hotspots[:1000]
                })
            except Exception as e:
                self.send_json(400, {"error": str(e)})
            return

        # Weather endpoint
        if path == "/api/weather":
            try:
                lat = float(query.get("lat", [-22])[0])
                lon = float(query.get("lon", [-48])[0])

                weather, error = fetch_weather(lat, lon)
                self.send_json(200, weather)
            except Exception as e:
                self.send_json(400, {"error": str(e)})
            return

        # Risk endpoint
        if path == "/api/risk":
            try:
                lat = float(query.get("lat", [-22])[0])
                lon = float(query.get("lon", [-48])[0])
                days_without_rain = int(query.get("days_without_rain", [5])[0])

                weather, _ = fetch_weather(lat, lon)
                risk_index = calculate_risk_index(
                    weather["temperature"],
                    weather["humidity"],
                    weather["wind_speed"],
                    days_without_rain
                )

                self.send_json(200, {
                    "risk_index": risk_index,
                    "risk_level": get_risk_level(risk_index),
                    "factors": {
                        "temperature": weather["temperature"],
                        "humidity": weather["humidity"],
                        "wind_speed": weather["wind_speed"],
                        "days_without_rain": days_without_rain
                    }
                })
            except Exception as e:
                self.send_json(400, {"error": str(e)})
            return

        # Clusters endpoint
        if path == "/api/clusters":
            try:
                west = float(query.get("west", [-74])[0])
                south = float(query.get("south", [-34])[0])
                east = float(query.get("east", [-34])[0])
                north = float(query.get("north", [5])[0])
                days = int(query.get("days", [1])[0])

                hotspots, error = fetch_hotspots(west, south, east, north, days)
                if error:
                    self.send_json(500, {"error": error})
                    return

                clusters = cluster_hotspots(hotspots)
                total_area = sum(c.get("estimated_area_ha", 0) for c in clusters)

                self.send_json(200, {
                    "total_hotspots": len(hotspots),
                    "total_clusters": len(clusters),
                    "total_area": round(total_area, 1),
                    "clusters": clusters[:50]
                })
            except Exception as e:
                self.send_json(400, {"error": str(e)})
            return

        # Emissions endpoint
        if path == "/api/emissions":
            try:
                lat = float(query.get("lat", [-22])[0])
                lon = float(query.get("lon", [-48])[0])
                area = float(query.get("area", [100])[0])

                biome_name, biome_data = get_biome(lat, lon)
                emissions = calculate_emissions(area, biome_data["carbon_tons_ha"])

                self.send_json(200, {
                    "biome": biome_name,
                    "carbon_tons_ha": biome_data["carbon_tons_ha"],
                    "recovery_years": biome_data.get("recovery_years", 20),
                    "area_ha": area,
                    "emissions": emissions
                })
            except Exception as e:
                self.send_json(400, {"error": str(e)})
            return

        # Prediction endpoint
        if path == "/api/predict":
            try:
                lat = float(query.get("lat", [-22])[0])
                lon = float(query.get("lon", [-48])[0])
                area = float(query.get("area", [50])[0])
                wind_dir = float(query.get("wind_dir", [90])[0])
                hours = int(query.get("hours", [6])[0])

                biome_name, biome_data = get_biome(lat, lon)
                weather, _ = fetch_weather(lat, lon)

                spread_rate = calculate_spread_rate(
                    weather["wind_speed"],
                    spread_factor=biome_data.get("spread_factor", 1.0)
                )

                predictions = predict_fire_perimeter(lat, lon, area, wind_dir, hours)

                self.send_json(200, {
                    "center_lat": lat,
                    "center_lon": lon,
                    "initial_area_ha": area,
                    "wind_direction": wind_dir,
                    "spread_rate": spread_rate,
                    "biome": biome_name,
                    "predictions": predictions
                })
            except Exception as e:
                self.send_json(400, {"error": str(e)})
            return

        # 404
        self.send_json(404, {"error": "Not found"})

    def send_json(self, status, data):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode("utf-8"))
