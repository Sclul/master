"""Clean, minimal UI components."""
from dash import dcc, html # type: ignore


def create_collapsible_section(section_id, step_number, title, content, optional=False, initial_collapsed=True):
    """Create a collapsible control section with header and body.
    
    Args:
        section_id: Unique ID for the section
        step_number: Step number (1-6)
        title: Section title text
        content: Section body content (list of components)
        optional: Whether this is an optional step
        initial_collapsed: Whether section starts collapsed
    """
    header_class = "section-header collapsed" if initial_collapsed else "section-header"
    body_class = "section-body collapsed" if initial_collapsed else "section-body"
    
    optional_label = html.Span("(optional)", className="step-optional") if optional else None
    
    return html.Section(
        id=section_id,
        className="control-section",
        children=[
            # Clickable header
            html.Div(
                id=f"{section_id}-header",
                className=header_class,
                children=[
                    html.Div(
                        className="section-header-content",
                        children=[
                            html.Span(str(step_number), className="step-number", id=f"step-{step_number}-badge"),
                            html.Span(title, className="step-text"),
                            optional_label
                        ]
                    ),
                    html.Span("▼", className="collapse-icon")
                ]
            ),
            # Collapsible body
            html.Div(
                id=f"{section_id}-body",
                className=body_class,
                children=content
            )
        ]
    )


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
        
        # Store for tracking workflow expansion state
        dcc.Store(id='workflow-expansion-store', data={'expanded_section': 'section-area-selection'}),
        
        html.H3("Controls"),
        
        # STEP 1: Area Selection (initially expanded)
        create_collapsible_section(
            section_id='section-area-selection',
            step_number=1,
            title='Area Selection',
            initial_collapsed=False,
            content=[
                html.Button("Draw Analysis Area", 
                           id="start-measurement-btn", 
                           className="btn btn-primary"),
                html.Div([
                    html.Label("Operating Hours (h/year):", className="form-label"),
                    dcc.Input(
                        id="operating-hours-input",
                        type="number",
                        placeholder="e.g., 2000",
                        value=config.pandapipes.get("assume_continuous_operation_h_per_year", 2000) if config else 2000,
                        min=1,
                        max=8760,
                        step=1,
                        className="form-input"
                    )
                ], className="form-group"),
                html.Div(id="measurement-status", className="status-display"),
                html.Div([
                    html.H4("Data Summary", style={"margin-top": "1rem"}),
                    html.Div(id="data-summary", className="summary-display")
                ])
            ]
        ),
        
        # STEP 2: Heat Sources (initially collapsed)
        create_collapsible_section(
            section_id='section-heat-sources',
            step_number=2,
            title='Heat Sources',
            initial_collapsed=True,
            content=[
                html.Button("Add Heat Source", 
                           id="add-heat-source-btn", 
                           className="btn btn-secondary",
                           disabled=True),
                html.Button("Clear Heat Sources", 
                           id="clear-heat-sources-btn", 
                           className="btn btn-secondary",
                           disabled=True),
                html.Div([
                    html.Label("Mass Flow Calculation Mode:", className="form-label"),
                    dcc.RadioItems(
                        id="mass-flow-mode",
                        options=[
                            {'label': ' Demand-matching (auto-calculated from building loads)', 'value': 'demand'},
                            {'label': ' Manual (based on heat source production)', 'value': 'manual'}
                        ],
                        value='demand',
                        className="form-radio",
                        style={"marginBottom": "10px"}
                    )
                ], className="form-group"),
                html.Div([
                    html.Label("Annual Heat Production (GW/year):", className="form-label"),
                    dcc.Input(
                        id="heat-source-production-input",
                        type="number",
                        placeholder="e.g., 1",
                        value=1,
                        min=0,
                        step=0.001,
                        className="form-input"
                    ),
                    html.Div(id="mass-flow-mode-indicator", style={"marginTop": "5px"})
                ], className="form-group"),
                html.Div(id="heat-source-status", className="status-display"),
                html.Div(id="heat-source-summary", className="summary-display")
            ]
        ),
        
        # STEP 3: Building Filters (optional, initially collapsed)
        create_collapsible_section(
            section_id='section-building-filters',
            step_number=3,
            title='Building Filters',
            optional=True,
            initial_collapsed=True,
            content=[
                html.Button("Apply Filters", 
                           id="apply-filters-btn", 
                           className="btn btn-primary",
                           disabled=True),
                html.Div(id="filter-status", className="status-display"),
                
                # Heat Demand Filters
                html.Div([
                    html.H5("Heat Demand", style={"margin": "1rem 0 0.5rem 0", "fontSize": "0.9rem", "fontWeight": "600", "color": "#2d3748"}),
                    html.Div([
                        dcc.Checklist(
                            id="exclude-zero-heat-demand",
                            options=[{"label": "Exclude zero heat demand", "value": "exclude"}],
                            value=["exclude"] if default_exclude_zero else [],
                            className="modern-checkbox"
                        )
                    ], className="form-group"),
                    html.Div([
                        html.Div([
                            html.Label("Min Heat Demand:", className="form-label"),
                            dcc.Input(
                                id="min-heat-demand",
                                type="number",
                                placeholder="Min kWh/year",
                                value=default_min_heat,
                                className="form-input"
                            )
                        ], style={"width": "48%", "display": "inline-block"}),
                        html.Div([
                            html.Label("Max Heat Demand:", className="form-label"),
                            dcc.Input(
                                id="max-heat-demand",
                                type="number",
                                placeholder="Max kWh/year",
                                value=default_max_heat,
                                className="form-input"
                            )
                        ], style={"width": "48%", "display": "inline-block", "marginLeft": "4%"})
                    ], className="form-group"),
                ]),
                
                # Building Attribute Filters
                html.Div([
                    html.H5("Building Attributes", style={"margin": "1.5rem 0 0.5rem 0", "fontSize": "0.9rem", "fontWeight": "600", "color": "#2d3748"}),
                    html.Div([
                        html.Label("Street:", className="form-label"),
                        dcc.Dropdown(
                            id="street-filter",
                            placeholder="Select streets...",
                            multi=True,
                            className="form-dropdown"
                        )
                    ], className="form-group"),
                    html.Div([
                        html.Label("Postcode:", className="form-label"),
                        dcc.Dropdown(
                            id="postcode-filter",
                            placeholder="Select postcodes...",
                            multi=True,
                            className="form-dropdown"
                        )
                    ], className="form-group"),
                    html.Div([
                        html.Label("City:", className="form-label"),
                        dcc.Dropdown(
                            id="city-filter",
                            placeholder="Select cities...",
                            multi=True,
                            className="form-dropdown"
                        )
                    ], className="form-group"),
                    html.Div([
                        html.Label("Building Use:", className="form-label"),
                        dcc.Dropdown(
                            id="building-use-filter",
                            placeholder="Select building uses...",
                            multi=True,
                            className="form-dropdown"
                        )
                    ], className="form-group"),
                ])
            ]
        ),
        
        # STEP 4: Network Generation (initially collapsed)
        create_collapsible_section(
            section_id='section-network-generation',
            step_number=4,
            title='District Heating Network',
            initial_collapsed=True,
            content=[
                html.Button("Generate Network", 
                           id="generate-network-btn", 
                           className="btn btn-primary",
                           disabled=True),
                html.Div(id="network-status", className="status-display")
            ]
        ),
        
        # STEP 5: Graph Optimization (optional, initially collapsed)
        create_collapsible_section(
            section_id='section-graph-optimization',
            step_number=5,
            title='Graph Optimization',
            optional=True,
            initial_collapsed=True,
            content=[
                html.Button("Optimize Network", 
                           id="optimize-network-btn", 
                           className="btn btn-primary",
                           disabled=True),
                html.Div(id="network-optimization-status", className="status-display"),
                html.Div([
                    html.Label("Max Building Connection Distance (m):", className="form-label"),
                    dcc.Input(
                        id="max-building-connection-input",
                        type="number",
                        placeholder="e.g., 100",
                        value=config.graph_filters.get("max_building_connection_distance", 100.0) if config else 100.0,
                        min=0,
                        className="form-input"
                    )
                ], className="form-group"),
                html.Div([
                    html.Label("Network Optimization:", className="form-label"),
                    dcc.Dropdown(
                        id="pruning-algorithm-dropdown",
                        options=[
                            {"label": "None", "value": "none"},
                            {"label": "Minimum Spanning Tree", "value": "minimum_spanning_tree"},
                            {"label": "All Building Connections", "value": "all_building_connections"},
                            {"label": "Steiner Tree", "value": "steiner_tree"}
                        ],
                        value=config.graph_filters.get("default_pruning_algorithm", "none") if config else "none",
                        multi=False,
                        className="form-dropdown"
                    )
                ], className="form-group")
            ]
        ),

    ], className="control-panel")


def create_status_panel():
    """Create a clean status panel."""
    return html.Div([
        # STEP 6: Hydraulic Simulation
        html.H3([
            html.Span("6", className="step-number", id="step-6-badge", style={"marginRight": "0.5rem"}),
            html.Span("Pandapipes Simulation")
        ]),

        # Minimal controls for initialization only
        html.Div([
            html.Button("Initialize Net", id="sim-init-btn", className="btn btn-secondary", disabled=True),
            html.Button("Run Pipeflow", id="sim-run-btn", className="btn btn-primary", disabled=True)
        ], className="button-group"),

        # Status + summary placeholders
        html.Div(id="sim-status", className="status-display"),
        html.Div(id="sim-summary", className="status-display"),
    ], id="section-simulation", className="status-panel locked")  # Initially locked