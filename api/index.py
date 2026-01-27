"""
FireWatch AI - Vercel Serverless Entry Point
"""

import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.api.main import app

# Vercel expects the app to be named 'app' or 'handler'
handler = app
