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


def get_dashboard_page():
    """Return HTML dashboard with interactive map."""
    return """<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <title>FireWatch AI - Dashboard</title>
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
        }
        .header {
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            padding: 15px 20px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid #333;
        }
        .logo { color: #ff6b35; font-size: 1.5em; font-weight: bold; }
        .logo span { color: #f7c873; }
        .container {
            display: grid;
            grid-template-columns: 300px 1fr;
            height: calc(100vh - 60px);
        }
        .sidebar {
            background: #1a1a2e;
            padding: 20px;
            overflow-y: auto;
            border-right: 1px solid #333;
        }
        .panel {
            background: #16213e;
            border-radius: 8px;
            padding: 15px;
            margin-bottom: 15px;
        }
        .panel h3 {
            color: #f7c873;
            font-size: 0.9em;
            margin-bottom: 15px;
            text-transform: uppercase;
            letter-spacing: 1px;
        }
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
        .stat-value {
            font-size: 1.8em;
            font-weight: bold;
            color: #ff6b35;
        }
        .stat-label {
            font-size: 0.75em;
            color: #888;
            margin-top: 5px;
        }
        .form-group {
            margin-bottom: 12px;
        }
        .form-group label {
            display: block;
            font-size: 0.85em;
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
        .btn {
            width: 100%;
            padding: 12px;
            border: none;
            border-radius: 6px;
            font-size: 1em;
            font-weight: bold;
            cursor: pointer;
            transition: all 0.2s;
        }
        .btn-primary {
            background: #ff6b35;
            color: white;
        }
        .btn-primary:hover {
            background: #ff8555;
        }
        .btn-secondary {
            background: #333;
            color: white;
            margin-top: 8px;
        }
        .btn-secondary:hover {
            background: #444;
        }
        #map {
            width: 100%;
            height: 100%;
            background: #0a0a15;
        }
        .loading {
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            background: rgba(0,0,0,0.8);
            padding: 20px 40px;
            border-radius: 10px;
            z-index: 1000;
            display: none;
        }
        .loading.active { display: block; }
        .spinner {
            width: 40px;
            height: 40px;
            border: 4px solid #333;
            border-top-color: #ff6b35;
            border-radius: 50%;
            animation: spin 1s linear infinite;
            margin: 0 auto 10px;
        }
        @keyframes spin { to { transform: rotate(360deg); } }
        .legend {
            background: #16213e;
            padding: 10px;
            border-radius: 6px;
            margin-top: 15px;
        }
        .legend-item {
            display: flex;
            align-items: center;
            margin: 5px 0;
            font-size: 0.85em;
        }
        .legend-color {
            width: 16px;
            height: 16px;
            border-radius: 50%;
            margin-right: 10px;
        }
        .hotspot-popup {
            font-family: -apple-system, BlinkMacSystemFont, sans-serif;
        }
        .hotspot-popup h4 {
            color: #ff6b35;
            margin-bottom: 8px;
        }
        .hotspot-popup p {
            margin: 4px 0;
            font-size: 0.9em;
        }
        .map-container {
            position: relative;
        }
        .map-overlay {
            position: absolute;
            top: 10px;
            right: 10px;
            z-index: 1000;
            background: rgba(26, 26, 46, 0.95);
            padding: 10px 15px;
            border-radius: 8px;
            font-size: 0.85em;
        }
        @media (max-width: 768px) {
            .container {
                grid-template-columns: 1fr;
            }
            .sidebar {
                display: none;
            }
        }
    </style>
</head>
<body>
    <div class="header">
        <div class="logo">FireWatch <span>AI</span></div>
        <div style="color: #888; font-size: 0.9em;">
            Real-time Fire Detection | NASA FIRMS Data
        </div>
    </div>

    <div class="container">
        <div class="sidebar">
            <div class="panel">
                <h3>Estatisticas</h3>
                <div class="stat-grid">
                    <div class="stat-box">
                        <div class="stat-value" id="totalFires">-</div>
                        <div class="stat-label">Focos Ativos</div>
                    </div>
                    <div class="stat-box">
                        <div class="stat-value" id="highConf">-</div>
                        <div class="stat-label">Alta Confianca</div>
                    </div>
                    <div class="stat-box">
                        <div class="stat-value" id="avgFRP">-</div>
                        <div class="stat-label">FRP Medio (MW)</div>
                    </div>
                    <div class="stat-box">
                        <div class="stat-value" id="maxFRP">-</div>
                        <div class="stat-label">FRP Maximo</div>
                    </div>
                </div>
            </div>

            <div class="panel">
                <h3>Filtros</h3>
                <div class="form-group">
                    <label>Regiao</label>
                    <select id="regionSelect">
                        <option value="brazil">Brasil Completo</option>
                        <option value="amazon">Amazonia</option>
                        <option value="cerrado">Cerrado</option>
                        <option value="pantanal">Pantanal</option>
                        <option value="saopaulo" selected>Sao Paulo</option>
                        <option value="nordeste">Nordeste</option>
                        <option value="sul">Sul</option>
                        <option value="custom">Personalizado</option>
                    </select>
                </div>
                <div class="form-group">
                    <label>Periodo (dias)</label>
                    <select id="daysSelect">
                        <option value="1">Ultimo dia</option>
                        <option value="2" selected>Ultimos 2 dias</option>
                        <option value="3">Ultimos 3 dias</option>
                        <option value="5">Ultimos 5 dias</option>
                        <option value="7">Ultima semana</option>
                    </select>
                </div>
                <button class="btn btn-primary" onclick="loadHotspots()">Atualizar Dados</button>
                <button class="btn btn-secondary" onclick="clearMap()">Limpar Mapa</button>
            </div>

            <div class="panel">
                <h3>Legenda</h3>
                <div class="legend">
                    <div class="legend-item">
                        <div class="legend-color" style="background: #ff0000;"></div>
                        <span>Alta intensidade (FRP > 50)</span>
                    </div>
                    <div class="legend-item">
                        <div class="legend-color" style="background: #ff6b35;"></div>
                        <span>Media intensidade (FRP 10-50)</span>
                    </div>
                    <div class="legend-item">
                        <div class="legend-color" style="background: #f7c873;"></div>
                        <span>Baixa intensidade (FRP < 10)</span>
                    </div>
                </div>
            </div>

            <div class="panel">
                <h3>Sobre</h3>
                <p style="font-size: 0.85em; color: #aaa; line-height: 1.5;">
                    FireWatch AI detecta focos de incendio em tempo real usando dados do satelite VIIRS da NASA FIRMS.
                </p>
                <p style="font-size: 0.8em; color: #666; margin-top: 10px;">
                    <a href="/" style="color: #ff6b35;">API Documentation</a> |
                    <a href="https://github.com/Cnk1Ra/FireWatch-AI" style="color: #ff6b35;">GitHub</a>
                </p>
            </div>
        </div>

        <div class="map-container">
            <div id="map"></div>
            <div class="loading" id="loading">
                <div class="spinner"></div>
                <div>Carregando dados...</div>
            </div>
            <div class="map-overlay">
                <strong>Ultima atualizacao:</strong> <span id="lastUpdate">-</span>
            </div>
        </div>
    </div>

    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <script src="https://unpkg.com/leaflet.markercluster@1.4.1/dist/leaflet.markercluster.js"></script>
    <script>
        // Regions configuration
        const regions = {
            brazil: { west: -74, south: -34, east: -34, north: 5, center: [-14, -52], zoom: 4 },
            amazon: { west: -74, south: -10, east: -44, north: 5, center: [-3, -60], zoom: 5 },
            cerrado: { west: -60, south: -24, east: -41, north: -2, center: [-15, -47], zoom: 5 },
            pantanal: { west: -59, south: -22, east: -54, north: -15, center: [-18, -56], zoom: 6 },
            saopaulo: { west: -53, south: -26, east: -44, north: -19, center: [-22, -48], zoom: 6 },
            nordeste: { west: -48, south: -18, east: -34, north: -2, center: [-9, -38], zoom: 5 },
            sul: { west: -58, south: -34, east: -48, north: -22, center: [-27, -51], zoom: 5 },
            custom: { west: -74, south: -34, east: -34, north: 5, center: [-14, -52], zoom: 4 }
        };

        // Initialize map
        const map = L.map('map').setView([-22, -48], 6);

        // Dark tile layer
        L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
            attribution: '&copy; OpenStreetMap, &copy; CartoDB',
            maxZoom: 19
        }).addTo(map);

        // Marker cluster group
        let markers = L.markerClusterGroup({
            maxClusterRadius: 50,
            spiderfyOnMaxZoom: true,
            showCoverageOnHover: false,
            iconCreateFunction: function(cluster) {
                const count = cluster.getChildCount();
                let size = 'small';
                if (count > 100) size = 'large';
                else if (count > 50) size = 'medium';

                return L.divIcon({
                    html: '<div style="background: rgba(255,107,53,0.9); color: white; border-radius: 50%; width: 40px; height: 40px; display: flex; align-items: center; justify-content: center; font-weight: bold; border: 2px solid #fff;">' + count + '</div>',
                    className: 'marker-cluster',
                    iconSize: L.point(40, 40)
                });
            }
        });
        map.addLayer(markers);

        // Get marker color based on FRP
        function getMarkerColor(frp) {
            if (frp > 50) return '#ff0000';
            if (frp > 10) return '#ff6b35';
            return '#f7c873';
        }

        // Create fire icon
        function createFireIcon(frp) {
            const color = getMarkerColor(frp);
            const size = frp > 50 ? 12 : (frp > 10 ? 10 : 8);
            return L.divIcon({
                html: '<div style="background: ' + color + '; width: ' + size + 'px; height: ' + size + 'px; border-radius: 50%; border: 2px solid rgba(255,255,255,0.8); box-shadow: 0 0 10px ' + color + ';"></div>',
                className: 'fire-marker',
                iconSize: [size, size]
            });
        }

        // Load hotspots from API
        async function loadHotspots() {
            const region = document.getElementById('regionSelect').value;
            const days = document.getElementById('daysSelect').value;
            const coords = regions[region];

            document.getElementById('loading').classList.add('active');

            try {
                const url = '/api/hotspots?west=' + coords.west + '&south=' + coords.south + '&east=' + coords.east + '&north=' + coords.north + '&days=' + days;
                const response = await fetch(url);
                const data = await response.json();

                if (data.error) {
                    alert('Erro: ' + data.error);
                    return;
                }

                // Clear existing markers
                markers.clearLayers();

                // Add new markers
                let highConfCount = 0;
                let totalFRP = 0;
                let maxFRP = 0;

                data.hotspots.forEach(function(h) {
                    const marker = L.marker([h.latitude, h.longitude], {
                        icon: createFireIcon(h.frp)
                    });

                    const popupContent = '<div class="hotspot-popup">' +
                        '<h4>Foco de Incendio</h4>' +
                        '<p><strong>Coordenadas:</strong> ' + h.latitude.toFixed(4) + ', ' + h.longitude.toFixed(4) + '</p>' +
                        '<p><strong>FRP:</strong> ' + h.frp.toFixed(1) + ' MW</p>' +
                        '<p><strong>Brilho:</strong> ' + h.brightness.toFixed(1) + ' K</p>' +
                        '<p><strong>Confianca:</strong> ' + h.confidence + '</p>' +
                        '<p><strong>Satelite:</strong> ' + h.satellite + '</p>' +
                        '<p><strong>Data/Hora:</strong> ' + h.acq_datetime + '</p>' +
                        '<p><strong>Periodo:</strong> ' + (h.daynight === 'D' ? 'Diurno' : 'Noturno') + '</p>' +
                        '</div>';

                    marker.bindPopup(popupContent);
                    markers.addLayer(marker);

                    // Stats
                    if (h.confidence === 'high' || h.confidence === 'h') highConfCount++;
                    totalFRP += h.frp;
                    if (h.frp > maxFRP) maxFRP = h.frp;
                });

                // Update stats
                document.getElementById('totalFires').textContent = data.count;
                document.getElementById('highConf').textContent = highConfCount;
                document.getElementById('avgFRP').textContent = data.count > 0 ? (totalFRP / data.count).toFixed(1) : '0';
                document.getElementById('maxFRP').textContent = maxFRP.toFixed(1);
                document.getElementById('lastUpdate').textContent = new Date().toLocaleString('pt-BR');

                // Fit map to markers
                if (data.count > 0) {
                    map.fitBounds(markers.getBounds(), { padding: [50, 50] });
                } else {
                    map.setView(coords.center, coords.zoom);
                }

            } catch (error) {
                alert('Erro ao carregar dados: ' + error.message);
            } finally {
                document.getElementById('loading').classList.remove('active');
            }
        }

        // Clear map
        function clearMap() {
            markers.clearLayers();
            document.getElementById('totalFires').textContent = '-';
            document.getElementById('highConf').textContent = '-';
            document.getElementById('avgFRP').textContent = '-';
            document.getElementById('maxFRP').textContent = '-';
        }

        // Region change handler
        document.getElementById('regionSelect').addEventListener('change', function() {
            const region = this.value;
            const coords = regions[region];
            map.setView(coords.center, coords.zoom);
        });

        // Load initial data
        loadHotspots();
    </script>
</body>
</html>"""


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

        # Dashboard (main page)
        if path == "/" or path == "" or path == "/dashboard":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(get_dashboard_page().encode("utf-8"))
            return

        # API documentation page
        if path == "/docs":
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
