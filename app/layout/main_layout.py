"""Clean, minimal desktop application layout."""
from dash import dcc # type: ignore
from dash_extensions.enrich import html # type: ignore

from .map_components import create_map_component
from .ui_components import create_control_panel, create_status_panel


def create_layout(config=None):
    """Create a clean, minimal desktop-focused application layout."""
    return html.Div([
        # Clean Header
        html.Header([
            html.H1("Heat Demand Analysis Platform", className="app-title"),
        ], className="app-header"),
        
        # Main desktop workspace - three columns
        html.Main([
            # Left sidebar with controls
            html.Aside([
                create_control_panel(config)
            ], className="sidebar"),
            
            # Central map area
            html.Section([
                create_map_component(config)
            ], className="map-section"),
            
            # Right panel for status and results
            html.Aside([
                create_status_panel()
            ], className="results-panel")
        ], className="main-workspace"),
        
        # Hidden data stores
        html.Div([
            dcc.Store(id="polygon-processed"),
            dcc.Store(id="streets-processed"),
            dcc.Store(id="buildings-processed"),
            dcc.Store(id="filtered-buildings"),
            dcc.Store(id="filter-options-store"),
            dcc.Store(id="network-data"),
            dcc.Store(id="heat-sources-data"),
            # Progress tracking
            dcc.Store(id="progress-store", data={"active": False, "value": 0, "message": "", "error": False}),
            dcc.Interval(
                id="progress-interval",
                interval=500,  # Update every 500ms
                n_intervals=0,
                disabled=False  # Always enabled
            )
        ], style={"display": "none"})
    ], className="app-container")