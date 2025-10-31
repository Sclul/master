"""Callbacks for UI updates and status displays."""
import logging
from dash_extensions.enrich import Input, Output, no_update, clientside_callback # type: ignore
from dash import html, dcc # type: ignore

from .base_callback import BaseCallback
from geospatial_handler import GeospatialHandler
from utils.status_messages import status_message

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
                    return status_message.error("Filter error", details=filter_data.get('message'))
                elif filter_data.get("status") == "empty":
                    return status_message.warning("No buildings match the current filters")
            
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
            # Import metric card components
            from layout.ui_components import create_metric_card, create_metric_group
            
            # Return empty message if no data or data is cleared
            if not buildings_data or not isinstance(buildings_data, dict) or not buildings_data:
                return "No data available"
            
            if not isinstance(buildings_data, dict):
                return "No data available"
            
            heat_stats = buildings_data.get("heat_demand_stats", {})
            
            if not isinstance(heat_stats, dict) or "total_buildings" not in heat_stats:
                return "No data available"
            
            # Create metric cards for data summary
            metrics = []
            
            # Check if clustering was applied
            clustering_stats = buildings_data.get("clustering_stats")
            clustering_applied = (clustering_stats and isinstance(clustering_stats, dict) and 
                                clustering_stats.get("merged_count", 0) > 0)
            
            # Total buildings - show clustering info if applied
            if clustering_applied:
                before = clustering_stats.get("before_count", 0)
                after = clustering_stats.get("after_count", 0)
                metrics.append(
                    create_metric_card(
                        label="Buildings (Clustered)",
                        value=f"{before} → {after}"
                    )
                )
            else:
                metrics.append(
                    create_metric_card(
                        label="Total Buildings",
                        value=heat_stats['total_buildings'],
                        unit="buildings"
                    )
                )
            
            # Buildings with heat data
            metrics.append(
                create_metric_card(
                    label="With Heat Data",
                    value=f"{heat_stats['buildings_with_data']} ({heat_stats['coverage_percentage']}%)"
                )
            )
            
            # Total heat demand
            total_heat_kwh = heat_stats.get('total_heat_demand', 0)
            # Convert to MW if large enough
            if total_heat_kwh >= 1_000_000:
                heat_display_value = total_heat_kwh / 1_000_000
                heat_unit = "GWh/year"
            elif total_heat_kwh >= 1_000:
                heat_display_value = total_heat_kwh / 1_000
                heat_unit = "MWh/year"
            else:
                heat_display_value = total_heat_kwh
                heat_unit = "kWh/year"
            
            metrics.append(
                create_metric_card(
                    label="Total Heat Demand",
                    value=heat_display_value,
                    unit=heat_unit
                )
            )
            
            return create_metric_group(
                title="Data Summary",
                metrics=metrics
            )

        @self.app.callback(
            Output("operating-hours-store", "data"),
            Input("operating-hours-input", "value"),
            prevent_initial_call=False
        )
        def store_operating_hours(operating_hours):
            """Store the operating hours value."""
            if operating_hours is None or operating_hours < 1:
                # Return default value from config
                return self.config.pandapipes.get("assume_continuous_operation_h_per_year", 2000)
            return operating_hours

        @self.app.callback(
            Output("operating-hours-input", "style"),
            Input("operating-hours-input", "value"),
            prevent_initial_call=False
        )
        def validate_operating_hours(value):
            """Provide visual feedback for operating hours validation."""
            if value is None:
                return {}
            if value < 1 or value > 8760:
                return {
                    "borderColor": "#ef4444",
                    "boxShadow": "0 0 0 3px rgba(239, 68, 68, 0.1)"
                }
            return {
                "borderColor": "#10b981", 
                "boxShadow": "0 0 0 3px rgba(16, 185, 129, 0.1)"
            }

        @self.app.callback(
            Output("heat-source-production-input", "style"),
            Input("heat-source-production-input", "value"),
            prevent_initial_call=False
        )
        def validate_heat_production(value):
            """Provide visual feedback for heat production validation."""
            if value is None:
                return {}
            if value < 0:
                return {
                    "borderColor": "#ef4444",
                    "boxShadow": "0 0 0 3px rgba(239, 68, 68, 0.1)"
                }
            return {
                "borderColor": "#10b981", 
                "boxShadow": "0 0 0 3px rgba(16, 185, 129, 0.1)"
            }

        @self.app.callback(
            Output("max-building-connection-input", "style"),
            Input("max-building-connection-input", "value"),
            prevent_initial_call=False
        )
        def validate_max_building_distance(value):
            """Provide visual feedback for max building connection distance validation."""
            if value is None:
                return {}
            if value < 0:
                return {
                    "borderColor": "#ef4444",
                    "boxShadow": "0 0 0 3px rgba(239, 68, 68, 0.1)"
                }
            return {
                "borderColor": "#10b981", 
                "boxShadow": "0 0 0 3px rgba(16, 185, 129, 0.1)"
            }

        @self.app.callback(
            [Output("min-heat-demand", "style"),
             Output("max-heat-demand", "style")],
            [Input("min-heat-demand", "value"),
             Input("max-heat-demand", "value")],
            prevent_initial_call=False
        )
        def validate_heat_demand_range(min_val, max_val):
            """Provide visual feedback for heat demand range validation."""
            min_style = {}
            max_style = {}
            
            # Check if both values are present for range validation
            if min_val is not None and max_val is not None and min_val > max_val:
                # Invalid range: min > max
                min_style = {
                    "borderColor": "#ef4444",
                    "boxShadow": "0 0 0 3px rgba(239, 68, 68, 0.1)"
                }
                max_style = {
                    "borderColor": "#ef4444",
                    "boxShadow": "0 0 0 3px rgba(239, 68, 68, 0.1)"
                }
            else:
                # Valid range or incomplete
                if min_val is not None:
                    min_style = {
                        "borderColor": "#10b981", 
                        "boxShadow": "0 0 0 3px rgba(16, 185, 129, 0.1)"
                    }
                if max_val is not None:
                    max_style = {
                        "borderColor": "#10b981", 
                        "boxShadow": "0 0 0 3px rgba(16, 185, 129, 0.1)"
                    }
            
            return min_style, max_style