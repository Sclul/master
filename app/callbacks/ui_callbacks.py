"""Callbacks for UI updates and status displays."""
import logging
from dash_extensions.enrich import Input, Output, no_update # type: ignore
from dash import html, dcc

from .base_callback import BaseCallback

logger = logging.getLogger(__name__)


class UICallbacks(BaseCallback):
    """Handles callbacks related to UI updates and displays."""
    
    def _register_callbacks(self):
        """Register UI-related callbacks."""
        
        @self.app.callback(
            Output("log", "children"), 
            Input("geojson-saved", "data")
        )
        def update_processing_log(status_data):
            """Update main processing log display."""
            if status_data is not None and isinstance(status_data, dict):
                return self._format_processing_messages(status_data)
            
            return "Ready to process polygon data"
        
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
            Output("data-summary", "children"),
            [Input("geojson-saved", "data"), Input("filtered-buildings", "data")]
        )
        def update_data_summary(processing_data, filter_data):
            """Update data summary display."""
            summary_elements = []
            
            if processing_data and isinstance(processing_data, dict):
                buildings_status = processing_data.get("buildings", {})
                heat_stats = buildings_status.get("heat_demand_stats", {})
                
                if isinstance(heat_stats, dict) and "total_buildings" in heat_stats:
                    summary_elements.extend([
                        html.H4("Data Summary"),
                        html.P(f"Total buildings found: {heat_stats['total_buildings']}"),
                        html.P(f"Buildings with heat data: {heat_stats['buildings_with_data']} ({heat_stats['coverage_percentage']}%)"),
                        html.P(f"Total heat demand: {heat_stats.get('total_heat_demand', 0)} kWh")
                    ])
            
            return summary_elements if summary_elements else "No data available"
    
    def _format_processing_messages(self, status_data):
        """Format processing status messages."""
        streets_status = status_data.get("streets", {})
        buildings_status = status_data.get("buildings", {})
        
        messages = []
        
        # Streets status
        if streets_status.get("status") == "no_streets":
            messages.append("❌ No streets found in the selected area.")
        elif streets_status.get("status") == "error":
            messages.append(f"❌ Streets error: {streets_status.get('message')}")
        elif streets_status.get("status") == "saved":
            messages.append("✅ Streets processed successfully")
        
        # Buildings status
        if buildings_status.get("status") == "no_buildings":
            messages.append("❌ No buildings found in the selected area.")
        elif buildings_status.get("status") == "error":
            messages.append(f"❌ Buildings error: {buildings_status.get('message')}")
        elif buildings_status.get("status") == "saved":
            messages.append("✅ Buildings processed successfully")
            
            # Heat demand statistics
            heat_stats = buildings_status.get("heat_demand_stats", {})
            if isinstance(heat_stats, dict) and "total_buildings" in heat_stats:
                messages.append(f"📊 Heat demand data: {heat_stats['buildings_with_data']}/{heat_stats['total_buildings']} buildings ({heat_stats['coverage_percentage']}% coverage)")
                if heat_stats.get("total_heat_demand"):
                    messages.append(f"🔥 Total heat demand: {heat_stats['total_heat_demand']} kWh")
        
        return [html.Div(message) for message in messages] if messages else "Processing completed"