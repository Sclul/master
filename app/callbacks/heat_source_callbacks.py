"""Callbacks for heat source management."""
import logging
from dash_extensions.enrich import Input, Output, State, no_update # type: ignore
from dash import html # type: ignore

from .base_callback import BaseCallback
from heat_source_handler import HeatSourceHandler
from utils.status_messages import status_message

logger = logging.getLogger(__name__)


class HeatSourceCallbacks(BaseCallback):
    """Handles callbacks related to heat source placement and management."""
    
    def __init__(self, app, config):
        """Initialize with Dash app and configuration."""
        super().__init__(app, config)
        self.heat_source_handler = HeatSourceHandler(config)
        self._heat_source_mode = False  # Track if we're in heat source placement mode
    
    def _get_production_capacity_for_mode(self, mode, operating_hours=None):
        """
        Get production capacity based on mode.
        
        In demand mode: returns total building demand (kWh/year)
        In manual mode: returns total heat source production (kWh/year)
        """
        from layout.ui_components import create_metric_card
        from pathlib import Path
        
        summary = self.heat_source_handler.get_heat_sources_summary()
        heat_source_count = summary.get('total_count', 0)
        
        if mode == "demand":
            # In demand mode, show building demand as production capacity
            # Load buildings to get total demand
            buildings_path = self.config.data_paths.get("filtered_buildings_path", "./data/filtered_buildings.geojson")
            if not Path(buildings_path).exists():
                buildings_path = self.config.data_paths.get("buildings_path", "./data/buildings.geojson")
            
            if Path(buildings_path).exists():
                import geopandas as gpd
                buildings_gdf = gpd.read_file(buildings_path)
                
                if not buildings_gdf.empty and 'heat_demand' in buildings_gdf.columns:
                    # Sum all building heat demands (already in kWh/year)
                    total_demand_kwh = buildings_gdf['heat_demand'].sum()
                    
                    # Convert to appropriate unit
                    if total_demand_kwh >= 1_000_000:
                        production_value = total_demand_kwh / 1_000_000
                        production_unit = "GWh/year"
                    elif total_demand_kwh >= 1_000:
                        production_value = total_demand_kwh / 1_000
                        production_unit = "MWh/year"
                    else:
                        production_value = total_demand_kwh
                        production_unit = "kWh/year"
                    
                    return heat_source_count, production_value, production_unit
            
            # Fallback if no buildings found
            return heat_source_count, 0.0, "GWh/year"
        else:
            # Manual mode: show heat source production from file
            total_production_kwh = summary.get('total_production', 0)  # Already in kWh/year
            
            # Convert to appropriate unit (same as manual entry: GW/year)
            total_production_gw = total_production_kwh / 1_000_000
            return heat_source_count, total_production_gw, "GW/year"
        
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
                State("heat-source-production-input", "value"),
                State("mass-flow-mode-store", "data")
            ],
            prevent_initial_call=True
        )
        def handle_map_click_for_heat_source(click_coords, heat_source_btn_clicks, production_value, mass_flow_mode):
            """Handle map clicks when in heat source placement mode."""
            if not click_coords or not heat_source_btn_clicks:
                return no_update, no_update, no_update
            
            # Only process if we're in heat source mode (button was clicked)
            if not self._heat_source_mode:
                return no_update, no_update, no_update
            
            lat, lng = click_coords
            production = production_value if production_value is not None else 1.0
            
            logger.info(f"Adding heat source at coordinates: {lat}, {lng} with production: {production} GW/year")
            
            # Add heat source
            result = self.heat_source_handler.add_heat_source(
                latitude=lat,
                longitude=lng,
                annual_heat_production=production,
                heat_source_type="Generic"
            )
            
            # Load all heat sources for the store
            heat_sources_gdf = self.heat_source_handler.load_heat_sources()
            heat_sources_list = []
            if not heat_sources_gdf.empty:
                # Convert to list of dicts for the store
                # Need to convert geometry to JSON-serializable format
                for idx, row in heat_sources_gdf.iterrows():
                    source_dict = {
                        'id': row['id'],
                        'annual_heat_production': float(row['annual_heat_production']),
                        'heat_source_type': row['heat_source_type'],
                        'latitude': row.geometry.y,
                        'longitude': row.geometry.x
                    }
                    heat_sources_list.append(source_dict)
            
            if result.get("status") == "success":
                # Import metric card components
                from layout.ui_components import create_metric_card, create_metric_group
                
                # Get production capacity based on mode
                mode = mass_flow_mode if mass_flow_mode else "demand"
                heat_source_count, production_value, production_unit = self._get_production_capacity_for_mode(mode)
                
                status_msg = status_message.success(result['message'])
                
                # Create metric cards for heat source summary
                metrics = [
                    create_metric_card(
                        label="Total Heat Sources",
                        value=heat_source_count,
                        unit="sources"
                    ),
                    create_metric_card(
                        label="Total Production Capacity",
                        value=production_value,
                        unit=production_unit
                    )
                ]
                
                summary_msg = create_metric_group(
                    title="Heat Source Summary",
                    metrics=metrics
                )
                
                # Reset heat source mode after successful placement
                self._heat_source_mode = False
                
                return status_msg, summary_msg, heat_sources_list
            else:
                return status_message.error(result.get('message', 'Unknown error')), no_update, no_update
        
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
            
            return status_message.info("Click on the map to place a heat source")
        
        @self.app.callback(
            [
                Output("heat-source-status", "children", allow_duplicate=True),
                Output("heat-source-summary", "children", allow_duplicate=True),
                Output("heat-sources-data", "data", allow_duplicate=True)
            ],
            Input("clear-heat-sources-btn", "n_clicks"),
            State("mass-flow-mode-store", "data"),
            prevent_initial_call=True
        )
        def clear_all_heat_sources(n_clicks, mass_flow_mode):
            """Clear all heat sources."""
            if not n_clicks:
                return no_update, no_update, no_update
            
            logger.info("Clearing all heat sources")
            result = self.heat_source_handler.clear_all_heat_sources()
            
            if result.get("status") == "success":
                # Import metric card components
                from layout.ui_components import create_metric_card, create_metric_group
                
                # Get production capacity based on mode
                mode = mass_flow_mode if mass_flow_mode else "demand"
                heat_source_count, production_value, production_unit = self._get_production_capacity_for_mode(mode)
                
                # Create metric cards
                metrics = [
                    create_metric_card(
                        label="Total Heat Sources",
                        value=heat_source_count,
                        unit="sources"
                    ),
                    create_metric_card(
                        label="Total Production Capacity",
                        value=production_value,
                        unit=production_unit
                    )
                ]
                
                summary_msg = create_metric_group(
                    title="Heat Source Summary",
                    metrics=metrics
                )
                
                # Reset heat source mode
                self._heat_source_mode = False
                
                return status_message.success(result['message']), summary_msg, []  # Return empty list
            else:
                return status_message.error(result.get('message', 'Unknown error')), no_update, no_update
        
        @self.app.callback(
            Output("heat-source-summary", "children", allow_duplicate=True),
            Input("heat-sources-data", "data"),
            State("mass-flow-mode-store", "data"),
            prevent_initial_call=True
        )
        def update_heat_source_summary(heat_sources_data, mass_flow_mode):
            """Update heat source summary when data changes."""
            from layout.ui_components import create_metric_card, create_metric_group
            
            if not heat_sources_data:
                return no_update
            
            # Get production capacity based on mode
            mode = mass_flow_mode if mass_flow_mode else "demand"
            heat_source_count, production_value, production_unit = self._get_production_capacity_for_mode(mode)
            
            metrics = [
                create_metric_card(
                    label="Total Heat Sources",
                    value=heat_source_count,
                    unit="sources"
                ),
                create_metric_card(
                    label="Total Production Capacity",
                    value=production_value,
                    unit=production_unit
                )
            ]
            
            return create_metric_group(
                title="Heat Source Summary",
                metrics=metrics
            )
        
        @self.app.callback(
            [
                Output("mass-flow-mode-indicator", "children"),
                Output("mass-flow-mode-store", "data"),
                Output("heat-source-summary", "children", allow_duplicate=True)
            ],
            Input("mass-flow-mode", "value"),
            prevent_initial_call=False
        )
        def update_mass_flow_mode_indicator(mode):
            """Update the mode indicator based on selected mode and refresh summary."""
            from layout.ui_components import create_metric_card, create_metric_group
            
            if mode == "demand":
                indicator = html.Div([
                    html.Strong("Auto-calculated from building demand", style={
                        "color": "#059669",
                        "fontSize": "0.85rem"
                    })
                ], style={
                    "padding": "0.5rem 0.75rem", 
                    "backgroundColor": "#f0fdf4", 
                    "border": "1px solid #bbf7d0",
                    "borderRadius": "0.375rem",
                    "marginTop": "0.5rem"
                })
            else:  # manual mode
                indicator = html.Div([
                    html.Strong("Based on heat source production", style={
                        "color": "#2563eb",
                        "fontSize": "0.85rem"
                    })
                ], style={
                    "padding": "0.5rem 0.75rem", 
                    "backgroundColor": "#eff6ff", 
                    "border": "1px solid #bfdbfe",
                    "borderRadius": "0.375rem",
                    "marginTop": "0.5rem"
                })
            
            # Update heat source summary based on new mode
            heat_source_count, production_value, production_unit = self._get_production_capacity_for_mode(mode)
            
            metrics = [
                create_metric_card(
                    label="Total Heat Sources",
                    value=heat_source_count,
                    unit="sources"
                ),
                create_metric_card(
                    label="Total Production Capacity",
                    value=production_value,
                    unit=production_unit
                )
            ]
            
            summary = create_metric_group(
                title="Heat Source Summary",
                metrics=metrics
            )
            
            return indicator, mode, summary

        @self.app.callback(
            Output("heat-production-input-container", "style"),
            Input("mass-flow-mode", "value"),
            prevent_initial_call=False
        )
        def toggle_production_input(mode):
            """Show/hide production input based on mode."""
            if mode == "demand":
                return {"display": "none"}
            else:
                return {"display": "block"}
