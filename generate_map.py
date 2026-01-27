#!/usr/bin/env python3
"""
FireWatch AI - Generate Interactive Fire Map
Fetches real-time fire data from NASA FIRMS and creates an interactive map.
"""
import os
import sys
from datetime import datetime

# Add src to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
from src.ingestion.firms_client import FIRMSClient, DataSource
from src.visualization.map_generator import create_fire_map

# Load environment variables
load_dotenv()

def main():
    api_key = os.getenv("FIRMS_API_KEY")

    if not api_key:
        print("ERROR: FIRMS_API_KEY not found in .env file")
        sys.exit(1)

    print("=" * 60)
    print("FireWatch AI - Generating Fire Map")
    print("=" * 60)

    # Initialize client
    client = FIRMSClient(api_key=api_key)

    print("\nFetching fire data from NASA FIRMS...")
    print("Region: Brazil (bounding box)")
    print("Source: VIIRS NOAA-20 (Near Real-Time)")
    print("Period: Last 24 hours")

    # Fetch Brazil hotspots using bounding box (more reliable)
    # Brazil bounding box: west=-73, south=-33, east=-35, north=5
    hotspots = client.get_area_hotspots(
        west=-73,
        south=-33,
        east=-35,
        north=5,
        days=1,
        source=DataSource.VIIRS_NOAA20_NRT
    )

    print(f"\nTotal hotspots found: {len(hotspots)}")

    if not hotspots:
        print("No fire hotspots detected in Brazil today.")
        return

    # Statistics
    high_conf = sum(1 for h in hotspots if h.confidence in ['h', 'high'])
    nominal_conf = sum(1 for h in hotspots if h.confidence in ['n', 'nominal'])
    low_conf = sum(1 for h in hotspots if h.confidence in ['l', 'low'])
    avg_frp = sum(h.frp for h in hotspots if h.frp) / len([h for h in hotspots if h.frp]) if hotspots else 0
    max_frp = max((h.frp for h in hotspots if h.frp), default=0)

    print(f"\nStatistics:")
    print(f"  - High confidence:    {high_conf}")
    print(f"  - Nominal confidence: {nominal_conf}")
    print(f"  - Low confidence:     {low_conf}")
    print(f"  - Average FRP:        {avg_frp:.2f} MW")
    print(f"  - Max FRP:            {max_frp:.2f} MW")

    # Generate map
    print("\nGenerating interactive map...")

    fire_map = create_fire_map(
        hotspots=hotspots,
        center=(-14.235, -51.925),  # Brazil center
        zoom=4,
        title=f"FireWatch AI - Brazil Active Fires ({datetime.now().strftime('%Y-%m-%d %H:%M')})",
        show_heatmap=True,
        show_markers=True,
        cluster_markers=True
    )

    # Save map
    output_path = os.path.join(os.path.dirname(__file__), "brazil_fire_map.html")
    fire_map.save(output_path)

    print(f"\nMap saved to: {output_path}")
    print("\nOpen the file in your browser to view the interactive map!")
    print("=" * 60)

if __name__ == "__main__":
    main()
