"""Clean, minimal UI components."""
from dash import dcc, html # type: ignore


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
        
        # Network generation
        html.Section([
            html.H4("District Heating Network"),
            html.Button("Generate Network", id="generate-network-btn", className="btn-primary"),
            html.Div(id="network-status")
        ], className="control-group"),
        
        # Graph optimization
        html.Section([
            html.H4("Graph Optimization"),
            html.Button("Optimize Network", id="optimize-network-btn", className="btn-primary"),
            html.Div(id="network-optimization-status"),
            
            html.Div([
                html.Label("Max Building Connection Distance (m):"),
                dcc.Input(
                    id="max-building-connection-input",
                    type="number",
                    placeholder="e.g., 100",
                    value=config.graph_filters.get("max_building_connection_distance", 100.0) if config else 100.0,
                    min=0,
                    className="input-small"
                )
            ], className="input-group"),
            
            html.Div([
                html.Label("Network Optimization:"),
                dcc.Dropdown(
                    id="pruning-algorithm-dropdown",
                    options=[
                        {"label": "None", "value": "none"},
                        {"label": "Minimum Spanning Tree", "value": "minimum_spanning_tree"},
                        {"label": "All Building Connections", "value": "all_building_connections"},
                        {"label": "Steiner Tree", "value": "steiner_tree"}
                    ],
                    value=config.graph_filters.get("default_pruning_algorithm", "none") if config else "none",
                    className="dropdown-small"
                )
            ], className="input-group")
        ], className="control-group"),
        
        # Heat demand filters
        html.Section([
            html.H4("Heat Demand"),
            
            html.Button("Apply Filters", id="apply-filters-btn", className="btn-primary"),
            html.Div(id="filter-status"),
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
        ], className="control-group"),

    ], className="control-panel")


def create_status_panel():
    """Create a clean status panel."""
    return html.Div([
        html.H3("Status"),
        
        html.Section([
            html.H4("Data Summary"),
            html.Div(id="data-summary", className="summary-area")
        ]),
    ], className="status-panel")