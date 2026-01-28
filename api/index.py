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
# Brazilian States (approximate bounds)
STATES = {
    "Acre": {"west": -74, "south": -11.5, "east": -66.5, "north": -7},
    "Amazonas": {"west": -74, "south": -10, "east": -56, "north": 2.5},
    "Roraima": {"west": -65, "south": 0, "east": -58, "north": 5.5},
    "Para": {"west": -59, "south": -10, "east": -46, "north": 3},
    "Amapa": {"west": -55, "south": -1, "east": -49, "north": 5},
    "Tocantins": {"west": -51, "south": -14, "east": -45.5, "north": -5},
    "Maranhao": {"west": -49, "south": -11, "east": -41, "north": -1},
    "Piaui": {"west": -46, "south": -11, "east": -40.5, "north": -2.5},
    "Ceara": {"west": -42, "south": -8, "east": -37, "north": -2.5},
    "Rio Grande do Norte": {"west": -38.5, "south": -7, "east": -34.5, "north": -4.5},
    "Paraiba": {"west": -39, "south": -8.5, "east": -34.5, "north": -6},
    "Pernambuco": {"west": -41.5, "south": -10, "east": -34.5, "north": -7},
    "Alagoas": {"west": -38.5, "south": -10.5, "east": -35, "north": -8.5},
    "Sergipe": {"west": -38.5, "south": -11.5, "east": -36.5, "north": -9.5},
    "Bahia": {"west": -47, "south": -18.5, "east": -37.5, "north": -8.5},
    "Minas Gerais": {"west": -52, "south": -23, "east": -39.5, "north": -14},
    "Espirito Santo": {"west": -42, "south": -21.5, "east": -39.5, "north": -17.5},
    "Rio de Janeiro": {"west": -45, "south": -23.5, "east": -40.5, "north": -20.5},
    "Sao Paulo": {"west": -54, "south": -26, "east": -44, "north": -19.5},
    "Parana": {"west": -55, "south": -27, "east": -48, "north": -22.5},
    "Santa Catarina": {"west": -54, "south": -29.5, "east": -48, "north": -25.5},
    "Rio Grande do Sul": {"west": -58, "south": -34, "east": -49, "north": -27},
    "Mato Grosso do Sul": {"west": -58, "south": -25, "east": -53, "north": -17},
    "Mato Grosso": {"west": -62, "south": -18, "east": -50, "north": -7},
    "Goias": {"west": -53.5, "south": -20, "east": -45.5, "north": -12.5},
    "Distrito Federal": {"west": -48.5, "south": -16.1, "east": -47, "north": -15.4},
    "Rondonia": {"west": -67, "south": -14, "east": -59.5, "north": -7.5}
}

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

def get_state(lat, lon):
    """Determine Brazilian state based on coordinates."""
    for name, bounds in STATES.items():
        if bounds["west"] <= lon <= bounds["east"] and bounds["south"] <= lat <= bounds["north"]:
            return name
    return "Brasil"


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

        # Add location info
        cluster["state"] = get_state(cluster["center_lat"], cluster["center_lon"])
        biome_name, biome_data = get_biome(cluster["center_lat"], cluster["center_lon"])
        cluster["biome"] = biome_name

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
        .btn-secondary.active { background: #ff6b35; }
        .btn-danger { background: #dc2626; color: white; }
        .btn-danger:hover { background: #ef4444; }
        .view-btn.active { background: #ff6b35 !important; color: white !important; }
        .view-btn:hover { background: #333 !important; color: white !important; }
        .pulse { animation: pulse 1s infinite; }
        @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }

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

        /* Loading Indicator (discrete in header) */
        .loading-indicator {
            display: none;
            align-items: center;
            gap: 8px;
            padding: 6px 12px;
            background: rgba(255, 107, 53, 0.15);
            border-radius: 20px;
            font-size: 0.75em;
            color: #ff6b35;
        }
        .loading-indicator.active { display: flex; }
        .spinner-small {
            width: 14px;
            height: 14px;
            border: 2px solid #333;
            border-top-color: #ff6b35;
            border-radius: 50%;
            animation: spin 1s linear infinite;
        }
        @keyframes spin { to { transform: rotate(360deg); } }

        /* Legacy loading (hidden) */
        .loading { display: none !important; }

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
            <div class="loading-indicator active" id="loadingIndicator">
                <div class="spinner-small"></div>
                <span>Carregando...</span>
            </div>
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
                <div class="tab" data-tab="alerts">Alertas</div>
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
                    <button class="btn btn-primary" onclick="loadAllData(true)">Atualizar Dados</button>
                    <button class="btn btn-secondary active" id="autoRefreshBtn" onclick="toggleAutoRefresh()">⏸ Pausar</button>
                </div>

                <div class="panel">
                    <h3><span class="icon">🗺️</span> Visualizacao</h3>
                    <div style="display: flex; gap: 5px;">
                        <button class="view-btn active" data-view="markers" onclick="setViewMode('markers')" style="flex:1; padding: 8px; border: 1px solid #333; background: #ff6b35; color: white; border-radius: 4px; cursor: pointer; font-size: 0.8em;">Marcadores</button>
                        <button class="view-btn" data-view="heatmap" onclick="setViewMode('heatmap')" style="flex:1; padding: 8px; border: 1px solid #333; background: #0f0f1a; color: #888; border-radius: 4px; cursor: pointer; font-size: 0.8em;">Calor</button>
                        <button class="view-btn" data-view="both" onclick="setViewMode('both')" style="flex:1; padding: 8px; border: 1px solid #333; background: #0f0f1a; color: #888; border-radius: 4px; cursor: pointer; font-size: 0.8em;">Ambos</button>
                    </div>
                    <p style="font-size: 0.7em; color: #666; margin-top: 8px; text-align: center;">
                        Use o controle no mapa para trocar o estilo base (Escuro, Satelite, Terreno, Ruas)
                    </p>
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
                    <h3><span class="icon">🌤️</span> Clima Atual</h3>
                    <div id="currentBiome" style="font-size: 0.85em; color: #f7c873; margin-bottom: 10px;">Carregando...</div>
                    <div class="stat-grid">
                        <div class="stat-box">
                            <div class="stat-value" id="sidebarTemp" style="font-size: 1.3em;">-</div>
                            <div class="stat-label">Temperatura</div>
                        </div>
                        <div class="stat-box">
                            <div class="stat-value green" id="sidebarHumid" style="font-size: 1.3em;">-</div>
                            <div class="stat-label">Umidade</div>
                        </div>
                        <div class="stat-box">
                            <div class="stat-value" id="sidebarWind" style="font-size: 1.3em;">-</div>
                            <div class="stat-label">Vento</div>
                        </div>
                        <div class="stat-box">
                            <div class="stat-value" id="sidebarWindDir" style="font-size: 1.3em;">-</div>
                            <div class="stat-label">Direcao</div>
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

            <!-- Alerts Tab -->
            <div class="tab-content" id="tab-alerts">
                <div class="panel">
                    <h3><span class="icon">🚨</span> Sistema de Alertas</h3>
                    <div class="stat-grid">
                        <div class="stat-box">
                            <div class="stat-value red" id="alertLevel">-</div>
                            <div class="stat-label">Nivel de Alerta</div>
                        </div>
                        <div class="stat-box">
                            <div class="stat-value yellow" id="alertsActive">0</div>
                            <div class="stat-label">Alertas Ativos</div>
                        </div>
                    </div>
                </div>

                <div class="panel">
                    <h3><span class="icon">📍</span> Areas em Risco</h3>
                    <div id="riskAreasList" style="max-height: 200px; overflow-y: auto;">
                        <div style="color: #666; text-align: center; padding: 15px; font-size: 0.85em;">
                            Carregando areas de risco...
                        </div>
                    </div>
                </div>

                <div class="panel">
                    <h3><span class="icon">🛣️</span> Rotas de Evacuacao</h3>
                    <p style="font-size: 0.8em; color: #888; margin-bottom: 10px;">
                        Selecione um incendio na aba Previsao para ver rotas de evacuacao.
                    </p>
                    <div id="evacuationRoutes" style="max-height: 250px; overflow-y: auto;">
                        <div style="color: #666; text-align: center; padding: 15px; font-size: 0.85em;">
                            Nenhuma rota de evacuacao necessaria no momento.
                        </div>
                    </div>
                </div>

                <div class="panel">
                    <h3><span class="icon">📞</span> Contatos de Emergencia</h3>
                    <div style="font-size: 0.85em;">
                        <div style="display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid #333;">
                            <span>Bombeiros</span>
                            <span style="color: #ff6b35; font-weight: bold;">193</span>
                        </div>
                        <div style="display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid #333;">
                            <span>Defesa Civil</span>
                            <span style="color: #ff6b35; font-weight: bold;">199</span>
                        </div>
                        <div style="display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid #333;">
                            <span>SAMU</span>
                            <span style="color: #ff6b35; font-weight: bold;">192</span>
                        </div>
                        <div style="display: flex; justify-content: space-between; padding: 8px 0;">
                            <span>Policia Militar</span>
                            <span style="color: #ff6b35; font-weight: bold;">190</span>
                        </div>
                    </div>
                </div>

                <div class="panel">
                    <h3><span class="icon">📊</span> Area Queimada Total</h3>
                    <div class="stat-grid">
                        <div class="stat-box full">
                            <div class="stat-value" id="totalBurnedArea">-</div>
                            <div class="stat-label">Hectares Estimados</div>
                        </div>
                        <div class="stat-box">
                            <div class="stat-value yellow" id="burnedForest">-</div>
                            <div class="stat-label">Floresta (ha)</div>
                        </div>
                        <div class="stat-box">
                            <div class="stat-value" id="burnedOther">-</div>
                            <div class="stat-label">Outros (ha)</div>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <div class="map-container">
            <div id="map"></div>


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
                <div class="info-chip" id="liveIndicator" style="background: rgba(255,107,53,0.3);">
                    <span style="color: #ff6b35;">●</span>
                    <span class="value" style="color: #ff6b35;">AO VIVO</span>
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
    <script src="https://unpkg.com/leaflet.heat@0.2.0/dist/leaflet-heat.js"></script>
    <script>
        // ========================================
        // Configuration
        // ========================================
        let autoRefreshInterval = null;
        let autoRefreshEnabled = false;
        let currentViewMode = 'markers'; // 'markers', 'heatmap', 'both'
        let heatLayer = null;

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
        // Initialize Map with Multiple Layers
        // ========================================
        const map = L.map('map').setView([-22, -48], 6);

        // Base layers - Google Maps as default
        const googleMaps = L.tileLayer('https://mt1.google.com/vt/lyrs=r&x={x}&y={y}&z={z}', {
            attribution: '&copy; Google Maps',
            maxZoom: 20
        });

        const googleSatellite = L.tileLayer('https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}', {
            attribution: '&copy; Google Satellite',
            maxZoom: 20
        });

        const googleHybrid = L.tileLayer('https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}', {
            attribution: '&copy; Google Hybrid',
            maxZoom: 20
        });

        const googleTerrain = L.tileLayer('https://mt1.google.com/vt/lyrs=p&x={x}&y={y}&z={z}', {
            attribution: '&copy; Google Terrain',
            maxZoom: 20
        });

        const darkLayer = L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
            attribution: '&copy; CartoDB',
            maxZoom: 19
        });

        // Add Google Maps as default layer
        googleMaps.addTo(map);

        // Layer control
        const baseLayers = {
            'Google Maps': googleMaps,
            'Google Satellite': googleSatellite,
            'Google Hybrid': googleHybrid,
            'Google Terrain': googleTerrain,
            'Modo Escuro': darkLayer
        };
        L.control.layers(baseLayers, null, { position: 'topright' }).addTo(map);

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

        // Brazilian states boundaries (simplified)
        const states = {
            "Acre": {west: -74, south: -11.5, east: -66.5, north: -7},
            "Amazonas": {west: -74, south: -10, east: -56, north: 2.5},
            "Roraima": {west: -65, south: 0, east: -58, north: 5.5},
            "Para": {west: -59, south: -10, east: -46, north: 3},
            "Amapa": {west: -55, south: -1, east: -49, north: 5},
            "Tocantins": {west: -51, south: -14, east: -45.5, north: -5},
            "Maranhao": {west: -49, south: -11, east: -41, north: -1},
            "Piaui": {west: -46, south: -11, east: -40.5, north: -2.5},
            "Ceara": {west: -42, south: -8, east: -37, north: -2.5},
            "Rio Grande do Norte": {west: -38.5, south: -7, east: -34.5, north: -4.5},
            "Paraiba": {west: -39, south: -8.5, east: -34.5, north: -6},
            "Pernambuco": {west: -41.5, south: -10, east: -34.5, north: -7},
            "Alagoas": {west: -38.5, south: -10.5, east: -35, north: -8.5},
            "Sergipe": {west: -38.5, south: -11.5, east: -36.5, north: -9.5},
            "Bahia": {west: -47, south: -18.5, east: -37.5, north: -8.5},
            "Minas Gerais": {west: -52, south: -23, east: -39.5, north: -14},
            "Espirito Santo": {west: -42, south: -21.5, east: -39.5, north: -17.5},
            "Rio de Janeiro": {west: -45, south: -23.5, east: -40.5, north: -20.5},
            "Sao Paulo": {west: -54, south: -26, east: -44, north: -19.5},
            "Parana": {west: -55, south: -27, east: -48, north: -22.5},
            "Santa Catarina": {west: -54, south: -29.5, east: -48, north: -25.5},
            "Rio Grande do Sul": {west: -58, south: -34, east: -49, north: -27},
            "Mato Grosso do Sul": {west: -58, south: -25, east: -53, north: -17},
            "Mato Grosso": {west: -62, south: -18, east: -50, north: -7},
            "Goias": {west: -53.5, south: -20, east: -45.5, north: -12.5},
            "Distrito Federal": {west: -48.5, south: -16.1, east: -47, north: -15.4},
            "Rondonia": {west: -67, south: -14, east: -59.5, north: -7.5}
        };

        function getStateName(lat, lon) {
            for (const [name, bounds] of Object.entries(states)) {
                if (lon >= bounds.west && lon <= bounds.east && lat >= bounds.south && lat <= bounds.north) {
                    return name;
                }
            }
            return 'Brasil';
        }

        function showLoading() {
            document.getElementById('loadingIndicator').classList.add('active');
        }

        function hideLoading() {
            document.getElementById('loadingIndicator').classList.remove('active');
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

        async function fetchLocationInfo(lat, lon) {
            const droughtDays = parseInt(document.getElementById('droughtDays').value) || 5;
            const url = '/api/location?lat=' + lat + '&lon=' + lon + '&days_without_rain=' + droughtDays;
            const response = await fetch(url);
            return await response.json();
        }

        async function fetchEvacuation(lat, lon, radius) {
            const url = '/api/evacuation?lat=' + lat + '&lon=' + lon + '&radius=' + radius;
            const response = await fetch(url);
            return await response.json();
        }

        async function fetchBurnedArea(coords, days) {
            const url = '/api/burned-area?west=' + coords.west + '&south=' + coords.south + '&east=' + coords.east + '&north=' + coords.north + '&days=' + days;
            const response = await fetch(url);
            return await response.json();
        }

        // ========================================
        // Heat Map Functions
        // ========================================
        function updateHeatMap() {
            if (heatLayer) {
                map.removeLayer(heatLayer);
            }

            if (currentViewMode === 'markers') return;

            const heatData = currentHotspots.map(h => [
                h.latitude,
                h.longitude,
                Math.min(1, h.frp / 100)  // Normalize intensity
            ]);

            heatLayer = L.heatLayer(heatData, {
                radius: 25,
                blur: 15,
                maxZoom: 10,
                max: 1.0,
                gradient: {
                    0.0: '#ffffb2',
                    0.25: '#fecc5c',
                    0.5: '#fd8d3c',
                    0.75: '#f03b20',
                    1.0: '#bd0026'
                }
            }).addTo(map);
        }

        function setViewMode(mode) {
            currentViewMode = mode;

            // Update buttons
            document.querySelectorAll('.view-btn').forEach(btn => btn.classList.remove('active'));
            document.querySelector('[data-view="' + mode + '"]').classList.add('active');

            // Update layers
            if (mode === 'markers') {
                if (heatLayer) map.removeLayer(heatLayer);
                map.addLayer(markers);
            } else if (mode === 'heatmap') {
                map.removeLayer(markers);
                updateHeatMap();
            } else { // both
                map.addLayer(markers);
                updateHeatMap();
            }
        }

        // ========================================
        // Auto Refresh Functions
        // ========================================
        function toggleAutoRefresh() {
            autoRefreshEnabled = !autoRefreshEnabled;
            const btn = document.getElementById('autoRefreshBtn');
            const indicator = document.getElementById('liveIndicator');

            if (autoRefreshEnabled) {
                btn.classList.add('active');
                btn.innerHTML = '⏸ Pausar';
                indicator.style.display = 'flex';
                indicator.classList.add('pulse');
                autoRefreshInterval = setInterval(() => loadAllData(false), 5000);
            } else {
                btn.classList.remove('active');
                btn.innerHTML = '▶ Auto (5s)';
                indicator.style.display = 'none';
                indicator.classList.remove('pulse');
                clearInterval(autoRefreshInterval);
            }
        }

        // ========================================
        // Load All Data
        // ========================================
        async function loadAllData(fitBounds = false) {
            const region = document.getElementById('regionSelect').value;
            const days = document.getElementById('daysSelect').value;
            const coords = regions[region];
            const droughtDays = parseInt(document.getElementById('droughtDays').value) || 5;

            if (!autoRefreshEnabled) showLoading();

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

                // Update alerts tab
                updateAlertsTab(clustersData, riskData);

                // Update timestamp
                document.getElementById('lastUpdate').textContent = new Date().toLocaleTimeString('pt-BR');

                // Update heat map if active
                if (currentViewMode !== 'markers') {
                    updateHeatMap();
                }

                // Fit map only on first load or manual refresh
                if (fitBounds && currentHotspots.length > 0) {
                    map.fitBounds(markers.getBounds(), { padding: [50, 50] });
                }

                // Hide loading indicator after successful load
                hideLoading();

            } catch (error) {
                console.error('Error loading data:', error);
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

                // Find state for this hotspot
                const state = getStateName(h.latitude, h.longitude);

                const popup = '<div style="font-family: sans-serif; min-width: 200px;">' +
                    '<h4 style="color: #ff6b35; margin: 0 0 8px 0; border-bottom: 1px solid #ddd; padding-bottom: 5px;">🔥 Foco de Incendio</h4>' +
                    '<p style="margin: 4px 0; font-weight: bold; color: #333;">📍 ' + state + '</p>' +
                    '<p style="margin: 4px 0; font-size: 0.85em; color: #666;">' + h.latitude.toFixed(5) + ', ' + h.longitude.toFixed(5) + '</p>' +
                    '<hr style="border: none; border-top: 1px solid #eee; margin: 8px 0;">' +
                    '<p style="margin: 4px 0;"><strong>FRP:</strong> <span style="color: ' + (h.frp > 50 ? '#dc2626' : h.frp > 10 ? '#f97316' : '#eab308') + '; font-weight: bold;">' + h.frp.toFixed(1) + ' MW</span></p>' +
                    '<p style="margin: 4px 0;"><strong>Brilho:</strong> ' + h.brightness.toFixed(1) + ' K</p>' +
                    '<p style="margin: 4px 0;"><strong>Confianca:</strong> ' + h.confidence + '</p>' +
                    '<p style="margin: 4px 0;"><strong>Satelite:</strong> ' + h.satellite + '</p>' +
                    '<p style="margin: 4px 0;"><strong>Data/Hora:</strong> ' + h.acq_datetime + '</p>' +
                    '<p style="margin: 4px 0;"><strong>Periodo:</strong> ' + (h.daynight === 'D' ? '☀️ Diurno' : '🌙 Noturno') + '</p>' +
                    '<hr style="border: none; border-top: 1px solid #eee; margin: 8px 0;">' +
                    '<p style="margin: 4px 0; font-size: 0.8em; color: #888;">Clique para ver dados climaticos</p>' +
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

            // Update sidebar weather panel
            document.getElementById('sidebarTemp').textContent = weather.temperature + '°C';
            document.getElementById('sidebarHumid').textContent = weather.humidity + '%';
            document.getElementById('sidebarWind').textContent = weather.wind_speed + ' km/h';
            document.getElementById('sidebarWindDir').textContent = getWindDirection(weather.wind_direction);
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
                        '<span class="cluster-id">' + (c.state || 'Brasil') + '</span>' +
                        '<span class="cluster-count">' + c.count + ' focos</span>' +
                    '</div>' +
                    '<div style="font-size: 0.7em; color: #f7c873; margin: 4px 0;">' + (c.biome || '') + '</div>' +
                    '<div class="cluster-details">' +
                        '<span>FRP: ' + c.total_frp.toFixed(1) + ' MW</span>' +
                        '<span>Area: ' + c.estimated_area_ha + ' ha</span>' +
                    '</div>' +
                '</div>'
            ).join('');
        }

        function updateFireSelect() {
            const select = document.getElementById('fireSelect');
            select.innerHTML = '<option value="">Selecione um incendio...</option>';

            currentClusters.slice(0, 20).forEach(c => {
                const location = c.state || 'Brasil';
                select.innerHTML += '<option value="' + c.id + '">' + location + ' - ' + c.count + ' focos (' + c.estimated_area_ha + ' ha)</option>';
            });
        }

        function updateAlertsTab(clustersData, riskData) {
            const clusters = clustersData.clusters || [];

            // Calculate total burned area
            const totalArea = clusters.reduce((sum, c) => sum + (c.estimated_area_ha || 0), 0);
            const forestArea = Math.round(totalArea * 0.65); // Estimate 65% forest
            const otherArea = Math.round(totalArea * 0.35);

            document.getElementById('totalBurnedArea').textContent = totalArea.toFixed(0);
            document.getElementById('burnedForest').textContent = forestArea;
            document.getElementById('burnedOther').textContent = otherArea;

            // Determine alert level based on risk
            const riskIndex = riskData ? riskData.risk_index : 0;
            let alertLevel = 'NORMAL';
            let alertsActive = 0;

            if (riskIndex >= 80) {
                alertLevel = 'CRITICO';
                alertsActive = clusters.length;
            } else if (riskIndex >= 60) {
                alertLevel = 'ALTO';
                alertsActive = Math.ceil(clusters.length * 0.7);
            } else if (riskIndex >= 40) {
                alertLevel = 'MODERADO';
                alertsActive = Math.ceil(clusters.length * 0.3);
            } else if (riskIndex >= 20) {
                alertLevel = 'BAIXO';
                alertsActive = Math.ceil(clusters.length * 0.1);
            }

            document.getElementById('alertLevel').textContent = alertLevel;
            document.getElementById('alertsActive').textContent = alertsActive;

            // Color based on alert level
            const alertEl = document.getElementById('alertLevel');
            alertEl.className = 'stat-value';
            if (alertLevel === 'CRITICO') alertEl.classList.add('red');
            else if (alertLevel === 'ALTO') alertEl.classList.add('yellow');
            else alertEl.classList.add('green');

            // Update risk areas list
            updateRiskAreasList(clusters);
        }

        function updateRiskAreasList(clusters) {
            const list = document.getElementById('riskAreasList');

            if (clusters.length === 0) {
                list.innerHTML = '<div style="color: #666; text-align: center; padding: 15px; font-size: 0.85em;">Nenhuma area em risco no momento</div>';
                return;
            }

            // Group by state
            const byState = {};
            clusters.forEach(c => {
                const state = c.state || 'Desconhecido';
                if (!byState[state]) {
                    byState[state] = { count: 0, area: 0, frp: 0 };
                }
                byState[state].count += c.count;
                byState[state].area += c.estimated_area_ha || 0;
                byState[state].frp += c.total_frp || 0;
            });

            // Sort by area
            const sorted = Object.entries(byState)
                .sort((a, b) => b[1].area - a[1].area)
                .slice(0, 8);

            list.innerHTML = sorted.map(([state, data]) => {
                const severity = data.area > 100 ? 'red' : data.area > 30 ? 'yellow' : 'green';
                return '<div style="padding: 10px; border-bottom: 1px solid #333; display: flex; justify-content: space-between; align-items: center;">' +
                    '<div>' +
                        '<div style="font-weight: bold; color: #fff;">' + state + '</div>' +
                        '<div style="font-size: 0.75em; color: #888;">' + data.count + ' focos</div>' +
                    '</div>' +
                    '<div style="text-align: right;">' +
                        '<div style="font-weight: bold; color: var(--' + severity + ', #ff6b35);">' + data.area.toFixed(0) + ' ha</div>' +
                        '<div style="font-size: 0.75em; color: #888;">FRP: ' + data.frp.toFixed(0) + '</div>' +
                    '</div>' +
                '</div>';
            }).join('');
        }

        // ========================================
        // Cluster Functions
        // ========================================
        function focusCluster(id) {
            const cluster = currentClusters.find(c => c.id === id);
            if (cluster) {
                map.setView([cluster.center_lat, cluster.center_lon], 10);
                selectCluster(cluster);
                loadLocationData(cluster.center_lat, cluster.center_lon);
            }
        }

        function selectCluster(cluster) {
            selectedCluster = cluster;
            document.getElementById('fireSelect').value = cluster.id;

            // Highlight selected in list
            document.querySelectorAll('.cluster-item').forEach((el, i) => {
                el.style.borderLeftColor = (currentClusters[i] && currentClusters[i].id === cluster.id) ? '#4ade80' : '#ff6b35';
            });
        }

        function selectHotspot(hotspot) {
            // Load location data for this hotspot
            loadLocationData(hotspot.latitude, hotspot.longitude);

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

        async function loadLocationData(lat, lon) {
            try {
                const data = await fetchLocationInfo(lat, lon);

                // Update weather display for this specific location
                document.getElementById('weatherTemp').textContent = data.weather.temperature + '°C';
                document.getElementById('weatherHumid').textContent = data.weather.humidity + '%';
                document.getElementById('weatherWind').textContent = data.weather.wind_speed + ' km/h';
                document.getElementById('weatherDir').textContent = getWindDirection(data.weather.wind_direction);

                // Update current biome display
                document.getElementById('currentBiome').textContent = data.state + ' - ' + data.biome;

                // Update risk display
                document.getElementById('riskValue').textContent = data.risk.index;
                document.getElementById('riskLevel').textContent = data.risk.level;
                document.getElementById('riskIndicator').style.left = data.risk.index + '%';
                document.getElementById('headerRisk').textContent = data.risk.level;

                // Color based on risk
                const riskEl = document.getElementById('riskValue');
                riskEl.className = 'risk-value';
                if (data.risk.index >= 60) riskEl.classList.add('red');
                else if (data.risk.index >= 40) riskEl.classList.add('yellow');
                else riskEl.classList.add('green');

                // Update factors
                document.getElementById('tempValue').textContent = data.weather.temperature + '°C';
                document.getElementById('tempBar').style.width = Math.min(100, (data.weather.temperature - 20) * 4) + '%';
                document.getElementById('humidValue').textContent = data.weather.humidity + '%';
                document.getElementById('humidBar').style.width = (100 - data.weather.humidity) + '%';
                document.getElementById('windValue').textContent = data.weather.wind_speed + ' km/h';
                document.getElementById('windBar').style.width = Math.min(100, data.weather.wind_speed * 2) + '%';

                // Update biome info
                document.getElementById('biomeName').textContent = data.biome;
                document.getElementById('biomeCarbon').textContent = data.biome_data.carbon_tons_ha;
                document.getElementById('biomeRecovery').textContent = data.biome_data.recovery_years;

                // Update weather current location
                currentWeather = data.weather;

            } catch (error) {
                console.error('Error loading location data:', error);
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

            // Update evacuation routes in Alerts tab
            updateEvacuationRoutes(cluster.center_lat, cluster.center_lon, lastPred.radius_m / 1000);

            // Fit map to show predictions
            if (predictionCircles.length > 0) {
                const group = L.featureGroup(predictionCircles);
                map.fitBounds(group.getBounds(), { padding: [50, 50] });
            }
        }

        async function updateEvacuationRoutes(lat, lon, radius) {
            try {
                const data = await fetchEvacuation(lat, lon, radius);
                const routesDiv = document.getElementById('evacuationRoutes');

                if (data.routes && data.routes.length > 0) {
                    routesDiv.innerHTML = data.routes.map(r =>
                        '<div style="padding: 10px; border-bottom: 1px solid #333; ' + (r.recommended ? 'background: rgba(74, 222, 128, 0.1);' : '') + '">' +
                            '<div style="display: flex; justify-content: space-between; align-items: center;">' +
                                '<div>' +
                                    '<div style="font-weight: bold; color: ' + (r.recommended ? '#4ade80' : '#fff') + ';">' +
                                        (r.recommended ? '✓ ' : '') + 'Rota ' + r.direction +
                                    '</div>' +
                                    '<div style="font-size: 0.75em; color: #888;">' + r.road_type + '</div>' +
                                '</div>' +
                                '<div style="text-align: right;">' +
                                    '<div style="font-weight: bold; color: #ff6b35;">' + r.distance_km + ' km</div>' +
                                    '<div style="font-size: 0.75em; color: #888;">' + r.estimated_time_min + ' min</div>' +
                                '</div>' +
                            '</div>' +
                        '</div>'
                    ).join('');

                    // Add shelter info
                    if (data.shelter_points && data.shelter_points.length > 0) {
                        routesDiv.innerHTML += '<div style="padding: 10px; background: rgba(255, 107, 53, 0.1); margin-top: 10px; border-radius: 6px;">' +
                            '<div style="font-weight: bold; color: #f7c873; margin-bottom: 8px;">Pontos de Abrigo</div>' +
                            data.shelter_points.map(s =>
                                '<div style="display: flex; justify-content: space-between; padding: 4px 0; font-size: 0.85em;">' +
                                    '<span>' + s.name + '</span>' +
                                    '<span style="color: #888;">' + s.distance_km + ' km</span>' +
                                '</div>'
                            ).join('') +
                        '</div>';
                    }
                }
            } catch (error) {
                console.error('Error loading evacuation routes:', error);
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
            loadAllData(false);
        });

        // ========================================
        // Initialize
        // ========================================
        loadAllData(true);

        // Start auto-refresh by default
        setTimeout(() => {
            toggleAutoRefresh();
        }, 1000);
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
                "version": "0.4.0",
                "api_key_configured": bool(FIRMS_API_KEY),
                "features": ["hotspots", "weather", "risk", "clusters", "emissions", "prediction", "location", "evacuation", "burned-area"]
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

        # Location info endpoint
        if path == "/api/location":
            try:
                lat = float(query.get("lat", [-22])[0])
                lon = float(query.get("lon", [-48])[0])

                state = get_state(lat, lon)
                biome_name, biome_data = get_biome(lat, lon)
                weather, _ = fetch_weather(lat, lon)

                # Calculate risk
                days_without_rain = int(query.get("days_without_rain", [5])[0])
                risk_index = calculate_risk_index(
                    weather["temperature"],
                    weather["humidity"],
                    weather["wind_speed"],
                    days_without_rain
                )

                self.send_json(200, {
                    "state": state,
                    "biome": biome_name,
                    "coordinates": {"lat": lat, "lon": lon},
                    "weather": weather,
                    "risk": {
                        "index": risk_index,
                        "level": get_risk_level(risk_index)
                    },
                    "biome_data": {
                        "carbon_tons_ha": biome_data["carbon_tons_ha"],
                        "recovery_years": biome_data.get("recovery_years", 20),
                        "spread_factor": biome_data.get("spread_factor", 1.0)
                    }
                })
            except Exception as e:
                self.send_json(400, {"error": str(e)})
            return

        # Evacuation routes endpoint
        if path == "/api/evacuation":
            try:
                lat = float(query.get("lat", [-22])[0])
                lon = float(query.get("lon", [-48])[0])
                radius_km = float(query.get("radius", [10])[0])

                state = get_state(lat, lon)
                biome_name, _ = get_biome(lat, lon)

                # Generate evacuation recommendations based on location
                cardinal_directions = ["Norte", "Sul", "Leste", "Oeste", "Nordeste", "Sudeste"]
                routes = []

                for i, direction in enumerate(cardinal_directions[:4]):
                    routes.append({
                        "id": i + 1,
                        "direction": direction,
                        "distance_km": round(radius_km * (1 + i * 0.3), 1),
                        "estimated_time_min": round(radius_km * (1 + i * 0.3) * 2, 0),
                        "road_type": "Principal" if i < 2 else "Secundaria",
                        "recommended": i == 0
                    })

                self.send_json(200, {
                    "center": {"lat": lat, "lon": lon},
                    "state": state,
                    "biome": biome_name,
                    "evacuation_radius_km": radius_km,
                    "routes": routes,
                    "shelter_points": [
                        {"name": "Ginasio Municipal", "type": "Abrigo", "distance_km": round(radius_km * 0.8, 1)},
                        {"name": "Escola Estadual", "type": "Ponto de Apoio", "distance_km": round(radius_km * 1.2, 1)}
                    ],
                    "emergency_contacts": {
                        "bombeiros": "193",
                        "defesa_civil": "199",
                        "samu": "192"
                    }
                })
            except Exception as e:
                self.send_json(400, {"error": str(e)})
            return

        # Burned area endpoint
        if path == "/api/burned-area":
            try:
                west = float(query.get("west", [-74])[0])
                south = float(query.get("south", [-33])[0])
                east = float(query.get("east", [-34])[0])
                north = float(query.get("north", [5])[0])
                days = int(query.get("days", [1])[0])

                # Get hotspots to estimate burned area
                hotspots, error = fetch_hotspots(west, south, east, north, days)

                if error:
                    self.send_json(500, {"error": error})
                    return

                if not hotspots:
                    self.send_json(200, {
                        "total_area_ha": 0,
                        "hotspot_count": 0,
                        "by_biome": {},
                        "by_state": {}
                    })
                    return

                # Calculate area by clustering
                clusters = cluster_hotspots(hotspots)
                total_area = sum(c.get("estimated_area_ha", 0) for c in clusters)

                # Group by biome and state
                by_biome = {}
                by_state = {}

                for c in clusters:
                    biome = c.get("biome", "Desconhecido")
                    state = c.get("state", "Desconhecido")
                    area = c.get("estimated_area_ha", 0)

                    by_biome[biome] = by_biome.get(biome, 0) + area
                    by_state[state] = by_state.get(state, 0) + area

                self.send_json(200, {
                    "total_area_ha": round(total_area, 1),
                    "hotspot_count": len(hotspots),
                    "cluster_count": len(clusters),
                    "by_biome": {k: round(v, 1) for k, v in by_biome.items()},
                    "by_state": {k: round(v, 1) for k, v in by_state.items()},
                    "severity": {
                        "severe_ha": round(total_area * 0.15, 1),
                        "moderate_ha": round(total_area * 0.50, 1),
                        "light_ha": round(total_area * 0.35, 1)
                    }
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
