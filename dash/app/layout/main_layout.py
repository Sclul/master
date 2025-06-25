"""Main application layout - simplified to essential features only."""
from dash import dcc
from dash_extensions.enrich import html # type: ignore

from .map_components import create_map_component
from .ui_components import create_control_panel, create_status_panel


def create_layout(config=None):
    """Create the main application layout with essential features only."""
    return html.Div([
        # Header
        html.Header([
            html.H1("OSM Heat Demand Analysis", className="app-title")
        ], className="app-header"),
        
        # Main content
        html.Main([
            # Control panel - simplified
            html.Aside([
                create_control_panel(config)
            ], className="control-panel"),
            
            # Map and status panel
            html.Section([
                create_map_component(config),
                create_status_panel()
            ], className="map-panel")
        ], className="main-content"),
        
        # Hidden data stores - only what's used
        html.Div([
            dcc.Store(id="geojson-saved"),
            dcc.Store(id="filtered-buildings"),
        ], id="data-stores", style={"display": "none"})
    ], className="app-container")