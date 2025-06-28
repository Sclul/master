"""Clean, minimal UI components."""
from dash import dcc, html


def create_control_panel(config=None):
    """Create a clean control panel with essential controls."""
    # Get default values from config
    default_exclude_zero = True
    default_min_heat = None
    default_max_heat = None
    
    if config:
        building_filters = config.building_filters
        default_exclude_zero = building_filters.get("exclude_zero_heat_demand", True)
        default_min_heat = building_filters.get("min_heat_demand")
        default_max_heat = building_filters.get("max_heat_demand")
    
    return html.Div([
        html.H3("Controls"),
        
        # Measurement tools
        html.Section([
            html.H4("Area Selection"),
            html.Button("Draw Analysis Area", id="start-measurement-btn", className="btn-primary"),
            html.Div(id="measurement-status")
        ], className="control-group"),
        
        # Apply filters button
        html.Button("Apply Filters", id="apply-filters-btn", className="btn-primary"),
        html.Div(id="filter-status"),
        
        # Heat demand filters
        html.Section([
            html.H4("Heat Demand"),
            
            html.Div([
                dcc.Checklist(
                    id="exclude-zero-heat-demand",
                    options=[{"label": "Exclude zero heat demand", "value": "exclude"}],
                    value=["exclude"] if default_exclude_zero else []
                )
            ]),
            
            html.Div([
                html.Label("Min:"),
                dcc.Input(
                    id="min-heat-demand",
                    type="number",
                    placeholder="Min",
                    value=default_min_heat,
                    className="input-small"
                )
            ], className="input-group"),
            
            html.Div([
                html.Label("Max:"),
                dcc.Input(
                    id="max-heat-demand",
                    type="number",
                    placeholder="Max",
                    value=default_max_heat,
                    className="input-small"
                )
            ], className="input-group"),
        ], className="control-group"),
        
        # Building filters
        html.Section([
            html.H4("Building Filters"),
            
            html.Div([
                html.Label("Street:"),
                dcc.Dropdown(
                    id="street-filter",
                    placeholder="Select...",
                    multi=True
                )
            ], className="filter-item"),
            
            html.Div([
                html.Label("Postcode:"),
                dcc.Dropdown(
                    id="postcode-filter",
                    placeholder="Select...",
                    multi=True
                )
            ], className="filter-item"),
            
            html.Div([
                html.Label("City:"),
                dcc.Dropdown(
                    id="city-filter",
                    placeholder="Select...",
                    multi=True
                )
            ], className="filter-item"),
            
            html.Div([
                html.Label("Building Use:"),
                dcc.Dropdown(
                    id="building-use-filter",
                    placeholder="Select...",
                    multi=True
                )
            ], className="filter-item"),
        ], className="control-group")
    ], className="control-panel")


def create_status_panel():
    """Create a clean status panel."""
    return html.Div([
        html.H3("Status"),
        
        html.Section([
            html.H4("Processing"),
            html.Div(id="log", className="log-area")
        ]),
        
        html.Section([
            html.H4("Data Summary"),
            html.Div(id="data-summary", className="summary-area")
        ]),
    ], className="status-panel")