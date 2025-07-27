"""Callbacks for district heating network generation."""
import logging
from dash_extensions.enrich import Input, Output, State, no_update # type: ignore
from dash import html # type: ignore

from .base_callback import BaseCallback
from network_constructor import NetworkConstructor
from graph_generator import GraphGenerator
from graph_filter import GraphFilter

logger = logging.getLogger(__name__)


class NetworkCallbacks(BaseCallback):
    """Handles callbacks related to district heating network generation."""
    
    def __init__(self, app, config):
        """Initialize with Dash app and configuration."""
        super().__init__(app, config)
        self.network_constructor = NetworkConstructor(config)
        self.graph_generator = GraphGenerator(config)
        self.graph_filter = GraphFilter(config)
        
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
            """Generate street network with nodes for every coordinate when button is clicked."""
            if not n_clicks:
                return no_update, no_update
            
            try:
                logger.info("Starting street network generation")
                
                # Import here to avoid circular import
                from utils.progress_tracker import progress_tracker
                
                # Start progress tracking
                progress_tracker.start("Generating street network...")
                
                # Generate the street network with nodes for every coordinate
                result = self.graph_generator.generate_graph()
                
                # Update status display
                if result.get("status") == "success":
                    progress_tracker.complete(f"Network generated: {result.get('total_nodes', 0)} nodes, {result.get('total_edges', 0)} edges")
                    
                    status_message = html.Div([
                        html.P(f"✅ {result.get('message')}", className="success-message"),
                        html.P(f"Total nodes: {result.get('total_nodes', 0)}", 
                              className="info-message"),
                        html.P(f"Total edges: {result.get('total_edges', 0)}", 
                              className="info-message")
                    ])
                    
                    return status_message, result
                    
                else:
                    progress_tracker.error(result.get('message', 'Network generation failed'))
                    error_message = html.Div(
                        f"❌ Street network generation failed: {result.get('message')}", 
                        className="error-message"
                    )
                    return error_message, result
                    
            except Exception as e:
                logger.error(f"Error in street network generation callback: {e}")
                # Import here to avoid circular import
                from utils.progress_tracker import progress_tracker
                progress_tracker.error(str(e))
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
        
        @self.app.callback(
            [Output("network-optimization-status", "children"),
             Output("network-data", "data", allow_duplicate=True)],
            [Input("optimize-network-btn", "n_clicks")],
            [State("max-building-connection-input", "value"),
             State("pruning-algorithm-dropdown", "value")],
            prevent_initial_call=True
        )
        def optimize_network(n_clicks, max_connection, pruning_algo):
            """Handle network optimization."""
            if not n_clicks:
                return no_update, no_update
            
            try:
                # Import here to avoid circular import
                from utils.progress_tracker import progress_tracker
                
                # Start progress tracking
                progress_tracker.start("Optimizing network...")
                
                # Apply graph filtering and optimization
                result = self.graph_filter.filter_and_optimize_graph(
                    max_building_connection=max_connection,
                    pruning_algorithm=pruning_algo if pruning_algo != "none" else None
                )
                
                if result["status"] == "success":
                    progress_tracker.update(80, "Converting to visualization format...")
                    
                    # Convert optimized GraphML to GeoJSON for visualization
                    geojson_result = self.network_constructor.build_network_geojson_from_graphml(
                        graphml_path=result["file_path"],
                        output_path=self.config.data_paths.get("filtered_network_path", "./data/filtered_heating_network.geojson")
                    )
                    
                    # Display optimization results
                    progress_tracker.complete(f"Network optimized: {result['node_reduction_percentage']}% nodes reduced, {result['edge_reduction_percentage']}% edges reduced")
                    
                    status_msg = html.Div([
                        html.P(f"✓ Network optimized successfully", className="success-message"),
                        html.P(f"Nodes: {result['initial_stats']['total_nodes']} → {result['final_stats']['total_nodes']} ({result['node_reduction_percentage']}% reduction)"),
                        html.P(f"Edges: {result['initial_stats']['total_edges']} → {result['final_stats']['total_edges']} ({result['edge_reduction_percentage']}% reduction)"),
                        html.P(f"Heat demand preserved: {result['final_stats']['total_heat_demand']} kW")
                    ])
                    
                    # Update network data to trigger map update
                    if geojson_result["status"] == "success":
                        network_data = {
                            "status": "success",
                            "message": "Network optimized and converted to GeoJSON",
                            "file_path": geojson_result["file_path"],
                            "optimization_stats": result
                        }
                        return status_msg, network_data
                    else:
                        return status_msg, no_update
                else:
                    progress_tracker.error(result['message'])
                    return html.P(f"✗ Error: {result['message']}", className="error-message"), no_update
                    
            except Exception as e:
                logger.error(f"Error optimizing network: {e}")
                # Import here to avoid circular import
                from utils.progress_tracker import progress_tracker
                progress_tracker.error(str(e))
                return html.P(f"✗ Error: {str(e)}", className="error-message"), no_update
