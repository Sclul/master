"""UI control and status components - simplified to essential features."""
from dash import dcc, html


def create_control_panel():
    """Create the control panel with only essential controls."""
    return html.Div([
        html.H3("Controls"),
        
        # Building filters - the only control you're actually using
        html.Section([
            html.H4("Building Filters"),
            html.Button("Apply Filters", id="apply-filters-btn", className="btn-primary"),
            html.Div(id="filter-status")
        ], className="filter-section"),
        
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