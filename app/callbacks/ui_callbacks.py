"""Callbacks for UI updates and status displays."""
import logging
from dash_extensions.enrich import Input, Output, no_update, clientside_callback # type: ignore
from dash import html, dcc # type: ignore

from .base_callback import BaseCallback

logger = logging.getLogger(__name__)


class UICallbacks(BaseCallback):
    """Handles callbacks related to UI updates and displays."""
    
    def _register_callbacks(self):
        """Register UI-related callbacks."""
        
        @self.app.callback(
            Output("filter-status", "children"),
            Input("filtered-buildings", "data"),
            prevent_initial_call=True
        )
        def update_filter_status(filter_data):
            """Update building filter status display."""
            if filter_data and isinstance(filter_data, dict):
                if filter_data.get("status") == "saved":
                    return ""  # No success message
                elif filter_data.get("status") == "error":
                    return html.Div(
                        f"❌ Filter error: {filter_data.get('message')}", 
                        className="error-message"
                    )
                elif filter_data.get("status") == "empty":
                    return html.Div(
                        "⚠️ No buildings match the current filters", 
                        className="warning-message"
                    )
            
            return ""  # Empty message

        @self.app.callback(
            Output("measurement-status", "children"),
            Input("start-measurement-btn", "n_clicks"),
            prevent_initial_call=True
        )
        def handle_measurement_button(n_clicks):
            """Handle measurement button click and provide status."""
            return ""

        # Add clientside callback to trigger the JavaScript function
        clientside_callback(
            "handleMeasurementButton",
            Output("start-measurement-btn", "data-n-clicks"),
            Input("start-measurement-btn", "n_clicks"),
            prevent_initial_call=True
        )

        @self.app.callback(
            Output("data-summary", "children"),
            [Input("buildings-processed", "data"), Input("filtered-buildings", "data")]
        )
        def update_data_summary(buildings_data, filter_data):
            """Update data summary display."""
            summary_elements = []
            
            if buildings_data and isinstance(buildings_data, dict):
                heat_stats = buildings_data.get("heat_demand_stats", {})
                
                if isinstance(heat_stats, dict) and "total_buildings" in heat_stats:
                    summary_elements.extend([
                        html.H4("Data Summary"),
                        html.P(f"Total buildings found: {heat_stats['total_buildings']}"),
                        html.P(f"Buildings with heat data: {heat_stats['buildings_with_data']} ({heat_stats['coverage_percentage']}%)"),
                        html.P(f"Total heat demand: {heat_stats.get('total_heat_demand', 0)} kWh")
                    ])
            
            return summary_elements if summary_elements else "No data available"