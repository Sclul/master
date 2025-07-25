"""Callbacks for UI updates and status displays."""
import logging
from dash_extensions.enrich import Input, Output, no_update, clientside_callback # type: ignore
from dash import html, dcc # type: ignore

from .base_callback import BaseCallback
from geospatial_handler import GeospatialHandler

logger = logging.getLogger(__name__)


class UICallbacks(BaseCallback):
    """Handles callbacks related to UI updates and displays."""
    
    def __init__(self, app, config):
        """Initialize with Dash app and configuration."""
        super().__init__(app, config)
        self.geospatial_handler = GeospatialHandler(config)
    
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
            [
                Output("measurement-status", "children"),
                Output("data-summary", "children", allow_duplicate=True),
                Output("layer-toggles", "value", allow_duplicate=True),
                Output("polygon-processed", "data", allow_duplicate=True),
                Output("streets-processed", "data", allow_duplicate=True),
                Output("buildings-processed", "data", allow_duplicate=True),
                Output("filtered-buildings", "data", allow_duplicate=True),
                Output("network-data", "data", allow_duplicate=True),
                Output("heat-sources-data", "data", allow_duplicate=True),
                Output("filter-status", "children", allow_duplicate=True)
            ],
            Input("start-measurement-btn", "n_clicks"),
            prevent_initial_call=True
        )
        def handle_measurement_button(n_clicks):
            """Handle measurement button click and clear previous data."""
            logger.info("Area Selection started - clearing previous data and layers")
            
            # Clear all files in the data directory (including heat_sources.geojson)
            try:
                clear_result = self.geospatial_handler.clear_data_directory()
                logger.info(f"Data directory clearing result: {clear_result}")
            except Exception as e:
                logger.error(f"Error clearing data directory: {e}")
            
            # Clear data summary
            empty_summary = "No data available"
            
            # Clear all layers
            empty_layers = []
            
            # Clear all data stores
            empty_data = {}
            
            # Clear filter status
            empty_filter_status = ""
            
            return ("", empty_summary, empty_layers, empty_data, empty_data, empty_data, empty_data, empty_data, empty_data, empty_filter_status)

        # Add clientside callback to trigger the JavaScript function
        clientside_callback(
            "handleMeasurementButton",
            Output("start-measurement-btn", "data-n-clicks"),
            Input("start-measurement-btn", "n_clicks"),
            prevent_initial_call=True
        )

        @self.app.callback(
            Output("data-summary", "children"),
            [Input("buildings-processed", "data"), Input("filtered-buildings", "data")],
            prevent_initial_call=False
        )
        def update_data_summary(buildings_data, filter_data):
            """Update data summary display."""
            # Return empty message if no data or data is cleared
            if not buildings_data or not isinstance(buildings_data, dict) or not buildings_data:
                return "No data available"
            
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