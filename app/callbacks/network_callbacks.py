"""Callbacks for district heating network generation."""
import logging
from dash_extensions.enrich import Input, Output, State, no_update # type: ignore
from dash import html # type: ignore

from .base_callback import BaseCallback
from network_constructor import NetworkConstructor
from street_network_generator import StreetNetworkGenerator

logger = logging.getLogger(__name__)


class NetworkCallbacks(BaseCallback):
    """Handles callbacks related to district heating network generation."""
    
    def __init__(self, app, config):
        """Initialize with Dash app and configuration."""
        super().__init__(app, config)
        self.network_constructor = NetworkConstructor(config)
        self.street_network_generator = StreetNetworkGenerator(config)
        
    def _register_callbacks(self):
        """Register network-related callbacks."""
        
        @self.app.callback(
            [
                Output("network-status", "children"),
                Output("network-data", "data")
            ],
            Input("generate-network-btn", "n_clicks"),
            [
                State("filtered-buildings", "data"),
                State("max-connection-distance-generation-input", "value")
            ],
            prevent_initial_call=True
        )
        def generate_network(n_clicks, filtered_buildings_data, max_connection_distance):
            """Generate street network with nodes for every coordinate when button is clicked."""
            if not n_clicks:
                return no_update, no_update
            
            try:
                logger.info("Starting street network generation")
                
                # Generate the street network with nodes for every coordinate
                result = self.street_network_generator.generate_street_network()
                
                # Update status display
                if result.get("status") == "success":
                    status_message = html.Div([
                        html.P(f"✅ {result.get('message')}", className="success-message"),
                        html.P(f"Total nodes: {result.get('total_nodes', 0)}", 
                              className="info-message"),
                        html.P(f"Total edges: {result.get('total_edges', 0)}", 
                              className="info-message")
                    ])
                    
                    return status_message, result
                    
                else:
                    error_message = html.Div(
                        f"❌ Street network generation failed: {result.get('message')}", 
                        className="error-message"
                    )
                    return error_message, result
                    
            except Exception as e:
                logger.error(f"Error in street network generation callback: {e}")
                error_message = html.Div(
                    f"❌ Street network generation error: {str(e)}", 
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
