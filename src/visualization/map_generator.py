"""
Map Visualization Module for FireWatch AI

Generates interactive maps using Folium to display fire hotspots
with various visualization options including markers, heatmaps, and clusters.
"""

import logging
from typing import Optional

import folium
from folium.plugins import HeatMap, MarkerCluster

logger = logging.getLogger(__name__)


def get_confidence_color(confidence: str) -> str:
    """Get marker color based on confidence level."""
    colors = {
        "h": "red",      # High confidence
        "high": "red",
        "n": "orange",   # Nominal confidence
        "nominal": "orange",
        "l": "yellow",   # Low confidence
        "low": "yellow",
    }
    return colors.get(confidence, "gray")


def get_frp_radius(frp: float) -> int:
    """Calculate marker radius based on Fire Radiative Power."""
    if frp < 5:
        return 5
    elif frp < 20:
        return 8
    elif frp < 50:
        return 12
    else:
        return 16


def create_fire_map(
    hotspots: list,
    center: Optional[tuple[float, float]] = None,
    zoom: int = 5,
    title: str = "FireWatch AI - Active Fires",
    show_heatmap: bool = True,
    show_markers: bool = True,
    cluster_markers: bool = True,
) -> folium.Map:
    """
    Create an interactive map with fire hotspots.
    
    Args:
        hotspots: List of FireHotspot objects
        center: Map center (lat, lon). Auto-calculated if None.
        zoom: Initial zoom level (1-18)
        title: Map title
        show_heatmap: Include heatmap layer
        show_markers: Include marker layer
        cluster_markers: Cluster markers when zoomed out
        
    Returns:
        Folium Map object
    """
    if not hotspots:
        logger.warning("No hotspots provided, creating empty map")
        center = center or (0, 0)
        return folium.Map(location=center, zoom_start=2)
    
    # Calculate center from hotspots if not provided
    if center is None:
        lats = [h.latitude for h in hotspots]
        lons = [h.longitude for h in hotspots]
        center = (sum(lats) / len(lats), sum(lons) / len(lons))
    
    # Create base map
    fire_map = folium.Map(
        location=center,
        zoom_start=zoom,
        tiles=None,
    )
    
    # Add tile layers
    folium.TileLayer(
        tiles="CartoDB dark_matter",
        name="Dark",
        attr="CartoDB",
    ).add_to(fire_map)
    
    folium.TileLayer(
        tiles="OpenStreetMap",
        name="Street",
    ).add_to(fire_map)
    
    folium.TileLayer(
        tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        name="Satellite",
        attr="Esri",
    ).add_to(fire_map)
    
    # Add heatmap layer
    if show_heatmap:
        heat_data = [[h.latitude, h.longitude, h.frp] for h in hotspots]
        heatmap = HeatMap(
            heat_data,
            name="Heatmap",
            radius=15,
            blur=10,
            max_zoom=13,
            gradient={0.2: "blue", 0.4: "lime", 0.6: "yellow", 0.8: "orange", 1: "red"},
        )
        heatmap.add_to(fire_map)
    
    # Add markers
    if show_markers:
        if cluster_markers:
            marker_group = MarkerCluster(name="Fire Hotspots")
        else:
            marker_group = folium.FeatureGroup(name="Fire Hotspots")
        
        for hotspot in hotspots:
            color = get_confidence_color(hotspot.confidence)
            radius = get_frp_radius(hotspot.frp)
            
            popup_html = f"""
            <div style="font-family: Arial; min-width: 200px;">
                <h4 style="margin: 0; color: {color};">🔥 Fire Hotspot</h4>
                <hr style="margin: 5px 0;">
                <b>Location:</b> {hotspot.latitude:.4f}, {hotspot.longitude:.4f}<br>
                <b>FRP:</b> {hotspot.frp:.1f} MW<br>
                <b>Brightness:</b> {hotspot.brightness:.1f} K<br>
                <b>Confidence:</b> {hotspot.confidence_level}<br>
                <b>Time:</b> {hotspot.datetime.strftime("%Y-%m-%d %H:%M")} UTC<br>
                <b>Satellite:</b> {hotspot.satellite} ({hotspot.instrument})<br>
                <b>Day/Night:</b> {"Day" if hotspot.is_daytime else "Night"}
            </div>
            """
            
            folium.CircleMarker(
                location=[hotspot.latitude, hotspot.longitude],
                radius=radius,
                popup=folium.Popup(popup_html, max_width=300),
                color=color,
                fill=True,
                fill_color=color,
                fill_opacity=0.7,
                weight=2,
            ).add_to(marker_group)
        
        marker_group.add_to(fire_map)
    
    # Add layer control
    folium.LayerControl(position="topright").add_to(fire_map)
    
    # Add title
    title_html = f'''
    <div style="position: fixed; 
                top: 10px; left: 50px; 
                background-color: rgba(0,0,0,0.8); 
                padding: 10px 20px; 
                border-radius: 5px;
                z-index: 9999;
                font-family: Arial;">
        <h3 style="margin: 0; color: white;">{title}</h3>
        <p style="margin: 5px 0 0 0; color: #ccc; font-size: 12px;">
            {len(hotspots)} hotspots detected
        </p>
    </div>
    '''
    fire_map.get_root().html.add_child(folium.Element(title_html))
    
    # Add legend
    legend_html = '''
    <div style="position: fixed; 
                bottom: 30px; right: 30px; 
                background-color: rgba(0,0,0,0.8); 
                padding: 10px; 
                border-radius: 5px;
                z-index: 9999;
                font-family: Arial; 
                font-size: 12px;
                color: white;">
        <b>Confidence Level</b><br>
        <span style="color: red;">●</span> High<br>
        <span style="color: orange;">●</span> Nominal<br>
        <span style="color: yellow;">●</span> Low<br>
        <hr style="margin: 5px 0; border-color: #555;">
        <b>Marker Size</b> = FRP (MW)
    </div>
    '''
    fire_map.get_root().html.add_child(folium.Element(legend_html))
    
    logger.info(f"Created map with {len(hotspots)} hotspots")
    return fire_map


def generate_brazil_fire_map(
    hotspots: list,
    output_path: str = "brazil_fires.html",
) -> str:
    """
    Generate and save a fire map for Brazil.
    
    Args:
        hotspots: List of FireHotspot objects
        output_path: Path to save HTML file
        
    Returns:
        Path to saved file
    """
    # Brazil center
    brazil_center = (-14.235, -51.925)
    
    fire_map = create_fire_map(
        hotspots=hotspots,
        center=brazil_center,
        zoom=4,
        title="FireWatch AI - Brazil Active Fires",
    )
    
    fire_map.save(output_path)
    logger.info(f"Map saved to {output_path}")
    
    return output_path
