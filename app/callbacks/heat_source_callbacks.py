"""Callbacks for heat source management."""
import logging
from dash_extensions.enrich import Input, Output, State, no_update # type: ignore
from dash import html # type: ignore

from .base_callback import BaseCallback
from heat_source_handler import HeatSourceHandler

logger = logging.getLogger(__name__)


class HeatSourceCallbacks(BaseCallback):
    """Handles callbacks related to heat source placement and management."""
    
    def __init__(self, app, config):
        """Initialize with Dash app and configuration."""
        super().__init__(app, config)
        self.heat_source_handler = HeatSourceHandler(config)
        self._heat_source_mode = False  # Track if we're in heat source placement mode
        
    def _register_callbacks(self):
        """Register heat source-related callbacks."""
        
        @self.app.callback(
            [
                Output("heat-source-status", "children"),
                Output("heat-source-summary", "children"),
                Output("heat-sources-data", "data")  # For triggering map updates
            ],
            Input("map", "click_lat_lng"),
            [
                State("add-heat-source-btn", "n_clicks"),
                State("heat-source-production-input", "value")
            ],
            prevent_initial_call=True
        )
        def handle_map_click_for_heat_source(click_coords, heat_source_btn_clicks, production_value):
            """Handle map clicks when in heat source placement mode."""
            if not click_coords or not heat_source_btn_clicks:
                return no_update, no_update, no_update
            
            # Only process if we're in heat source mode (button was clicked)
            if not self._heat_source_mode:
                return no_update, no_update, no_update
            
            lat, lng = click_coords
            production = production_value if production_value is not None else 1000.0
            
            logger.info(f"Adding heat source at coordinates: {lat}, {lng} with production: {production}")
            
            # Add heat source
            result = self.heat_source_handler.add_heat_source(
                latitude=lat,
                longitude=lng,
                annual_heat_production=production,
                heat_source_type="Generic"
            )
            
            # Get updated summary
            summary = self.heat_source_handler.get_heat_sources_summary()
            
            if result.get("status") == "success":
                status_msg = html.Div([
                    html.P(f"{result['message']}", className="success-message"),
                    html.P(f"Location: {lat:.4f}, {lng:.4f}", className="info-message"),
                    html.P(f"Production: {production} kWh/year", className="info-message")
                ])
                
                summary_msg = html.Div([
                    html.P(f"Total Sources: {summary.get('total_count', 0)}", className="info-message"),
                    html.P(f"Total Production: {summary.get('total_production', 0):.0f} kWh/year", className="info-message")
                ])
                
                # Reset heat source mode after successful placement
                self._heat_source_mode = False
                
                return status_msg, summary_msg, {"updated": True, "timestamp": result.get("heat_source_id")}
            else:
                error_msg = html.Div(f"{result.get('message', 'Unknown error')}", className="error-message")
                return error_msg, no_update, no_update
        
        @self.app.callback(
            Output("heat-source-status", "children", allow_duplicate=True),
            Input("add-heat-source-btn", "n_clicks"),
            prevent_initial_call=True
        )
        def toggle_heat_source_mode(n_clicks):
            """Toggle heat source placement mode."""
            if not n_clicks:
                return no_update
            
            self._heat_source_mode = True
            logger.info("Heat source placement mode activated")
            
            return html.Div("Click on the map to place a heat source", className="info-message")
        
        @self.app.callback(
            [
                Output("heat-source-status", "children", allow_duplicate=True),
                Output("heat-source-summary", "children", allow_duplicate=True),
                Output("heat-sources-data", "data", allow_duplicate=True)
            ],
            Input("clear-heat-sources-btn", "n_clicks"),
            prevent_initial_call=True
        )
        def clear_all_heat_sources(n_clicks):
            """Clear all heat sources."""
            if not n_clicks:
                return no_update, no_update, no_update
            
            logger.info("Clearing all heat sources")
            result = self.heat_source_handler.clear_all_heat_sources()
            
            if result.get("status") == "success":
                status_msg = html.Div(f"{result['message']}", className="success-message")
                summary_msg = html.Div("No heat sources", className="info-message")
                
                # Reset heat source mode
                self._heat_source_mode = False
                
                return status_msg, summary_msg, {"cleared": True, "timestamp": n_clicks}
            else:
                error_msg = html.Div(f"{result.get('message', 'Unknown error')}", className="error-message")
                return error_msg, no_update, no_update
        
        @self.app.callback(
            Output("heat-source-summary", "children", allow_duplicate=True),
            Input("heat-sources-data", "data"),
            prevent_initial_call=True
        )
        def update_heat_source_summary(heat_sources_data):
            """Update heat source summary when data changes."""
            if not heat_sources_data:
                return no_update
            
            summary = self.heat_source_handler.get_heat_sources_summary()
            
            if summary.get("status") == "success":
                total_count = summary.get("total_count", 0)
                total_production = summary.get("total_production", 0)
                
                if total_count == 0:
                    return html.Div("No heat sources", className="info-message")
                else:
                    return html.Div([
                        html.H4("Heat Source Summary", className="summary-title"),
                        html.P(f"Total Sources: {summary.get('count', 0)}", className="info-message"),
                        html.P(f"Total Production: {total_production:.0f} kWh/year", className="info-message")
                    ])
            else:
                return html.Div(f"{summary.get('message', 'Error getting summary')}", className="error-message")
