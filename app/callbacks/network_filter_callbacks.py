"""Callbacks for network filtering functionality."""
import logging
from dash_extensions.enrich import Input, Output, State, no_update # type: ignore
from dash import html # type: ignore

from .base_callback import BaseCallback
from network_filter import NetworkFilter

logger = logging.getLogger(__name__)


class NetworkFilterCallbacks(BaseCallback):
    """Handles callbacks related to network filtering."""
    
    def __init__(self, app, config):
        """Initialize with Dash app and configuration."""
        super().__init__(app, config)
        self.network_filter = NetworkFilter(config)
        
    def _register_callbacks(self):
        """Register network filter-related callbacks."""
        
        @self.app.callback(
            [
                Output("network-filter-status", "children"),
                Output("filtered-network-data", "data")
            ],
            Input("apply-network-filters-btn", "n_clicks"),
            [
                State("show-streets-only-filter", "value"),
                State("exclude-unconnected-nodes-checklist", "value")
            ],
            prevent_initial_call=True
        )
        def apply_network_filters(n_clicks, show_streets_only, exclude_unconnected):
            """Apply network filters when button is clicked."""
            if not n_clicks:
                return no_update, no_update
            
            try:
                logger.info("Starting network filtering")
                
                # Build filter criteria
                filter_criteria = {}
                
                if show_streets_only and "streets_only" in show_streets_only:
                    filter_criteria["edge_types"] = ["street"]
                    logger.info("Filtering to show streets only")
                
                if exclude_unconnected and "exclude" in exclude_unconnected:
                    filter_criteria["exclude_unconnected_nodes"] = True
                    logger.info("Excluding unconnected nodes")
                
                # Apply filters
                result = self.network_filter.filter_network(filter_criteria)
                
                # Update status display
                if result.get("status") == "success":
                    status_message = html.Div([
                        html.P(f"✅ Network filtered successfully", className="success-message")
                    ])
                    
                    return status_message, result
                    
                else:
                    error_message = html.Div(
                        f"❌ Network filtering failed: {result.get('message')}", 
                        className="error-message"
                    )
                    return error_message, result
                    
            except Exception as e:
                logger.error(f"Error in network filtering callback: {e}")
                error_message = html.Div(
                    f"❌ Network filtering error: {str(e)}", 
                    className="error-message"
                )
                return error_message, {"status": "error", "message": str(e)}
        
        @self.app.callback(
            Output("filtered-network-summary", "children"),
            Input("filtered-network-data", "data"),
            prevent_initial_call=True
        )
        def update_filtered_network_summary(filtered_network_data):
            """Update summary display for filtered network."""
            if not filtered_network_data or filtered_network_data.get("status") != "success":
                return "No filtered network available"
            
            try:
                # Get statistics for the filtered network
                stats = self.network_filter.get_network_statistics()
                
                if stats.get("status") == "success":
                    summary_elements = []
                    
                    # Basic network info
                    summary_elements.append(
                        html.P(f"📊 Filtered Network: {stats.get('total_nodes', 0)} nodes, "
                              f"{stats.get('total_edges', 0)} edges")
                    )
                    
                    # Node type breakdown
                    node_types = stats.get("node_types", {})
                    if node_types:
                        node_breakdown = ", ".join([f"{k}: {v}" for k, v in node_types.items()])
                        summary_elements.append(html.P(f"🏠 Nodes: {node_breakdown}"))
                    
                    # Edge type breakdown
                    edge_types = stats.get("edge_types", {})
                    if edge_types:
                        edge_breakdown = ", ".join([f"{k}: {v}" for k, v in edge_types.items()])
                        summary_elements.append(html.P(f"🔗 Edges: {edge_breakdown}"))
                    
                    # Heat demand
                    total_heat_demand = stats.get("total_heat_demand", 0)
                    if total_heat_demand > 0:
                        summary_elements.append(html.P(f"🔥 Total Heat Demand: {total_heat_demand:.2f} kW"))
                    
                    # Connectivity
                    is_connected = stats.get("is_connected", False)
                    num_components = stats.get("num_components", 0)
                    connectivity_status = "Connected" if is_connected else f"{num_components} components"
                    summary_elements.append(html.P(f"🌐 Network: {connectivity_status}"))
                    
                    return html.Div(summary_elements)
                else:
                    return "Error getting filtered network statistics"
                    
            except Exception as e:
                logger.error(f"Error updating filtered network summary: {e}")
                return "Error updating summary"
        
        @self.app.callback(
            Output("network-filter-status", "children", allow_duplicate=True),
            Input("start-measurement-btn", "n_clicks"),
            prevent_initial_call=True
        )
        def clear_network_filter_status_on_measurement(n_clicks):
            """Clear network filter status when starting area selection."""
            return ""
