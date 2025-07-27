"""Clean, minimal UI components."""
from dash import dcc, html # type: ignore


def create_progress_bar():
    """Create a progress bar component for long-running operations."""
    return html.Div(
        id="progress-container",
        style={"display": "block"},  # Always visible
        children=[
            html.H5("Status", id="progress-title"),
            html.Div(
                style={
                    "width": "100%", 
                    "height": "20px", 
                    "background-color": "#e9ecef", 
                    "border-radius": "4px",
                    "margin": "10px 0"
                },
                children=[
                    html.Div(
                        id="progress-bar",
                        style={
                            "width": "0%",
                            "height": "100%",
                            "background-color": "#007bff",
                            "border-radius": "4px",
                            "transition": "width 0.3s ease"
                        }
                    )
                ]
            ),
            html.Div(
                id="progress-details",
                style={"font-size": "0.9em", "color": "#666"},
                children=["Ready"]
            )
        ],
        className="mb-3 p-3 border rounded"
    )


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
        
        # Heat source placement (UI only)
        html.Section([
            html.H4("Heat Sources"),
            html.Button("Add Heat Source", id="add-heat-source-btn", className="btn-secondary"),
            html.Button("Clear Heat Sources", id="clear-heat-sources-btn", className="btn-secondary"),
            html.Div([
                html.Label("Annual Heat Production (kW/year):"),
                dcc.Input(
                    id="heat-source-production-input",
                    type="number",
                    placeholder="e.g., 1000",
                    value=1000,
                    min=0,
                    className="input-small"
                )
            ], className="input-group"),
            html.Div(id="heat-source-status"),
            html.Div(id="heat-source-summary")
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
        
        # Add progress bar before existing status
        create_progress_bar(),
        
        html.Section([
            html.H4("Data Summary"),
            html.Div(id="data-summary", className="summary-area")
        ]),
    ], className="status-panel")