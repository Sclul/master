"""Callbacks for district heating network generation."""
import logging
from dash_extensions.enrich import Input, Output, State, no_update # type: ignore
from dash import html # type: ignore

from .base_callback import BaseCallback
from network_constructor import NetworkConstructor
from graph_generator import GraphGenerator
from graph_filter import GraphFilter
from utils.status_messages import status_message

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
                    
                    # Import metric card components
                    from layout.ui_components import create_metric_card, create_metric_group
                    
                    # Create metric cards for network generation results
                    metrics = [
                        create_metric_card(
                            label="Total Graph Nodes",
                            value=result.get('total_nodes', 0),
                            unit="nodes"
                        ),
                        create_metric_card(
                            label="Total Graph Edges",
                            value=result.get('total_edges', 0),
                            unit="edges"
                        )
                    ]
                    
                    status_msg = create_metric_group(
                        title="Network Generation Complete",
                        metrics=metrics
                    )
                    
                    return status_msg, result
                    
                else:
                    progress_tracker.error(result.get('message', 'Network generation failed'))
                    return status_message.error("Street network generation failed", details=result.get('message')), result
                    
            except Exception as e:
                logger.error(f"Error in street network generation callback: {e}")
                # Import here to avoid circular import
                from utils.progress_tracker import progress_tracker
                progress_tracker.error(str(e))
                return status_message.error("Street network generation error", details=str(e)), {"status": "error", "message": str(e)}
            
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
                    
                    # Import metric card components
                    from layout.ui_components import create_reduction_metric, create_metric_card, create_metric_group
                    
                    # Create metric cards for optimization results
                    metrics = [
                        create_reduction_metric(
                            label="Graph Nodes",
                            before=result['initial_stats']['total_nodes'],
                            after=result['final_stats']['total_nodes'],
                            unit="nodes"
                        ),
                        create_reduction_metric(
                            label="Graph Edges",
                            before=result['initial_stats']['total_edges'],
                            after=result['final_stats']['total_edges'],
                            unit="edges"
                        ),
                        create_metric_card(
                            label="Heat Demand Preserved",
                            value=result['final_stats']['total_heat_demand'],
                            unit="kW"
                        )
                    ]
                    
                    status_msg = create_metric_group(
                        title="Network Optimization Complete",
                        metrics=metrics
                    )
                    
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
                    return status_message.error(result['message']), no_update
                    
            except Exception as e:
                logger.error(f"Error optimizing network: {e}")
                # Import here to avoid circular import
                from utils.progress_tracker import progress_tracker
                progress_tracker.error(str(e))
                return status_message.error("Optimization failed", details=str(e)), no_update
