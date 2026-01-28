"""
FireWatch AI - Vercel Serverless Entry Point
Uses FastAPI with all features: hotspots, crowdsource, alerts, maps
"""

import os
import sys

# Add project root to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.api.main import app

# Vercel serverless handler
handler = app
