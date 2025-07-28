"""Clean, minimal UI components."""
from dash import dcc, html # type: ignore


def create_progress_bar():
    """Create an enhanced progress bar with better visual feedback."""
    return html.Div([
        html.Div([
            html.H5("Status", id="progress-title", className="progress-title"),
            html.Div([
                html.Div(
                    id="progress-bar",
                    className="progress-bar-fill"
                )
            ], className="progress-bar-container"),
            html.Div(
                id="progress-details",
                className="progress-details",
                children=["Ready"]
            )
        ], className="progress-content")
    ], id="progress-container", className="progress-widget")


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
        # Add progress bar at the top
        create_progress_bar(),
        
        html.H3("Controls"),
        
        # Measurement tools - Updated with unified classes
        html.Section([
            html.H4("Area Selection"),
            html.Button("Draw Analysis Area", 
                       id="start-measurement-btn", 
                       className="btn btn-primary"),  # Unified button class
            html.Div(id="measurement-status", className="status-display"),  # Unified status class
            # Add data summary under area selection
            html.Div([
                html.H4("Data Summary", style={"margin-top": "1rem"}),
                html.Div(id="data-summary", className="summary-display")  # Unified summary class
            ])
        ], className="control-section"),  # Unified section class
        
        # Heat source placement - Updated with unified classes
        html.Section([
            html.H4("Heat Sources"),
            html.Button("Add Heat Source", 
                       id="add-heat-source-btn", 
                       className="btn btn-secondary"),  # Unified button class
            html.Button("Clear Heat Sources", 
                       id="clear-heat-sources-btn", 
                       className="btn btn-secondary"),  # Unified button class
            html.Div([
                html.Label("Annual Heat Production (kW/year):", className="form-label"),  # Unified label
                dcc.Input(
                    id="heat-source-production-input",
                    type="number",
                    placeholder="e.g., 1000",
                    value=1000,
                    min=0,
                    className="form-input"  # Unified input class
                )
            ], className="form-group"),  # Unified form group
            html.Div(id="heat-source-status", className="status-display"),  # Unified status
            html.Div(id="heat-source-summary", className="summary-display")  # Unified summary
        ], className="control-section"),  # Unified section class
        
        # Network generation - Updated with unified classes
        html.Section([
            html.H4("District Heating Network"),
            html.Button("Generate Network", 
                       id="generate-network-btn", 
                       className="btn btn-primary"),  # Unified button class
            html.Div(id="network-status", className="status-display")  # Unified status
        ], className="control-section"),  # Unified section class
        
        # Graph optimization - Updated with unified classes
        html.Section([
            html.H4("Graph Optimization"),
            html.Button("Optimize Network", 
                       id="optimize-network-btn", 
                       className="btn btn-primary"),  # Unified button class
            html.Div(id="network-optimization-status", className="status-display"),  # Unified status
            
            html.Div([
                html.Label("Max Building Connection Distance (m):", className="form-label"),  # Unified label
                dcc.Input(
                    id="max-building-connection-input",
                    type="number",
                    placeholder="e.g., 100",
                    value=config.graph_filters.get("max_building_connection_distance", 100.0) if config else 100.0,
                    min=0,
                    className="form-input"  # Unified input class
                )
            ], className="form-group"),  # Unified form group
            
            html.Div([
                html.Label("Network Optimization:", className="form-label"),  # Unified label
                dcc.Dropdown(
                    id="pruning-algorithm-dropdown",
                    options=[
                        {"label": "None", "value": "none"},
                        {"label": "Minimum Spanning Tree", "value": "minimum_spanning_tree"},
                        {"label": "All Building Connections", "value": "all_building_connections"},
                        {"label": "Steiner Tree", "value": "steiner_tree"}
                    ],
                    value=config.graph_filters.get("default_pruning_algorithm", "none") if config else "none",
                    multi=False,  # Ensure single selection only
                    className="form-dropdown"  # Unified dropdown class
                )
            ], className="form-group")  # Unified form group
        ], className="control-section"),  # Unified section class
        
        # Building & Heat Demand Filters - Combined section with unified classes
        html.Section([
            html.H4("Building & Heat Demand Filters"),
            
            html.Button("Apply Filters", 
                       id="apply-filters-btn", 
                       className="btn btn-primary"),  # Unified button class
            html.Div(id="filter-status", className="status-display"),  # Unified status
            
            # Heat Demand Filters Subsection
            html.Div([
                html.H5("Heat Demand", style={"margin": "1rem 0 0.5rem 0", "fontSize": "0.9rem", "fontWeight": "600", "color": "#2d3748"}),
                
                html.Div([
                    dcc.Checklist(
                        id="exclude-zero-heat-demand",
                        options=[{"label": "Exclude zero heat demand", "value": "exclude"}],
                        value=["exclude"] if default_exclude_zero else [],
                        className="modern-checkbox"  # Unified checkbox class
                    )
                ], className="form-group"),  # Unified form group
                
                html.Div([
                    html.Div([
                        html.Label("Min Heat Demand:", className="form-label"),  # Unified label
                        dcc.Input(
                            id="min-heat-demand",
                            type="number",
                            placeholder="Min kWh/year",
                            value=default_min_heat,
                            className="form-input"  # Unified input class
                        )
                    ], style={"width": "48%", "display": "inline-block"}),
                    
                    html.Div([
                        html.Label("Max Heat Demand:", className="form-label"),  # Unified label
                        dcc.Input(
                            id="max-heat-demand",
                            type="number",
                            placeholder="Max kWh/year",
                            value=default_max_heat,
                            className="form-input"  # Unified input class
                        )
                    ], style={"width": "48%", "display": "inline-block", "marginLeft": "4%"})
                ], className="form-group"),  # Unified form group
            ]),
            
            # Building Attribute Filters Subsection
            html.Div([
                html.H5("Building Attributes", style={"margin": "1.5rem 0 0.5rem 0", "fontSize": "0.9rem", "fontWeight": "600", "color": "#2d3748"}),
                
                html.Div([
                    html.Label("Street:", className="form-label"),  # Unified label
                    dcc.Dropdown(
                        id="street-filter",
                        placeholder="Select streets...",
                        multi=True,
                        className="form-dropdown"  # Unified dropdown class
                    )
                ], className="form-group"),  # Unified form group
                
                html.Div([
                    html.Label("Postcode:", className="form-label"),  # Unified label
                    dcc.Dropdown(
                        id="postcode-filter",
                        placeholder="Select postcodes...",
                        multi=True,
                        className="form-dropdown"  # Unified dropdown class
                    )
                ], className="form-group"),  # Unified form group
                
                html.Div([
                    html.Label("City:", className="form-label"),  # Unified label
                    dcc.Dropdown(
                        id="city-filter",
                        placeholder="Select cities...",
                        multi=True,
                        className="form-dropdown"  # Unified dropdown class
                    )
                ], className="form-group"),  # Unified form group
                
                html.Div([
                    html.Label("Building Use:", className="form-label"),  # Unified label
                    dcc.Dropdown(
                        id="building-use-filter",
                        placeholder="Select building uses...",
                        multi=True,
                        className="form-dropdown"  # Unified dropdown class
                    )
                ], className="form-group"),  # Unified form group
            ])
        ], className="control-section"),  # Unified section class

    ], className="control-panel")


def create_status_panel():
    """Create a clean status panel."""
    return html.Div([
        html.H3("Status"),
        
        # Status panel is now just for future status content
        # Progress bar and data summary moved to left sidebar
        
    ], className="status-panel")