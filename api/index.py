"""
FireWatch AI - Vercel Serverless API
Simple HTTP handler version (no external dependencies)
"""

import json
import os
from urllib.request import urlopen, Request
from urllib.parse import parse_qs, urlparse
from http.server import BaseHTTPRequestHandler

FIRMS_API_KEY = os.environ.get("FIRMS_API_KEY", "")
FIRMS_BASE_URL = "https://firms.modaps.eosdis.nasa.gov/api"


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


def get_landing_page():
    """Return HTML landing page."""
    return """<!DOCTYPE html>
<html>
<head>
    <title>FireWatch AI</title>
    <meta charset="utf-8">
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
            font-family: monospace;
            display: inline-block;
            margin: 5px 0;
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
        hr { border: none; border-top: 1px solid #333; margin: 40px 0; }
    </style>
</head>
<body>
    <h1>FireWatch AI</h1>
    <p class="subtitle">Open-source wildfire detection platform using NASA FIRMS satellite data.</p>

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

    <h3>API Endpoints</h3>
    <div class="endpoint">
        <span class="tag">GET</span>
        <code>/api/health</code> - Health check
    </div>
    <div class="endpoint">
        <span class="tag">GET</span>
        <code>/api/hotspots?west=-50&south=-25&east=-44&north=-19</code> - Get fire hotspots
    </div>

    <h3>Example: Fires in Sao Paulo Region</h3>
    <p><a href="/api/hotspots?west=-50&south=-25&east=-44&north=-19&days=2">/api/hotspots?west=-50&south=-25&east=-44&north=-19&days=2</a></p>

    <h3>Example: Fires in Amazon</h3>
    <p><a href="/api/hotspots?west=-70&south=-10&east=-50&north=5&days=1">/api/hotspots?west=-70&south=-10&east=-50&north=5&days=1</a></p>

    <hr>
    <footer>
        <p>
            <a href="https://github.com/Cnk1Ra/FireWatch-AI">GitHub Repository</a> |
            Data: <a href="https://firms.modaps.eosdis.nasa.gov/">NASA FIRMS</a>
        </p>
        <p>Version 0.2.0</p>
    </footer>
</body>
</html>"""


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)

        # Landing page
        if path == "/" or path == "":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(get_landing_page().encode("utf-8"))
            return

        # Health check
        if path == "/api/health" or path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            response = {
                "status": "healthy",
                "version": "0.2.0",
                "api_key_configured": bool(FIRMS_API_KEY)
            }
            self.wfile.write(json.dumps(response).encode("utf-8"))
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
                    self.send_response(500)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps({"error": error}).encode("utf-8"))
                    return

                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                response = {
                    "count": len(hotspots),
                    "source": "VIIRS_NOAA20_NRT",
                    "hotspots": hotspots[:500]  # Limit to 500 results
                }
                self.wfile.write(json.dumps(response).encode("utf-8"))
                return

            except Exception as e:
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))
                return

        # 404 for other paths
        self.send_response(404)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"error": "Not found"}).encode("utf-8"))
