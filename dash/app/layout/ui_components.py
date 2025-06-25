"""UI control and status components - simplified to essential features."""
from dash import dcc, html


def create_control_panel(config=None):
    """Create the control panel with only essential controls."""
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
        
        # Apply filters button at the top
        html.Button("Apply Filters", id="apply-filters-btn", className="btn-primary"),
        html.Div(id="filter-status"),
        
        # Building filters - heat demand controls
        html.Section([
            html.H4("Heat Demand Filters"),
            
            # Exclude zero heat demand checkbox
            html.Div([
                dcc.Checklist(
                    id="exclude-zero-heat-demand",
                    options=[{"label": "Exclude buildings with zero heat demand", "value": "exclude"}],
                    value=["exclude"] if default_exclude_zero else [],
                    className="filter-checkbox"
                )
            ], className="filter-row"),
            
            # Min heat demand input
            html.Div([
                html.Label("Minimum Heat Demand:", className="filter-label"),
                dcc.Input(
                    id="min-heat-demand",
                    type="number",
                    placeholder="Enter minimum heat demand",
                    value=default_min_heat,
                    step=1,
                    min=0,
                    className="number-input"
                )
            ], className="filter-row"),
            
            # Max heat demand input  
            html.Div([
                html.Label("Maximum Heat Demand:", className="filter-label"),
                dcc.Input(
                    id="max-heat-demand",
                    type="number",
                    placeholder="Enter maximum heat demand",
                    value=default_max_heat,
                    step=1,
                    min=0,
                    className="number-input"
                )
            ], className="filter-row"),
            
        ], className="filter-section"),
        
        # Building attribute filters
        html.Section([
            html.H4("Building Attribute Filters"),
            
            # Street filter
            html.Div([
                html.Label("Street:", className="filter-label"),
                dcc.Dropdown(
                    id="street-filter",
                    placeholder="Select streets...",
                    multi=True,
                    className="dropdown-filter"
                )
            ], className="filter-row"),
            
            # Postcode filter
            html.Div([
                html.Label("Postcode:", className="filter-label"),
                dcc.Dropdown(
                    id="postcode-filter",
                    placeholder="Select postcodes...",
                    multi=True,
                    className="dropdown-filter"
                )
            ], className="filter-row"),
            
            # City filter
            html.Div([
                html.Label("City:", className="filter-label"),
                dcc.Dropdown(
                    id="city-filter",
                    placeholder="Select cities...",
                    multi=True,
                    className="dropdown-filter"
                )
            ], className="filter-row"),
            
            # Building use filter
            html.Div([
                html.Label("Building Use:", className="filter-label"),
                dcc.Dropdown(
                    id="building-use-filter",
                    placeholder="Select building uses...",
                    multi=True,
                    className="dropdown-filter"
                )
            ], className="filter-row"),
            
        ], className="filter-section"),
        
        # Hidden store for filter options
        dcc.Store(id="filter-options-store")
        
    ], className="control-panel-content")


def create_status_panel():
    """Create the status panel with only essential information."""
    return html.Div([
        # Processing status - essential
        html.Section([
            html.H4("Processing Status"),
            html.Div(id="log", className="log-display")
        ], className="status-section"),
        
        # Data summary - essential
        html.Section([
            html.H4("Data Summary"),
            html.Div(id="data-summary", className="summary-display")
        ], className="summary-section"),
        
    ], className="status-panel-content")