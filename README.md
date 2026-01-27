# 🔥 FireWatch AI

**Open-source global wildfire detection platform combining NASA satellite data, crowdsourcing, and AI**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![NASA FIRMS](https://img.shields.io/badge/Data-NASA%20FIRMS-red.svg)](https://firms.modaps.eosdis.nasa.gov/)

---

## 🌍 The Problem

Wildfires are becoming more frequent and devastating due to climate change. Current detection systems have critical limitations:

- **NASA FIRMS**: 3-hour delay for global data (Near Real-Time)
- **Fixed cameras**: $50k+ per unit, limited coverage
- **Manual reports**: Slow, inconsistent, no validation

**Every minute of delay means more hectares burned, more lives at risk.**

## 💡 Our Solution

FireWatch AI is an **open-source platform** that combines multiple data sources to detect wildfires faster and more accurately:

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  NASA Satellite │     │  Crowdsourcing  │     │   Weather Data  │
│   (FIRMS API)   │     │  (User Reports) │     │  (Wind, Humidity)│
└────────┬────────┘     └────────┬────────┘     └────────┬────────┘
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │      AI Engine          │
                    │  • Hotspot clustering   │
                    │  • Cross-validation     │
                    │  • Confidence scoring   │
                    │  • Spread prediction    │
                    └────────────┬────────────┘
                                 │
              ┌──────────────────┼──────────────────┐
              │                  │                  │
     ┌────────▼────────┐ ┌──────▼──────┐ ┌────────▼────────┐
     │   Real-time     │ │   Alerts    │ │   Dashboard     │
     │   Map (Web)     │ │ (Email/SMS) │ │  (Fire Depts)   │
     └─────────────────┘ └─────────────┘ └─────────────────┘
```

## ✨ Key Features

| Feature | Status | Description |
|---------|--------|-------------|
| 🛰️ NASA FIRMS Integration | ✅ Done | Real-time hotspot data from VIIRS/MODIS satellites |
| 🗺️ Interactive Map | 🔄 In Progress | Leaflet-based visualization with heatmaps |
| 📊 REST API | 🔄 In Progress | Public endpoints for developers |
| 👥 Crowdsourcing | 📋 Planned | Citizen reports with geolocation |
| 🤖 AI Confidence Scoring | 📋 Planned | Reduce false positives by 50%+ |
| 📈 Spread Prediction | 📋 Planned | Wind + terrain-based propagation model |
| 🚨 Alert System | 📋 Planned | Email/SMS notifications by region |

## 🚀 Quick Start

### Prerequisites

- Python 3.10+
- NASA FIRMS API Key ([Get one free](https://firms.modaps.eosdis.nasa.gov/api/area/))

### Installation

```bash
# Clone the repository
git clone https://github.com/Cnk1Ra/FireWatch-AI.git
cd FireWatch-AI

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or: venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env and add your FIRMS_API_KEY
```

### Run the API

```bash
uvicorn src.api.main:app --reload
```

Visit `http://localhost:8000/docs` for interactive API documentation.

### Generate a Fire Map

```python
from src.ingestion.firms_client import FIRMSClient
from src.visualization.map_generator import create_fire_map

# Initialize client
client = FIRMSClient(api_key="your_key")

# Get hotspots for Brazil (last 24h)
hotspots = client.get_country_hotspots("BRA", days=1)

# Generate interactive map
fire_map = create_fire_map(hotspots)
fire_map.save("brazil_fires.html")
```

## 📡 Data Sources

| Source | Type | Update Frequency | Cost |
|--------|------|------------------|------|
| [NASA FIRMS](https://firms.modaps.eosdis.nasa.gov/) | Satellite hotspots | 3h (NRT) / 60s (URT*) | Free |
| [Open-Meteo](https://open-meteo.com/) | Weather forecasts | 15 min | Free |
| [OpenWeatherMap](https://openweathermap.org/) | Current conditions | Real-time | Free tier |

*URT (Ultra Real-Time) available only for US/Canada

## 🏗️ Architecture

```
firewatch-ai/
├── src/
│   ├── api/              # FastAPI REST endpoints
│   ├── ingestion/        # NASA FIRMS client
│   ├── ml/               # AI models (Phase 2)
│   ├── visualization/    # Map generation
│   └── alerts/           # Notification system
├── tests/                # Unit & integration tests
├── docs/                 # Documentation
├── data/                 # Local data storage
│   ├── raw/              # Original satellite data
│   └── processed/        # Cleaned & enriched data
├── docker-compose.yml    # Container orchestration
└── requirements.txt      # Python dependencies
```

## 🗺️ Roadmap

### Phase 1: MVP (Current)
- [x] NASA FIRMS API integration
- [x] Basic hotspot visualization
- [ ] REST API endpoints
- [ ] Email alerts by region

### Phase 2: AI & Validation (Q2 2026)
- [ ] Confidence scoring algorithm
- [ ] Weather data integration
- [ ] Basic spread prediction
- [ ] Fire department dashboard

### Phase 3: Scale (Q3 2026)
- [ ] Mobile PWA
- [ ] Crowdsourcing module
- [ ] ML smoke detection
- [ ] Multi-language support

## 🤝 Contributing

We welcome contributions! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

```bash
# Fork the repo, then:
git checkout -b feature/your-feature
# Make changes
git commit -m "Add: your feature description"
git push origin feature/your-feature
# Open a Pull Request
```

## 📄 License

This project is licensed under the MIT License - see [LICENSE](LICENSE) for details.

## 🙏 Acknowledgments

- **NASA FIRMS** for providing free satellite fire data
- **Open-Meteo** for weather API
- The open-source community

## 📬 Contact

- **GitHub Issues**: For bugs and feature requests
- **Discussions**: For questions and ideas

---

<p align="center">
  <b>🔥 Detecting fires faster. Saving lives. 🌍</b>
</p>

<p align="center">
  <i>Built with ❤️ for the planet</i>
</p>
