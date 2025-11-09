"""Clean, minimal UI components."""
from dash import dcc, html # type: ignore
from typing import Optional, Any, Dict, List, Union


def create_metric_card(
    label: str,
    value: Any,
    unit: str = "",
    icon: Optional[str] = None,
    card_class: str = "metric-card"
) -> html.Div:
    """Create a structured metric card with consistent styling.
    
    Args:
        label: Metric label text
        value: Metric value (number, string, or formatted component)
        unit: Optional unit suffix (e.g., "kW", "nodes")
        icon: Optional emoji/unicode icon
        card_class: CSS class for styling variants
    
    Returns:
        Styled metric card component
    """
    icon_element = html.Span(icon, className="metric-icon") if icon else None
    
    # Format value display
    if isinstance(value, (int, float)):
        if isinstance(value, float) and value >= 1000:
            value_str = f"{value:,.1f}"
        elif isinstance(value, float):
            value_str = f"{value:.2f}"
        else:
            value_str = f"{value:,}"
    else:
        value_str = str(value)
    
    # Add unit if provided
    value_display = f"{value_str} {unit}" if unit else value_str
    
    return html.Div(
        className=card_class,
        children=[
            html.Div(className="metric-content", children=[
                icon_element,
                html.Div(className="metric-text", children=[
                    html.Div(label, className="metric-label"),
                    html.Div(value_display, className="metric-value")
                ])
            ])
        ]
    )


def create_reduction_metric(
    label: str,
    before: Union[int, float],
    after: Union[int, float],
    unit: str = "",
    icon: Optional[str] = None
) -> html.Div:
    """Create a metric card showing before → after reduction with percentage.
    
    Args:
        label: Metric label text
        before: Original value
        after: Reduced value
        unit: Optional unit suffix
        icon: Optional emoji/unicode icon
    
    Returns:
        Styled reduction metric card
    """
    reduction_pct = ((before - after) / before * 100) if before > 0 else 0
    
    icon_element = html.Span(icon, className="metric-icon") if icon else None
    
    # Format numbers
    before_str = f"{before:,}" if isinstance(before, int) else f"{before:,.1f}"
    after_str = f"{after:,}" if isinstance(after, int) else f"{after:,.1f}"
    
    return html.Div(
        className="metric-card metric-card-reduction",
        children=[
            html.Div(className="metric-content", children=[
                icon_element,
                html.Div(className="metric-text", children=[
                    html.Div(label, className="metric-label"),
                    html.Div(
                        className="metric-value-reduction",
                        children=[
                            html.Span(f"{before_str}", className="value-before"),
                            html.Span(" → ", className="arrow"),
                            html.Span(f"{after_str}", className="value-after"),
                            html.Span(f" {unit}" if unit else "", className="unit")
                        ]
                    ),
                    html.Div(f"⬇ {reduction_pct:.1f}% reduction", className="reduction-badge")
                ])
            ])
        ]
    )


def create_range_metric(
    label: str,
    min_val: Union[int, float],
    max_val: Union[int, float],
    avg_val: Optional[Union[int, float]] = None,
    unit: str = "",
    icon: Optional[str] = None
) -> html.Div:
    """Create a metric card showing min/max/avg range.
    
    Args:
        label: Metric label text
        min_val: Minimum value
        max_val: Maximum value
        avg_val: Optional average value
        unit: Unit suffix
        icon: Optional emoji/unicode icon
    
    Returns:
        Styled range metric card
    """
    icon_element = html.Span(icon, className="metric-icon") if icon else None
    
    # Format values
    def fmt(val):
        if isinstance(val, int):
            return f"{val:,}"
        return f"{val:.2f}"
    
    range_parts = [
        html.Div([
            html.Span("Min: ", className="range-label"),
            html.Span(f"{fmt(min_val)} {unit}", className="range-value")
        ], className="range-item"),
        html.Div([
            html.Span("Max: ", className="range-label"),
            html.Span(f"{fmt(max_val)} {unit}", className="range-value")
        ], className="range-item")
    ]
    
    if avg_val is not None:
        range_parts.append(
            html.Div([
                html.Span("Avg: ", className="range-label"),
                html.Span(f"{fmt(avg_val)} {unit}", className="range-value")
            ], className="range-item")
        )
    
    return html.Div(
        className="metric-card metric-card-range",
        children=[
            html.Div(className="metric-content", children=[
                icon_element,
                html.Div(className="metric-text", children=[
                    html.Div(label, className="metric-label"),
                    html.Div(range_parts, className="metric-range")
                ])
            ])
        ]
    )


def create_status_metric(
    label: str,
    status: bool,
    success_text: str = "Yes",
    failure_text: str = "No",
    icon: Optional[str] = None
) -> html.Div:
    """Create a metric card showing binary status (success/failure).
    
    Args:
        label: Metric label text
        status: True for success, False for failure
        success_text: Text to show on success
        failure_text: Text to show on failure
        icon: Optional emoji/unicode icon
    
    Returns:
        Styled status metric card
    """
    status_class = "metric-card-success" if status else "metric-card-error"
    status_text = success_text if status else failure_text
    default_icon = "✓" if status else "✗"
    display_icon = icon if icon else default_icon
    
    return html.Div(
        className=f"metric-card {status_class}",
        children=[
            html.Div(className="metric-content", children=[
                html.Span(display_icon, className="metric-icon"),
                html.Div(className="metric-text", children=[
                    html.Div(label, className="metric-label"),
                    html.Div(status_text, className="metric-value")
                ])
            ])
        ]
    )


def create_metric_group(
    title: str,
    metrics: List[html.Div],
    group_class: str = "metric-group"
) -> html.Div:
    """Group multiple metric cards under a common title.
    
    Args:
        title: Group title
        metrics: List of metric card components
        group_class: CSS class for the group container
    
    Returns:
        Grouped metrics container
    """
    return html.Div(
        className=group_class,
        children=[
            html.H4(title, className="metric-group-title"),
            html.Div(metrics, className="metric-grid")
        ]
    )


def create_progress_modal():
    """Create a bottom sheet modal for long-running operations.
    
    Modal slides up from bottom with no backdrop dimming.
    Shows operation progress with icon, title, progress bar, and details.
    """
    return html.Div(
        id="progress-modal",
        className="progress-modal hidden",
        children=[
            html.Div(
                className="progress-modal-content",
                children=[
                    # Icon on the left (spinner, success checkmark, or error X)
                    html.Div(id="progress-modal-icon", className="progress-modal-icon"),
                    # Content on the right (title, bar, details)
                    html.Div([
                        html.H4(id="progress-modal-title", className="progress-modal-title", children="Ready"),
                        html.Div(
                            className="progress-modal-bar-container",
                            children=[
                                html.Div(id="progress-modal-bar", className="progress-modal-bar-fill", style={"width": "0%"})
                            ]
                        ),
                        html.Div(id="progress-modal-details", className="progress-modal-details", children="")
                    ])
                ]
            )
        ]
    )


def create_action_button(button_id, text, button_class="btn-primary", disabled=False):
    """Create a button with loading state support.
    
    Args:
        button_id: Unique ID for the button
        text: Button label text
        button_class: CSS class (btn-primary, btn-secondary, etc.)
        disabled: Initial disabled state
    
    Returns:
        Button component with spinner support
    """
    return html.Button(
        id=button_id,
        className=f"btn {button_class}",
        disabled=disabled,
        children=[
            html.Span(id=f"{button_id}-spinner", className="btn-spinner hidden"),
            html.Span(id=f"{button_id}-text", children=text)
        ]
    )


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
                create_action_button("start-measurement-btn", "Draw Analysis Area", "btn-primary"),
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
                    ),
                    html.Small("Valid range: 1-8760 hours per year", 
                              style={"color": "#6b7280", "fontSize": "0.75rem", "marginTop": "0.25rem", "display": "block"})
                ], className="form-group"),
                html.Div(id="measurement-status", className="status-display"),
                html.Div(id="data-summary", className="summary-display")
            ]
        ),
        
        # STEP 2: Building Filters (optional, initially collapsed)
        create_collapsible_section(
            section_id='section-building-filters',
            step_number=2,
            title='Building Filters',
            optional=True,
            initial_collapsed=True,
            content=[
                create_action_button("apply-filters-btn", "Apply Filters", "btn-primary", disabled=True),
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
                            ),
                            html.Small("Minimum annual heat demand in kWh", 
                                      style={"color": "#6b7280", "fontSize": "0.75rem", "marginTop": "0.25rem", "display": "block"})
                        ], style={"width": "48%", "display": "inline-block"}),
                        html.Div([
                            html.Label("Max Heat Demand:", className="form-label"),
                            dcc.Input(
                                id="max-heat-demand",
                                type="number",
                                placeholder="Max kWh/year",
                                value=default_max_heat,
                                className="form-input"
                            ),
                            html.Small("Maximum annual heat demand in kWh", 
                                      style={"color": "#6b7280", "fontSize": "0.75rem", "marginTop": "0.25rem", "display": "block"})
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
        
        # STEP 3: Heat Sources (initially collapsed)
        create_collapsible_section(
            section_id='section-heat-sources',
            step_number=3,
            title='Heat Sources',
            initial_collapsed=True,
            content=[
                create_action_button("add-heat-source-btn", "Add Heat Source", "btn-secondary", disabled=True),
                create_action_button("clear-heat-sources-btn", "Clear Heat Sources", "btn-secondary", disabled=True),
                html.Div([
                    html.Label("Mass Flow Calculation Mode:", className="form-label"),
                    dcc.RadioItems(
                        id="mass-flow-mode",
                        options=[
                            {'label': ' Demand-matching', 'value': 'demand'},
                            {'label': ' Manual', 'value': 'manual'}
                        ],
                        value='demand',
                        className="form-radio",
                        style={"marginBottom": "10px"}
                    ),
                    html.Div(id="mass-flow-mode-indicator")
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
                    html.Small("Valid range: ≥ 0 GW/year (used in manual mass flow mode)", 
                              style={"color": "#6b7280", "fontSize": "0.75rem", "marginTop": "0.25rem", "display": "block"})
                ], id="heat-production-input-container", className="form-group"),
                html.Div(id="heat-source-status", className="status-display"),
                html.Div(id="heat-source-summary", className="summary-display")
            ]
        ),
        
        # STEP 4: Network Generation (initially collapsed)
        create_collapsible_section(
            section_id='section-network-generation',
            step_number=4,
            title='District Heating Network',
            initial_collapsed=True,
            content=[
                create_action_button("generate-network-btn", "Generate Network", "btn-primary", disabled=True),
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
                create_action_button("optimize-network-btn", "Optimize Network", "btn-primary", disabled=True),
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
                    ),
                    html.Small("Valid range: ≥ 0 meters (max distance to connect buildings to street network)", 
                              style={"color": "#6b7280", "fontSize": "0.75rem", "marginTop": "0.25rem", "display": "block"})
                ], className="form-group"),
                html.Div([
                    html.Label("Network Optimization:", className="form-label"),
                    dcc.Dropdown(
                        id="pruning-algorithm-dropdown",
                        options=[
                            {"label": "None", "value": "none"},
                            {"label": "Minimum Spanning Tree", "value": "minimum_spanning_tree"},
                            {"label": "All Building Connections", "value": "all_building_connections"},
                            {"label": "Steiner Tree", "value": "steiner_tree"},
                            {"label": "Loop-Enhanced MST (Hydraulic Optimization)", "value": "loop_enhanced_mst"}
                        ],
                        value="none",
                        clearable=True,
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
            create_action_button("sim-init-btn", "Initialize Net", "btn-secondary", disabled=True),
            create_action_button("sim-run-btn", "Run Pipeflow", "btn-primary", disabled=True)
        ], className="button-group"),

        # Status + validation alert + summary placeholders
        html.Div(id="sim-status", className="status-display"),
        html.Div(id="validation-alert", style={'display': 'none'}),
        html.Div(id="sim-summary", className="status-display"),
    ], id="section-simulation", className="status-panel locked")  # Initially locked