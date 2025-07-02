"""Callbacks for district heating network generation."""
import logging
from dash_extensions.enrich import Input, Output, State, no_update # type: ignore
from dash import html # type: ignore

from .base_callback import BaseCallback
from district_heating_network import DistrictHeatingNetwork

logger = logging.getLogger(__name__)


class NetworkCallbacks(BaseCallback):
    """Handles callbacks related to district heating network generation."""
    
    def __init__(self, app, config):
        """Initialize with Dash app and configuration."""
        super().__init__(app, config)
        self.network_generator = DistrictHeatingNetwork(config)
        
    def _register_callbacks(self):
        """Register network-related callbacks."""
        
        @self.app.callback(
            [
                Output("network-status", "children"),
                Output("network-data", "data")
            ],
            Input("generate-network-btn", "n_clicks"),
            State("filtered-buildings", "data"),
            prevent_initial_call=True
        )
        def generate_network(n_clicks, filtered_buildings_data):
            """Generate district heating network when button is clicked."""
            if not n_clicks:
                return no_update, no_update
            
            try:
                logger.info("Starting network generation")
                
                # Check if we should use filtered buildings
                use_filtered = (
                    filtered_buildings_data and 
                    isinstance(filtered_buildings_data, dict) and 
                    filtered_buildings_data.get("status") == "saved"
                )
                
                # Generate the network
                result = self.network_generator.connect_buildings_to_streets(
                    use_filtered_buildings=use_filtered
                )
                
                # Update status display
                if result.get("status") == "success":
                    status_message = html.Div([
                        html.P(f"✅ {result.get('message')}", className="success-message"),
                        html.P(f"Total network features: {result.get('total_features', 0)}", 
                              className="info-message")
                    ])
                    
                    return status_message, result
                    
                else:
                    error_message = html.Div(
                        f"❌ Network generation failed: {result.get('message')}", 
                        className="error-message"
                    )
                    return error_message, result
                    
            except Exception as e:
                logger.error(f"Error in network generation callback: {e}")
                error_message = html.Div(
                    f"❌ Network generation error: {str(e)}", 
                    className="error-message"
                )
                return error_message, {"status": "error", "message": str(e)}
            
        @self.app.callback(
            Output("network-status", "children", allow_duplicate=True),
            Input("start-measurement-btn", "n_clicks"),
            prevent_initial_call=True
        )
        def clear_network_status_on_measurement(n_clicks):
            """Clear network status when starting area selection."""
            logger.info("Area Selection started - clearing network status")
            return ""
