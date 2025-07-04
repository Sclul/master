"""Callbacks for geospatial data processing and building filtering."""
import logging
from dash_extensions.enrich import Input, Output, State, no_update # type: ignore
from dash import html # type: ignore

from .base_callback import BaseCallback
from geospatial_handler import GeospatialHandler
from building_filter import BuildingFilter

logger = logging.getLogger(__name__)


class GeospatialCallbacks(BaseCallback):
    """Handles callbacks related to geospatial processing and filtering."""
    
    def __init__(self, app, config):
        """Initialize with Dash app and configuration."""
        super().__init__(app, config)
        self.geospatial_handler = GeospatialHandler(config)
        self.building_filter = BuildingFilter(config)
        
    def _register_callbacks(self):
        """Register geospatial-related callbacks."""
        
        @self.app.callback(
            [
                Output("street-filter", "options"),
                Output("postcode-filter", "options"),
                Output("city-filter", "options"),
                Output("building-use-filter", "options"),
                Output("filter-options-store", "data")
            ],
            Input("buildings-processed", "data"),
            prevent_initial_call=True
        )
        def update_filter_options(buildings_data):
            """Update dropdown options based on loaded building data."""
            logger.info(f"update_filter_options called with: {buildings_data}")
            
            if not buildings_data or buildings_data.get("status") != "processed":
                logger.warning(f"Buildings data not ready: {buildings_data}")
                empty_options = []
                return empty_options, empty_options, empty_options, empty_options, {}
            
            try:
                # Load buildings data to get filter options
                buildings_gdf, _ = self.building_filter.load_geospatial_data()
                
                if buildings_gdf is None or buildings_gdf.empty:
                    logger.warning("Buildings GDF is None or empty")
                    empty_options = []
                    return empty_options, empty_options, empty_options, empty_options, {}
                
                # Get filter options
                filter_options = self.building_filter.get_filter_options(buildings_gdf)
                
                # Convert to dropdown format
                street_options = [{"label": street, "value": street} 
                                for street in filter_options.get("streets", [])]
                postcode_options = [{"label": pc, "value": pc} 
                                  for pc in filter_options.get("postcodes", [])]
                city_options = [{"label": city, "value": city} 
                              for city in filter_options.get("cities", [])]
                building_use_options = [{"label": use, "value": use} 
                                      for use in filter_options.get("building_uses", [])]
                
                logger.info(f"Updated filter options: {len(street_options)} streets, "
                           f"{len(postcode_options)} postcodes, {len(city_options)} cities, "
                           f"{len(building_use_options)} building uses")
                
                return (street_options, postcode_options, city_options, 
                       building_use_options, filter_options)
                
            except Exception as e:
                logger.error(f"Error updating filter options: {e}")
                empty_options = []
                return empty_options, empty_options, empty_options, empty_options, {}
        
        @self.app.callback(
            Output("polygon-processed", "data"),
            Input("map", "coords"),
            prevent_initial_call=True
        )
        def process_polygon_data(coords):
            """Process polygon data from map coordinates and prepare for streets/buildings processing."""
            logger.info(f"process_polygon_data called with coords: {coords}")
            
            if not coords:
                logger.warning("No coordinates provided to process_polygon_data")
                return no_update
            
            try:
                logger.info("Processing polygon coordinates from map")
                
                self.geospatial_handler.clear_data_directory()

                # Create GeoJSON from coordinates
                geojson = self.geospatial_handler.create_geojson_from_coordinates(coords)
                
                # Save polygon
                polygon_path = self.data_paths["polygon_path"]
                self.geospatial_handler.save_polygon(geojson, polygon_path)
                
                logger.info("Polygon processing completed successfully")
                return {
                    "status": "processed",
                    "geojson": geojson,
                    "timestamp": logger.handlers[0].formatter.formatTime(logging.LogRecord("", 0, "", 0, "", (), None)) if logger.handlers else None
                }
                
            except Exception as e:
                logger.error(f"Error processing polygon: {e}")
                return {
                    "status": "error",
                    "message": str(e)
                }
        
        @self.app.callback(
            Output("streets-processed", "data"),
            Input("polygon-processed", "data"),
            prevent_initial_call=True
        )
        def process_streets_data(polygon_data):
            """Process streets data from polygon."""
            logger.info(f"process_streets_data called with polygon_data: {polygon_data}")
            
            if not polygon_data or polygon_data.get("status") != "processed":
                logger.warning("No polygon data or status not 'processed' in process_streets_data")
                return no_update
            
            try:
                logger.info("Processing streets from polygon")
                
                geojson = polygon_data["geojson"]
                streets_path = self.data_paths["streets_path"]
                streets_result = self.geospatial_handler.process_streets_from_polygon(geojson, streets_path)
                
                logger.info(f"Streets processing result: {streets_result}")
                return streets_result
                
            except Exception as e:
                logger.error(f"Error processing streets: {e}")
                return {"status": "error", "message": str(e)}
        
        @self.app.callback(
            Output("buildings-processed", "data"),
            Input("polygon-processed", "data"),
            prevent_initial_call=True
        )
        def process_buildings_data(polygon_data):
            """Process buildings data from polygon."""
            logger.info(f"process_buildings_data called with polygon_data: {polygon_data}")
            
            if not polygon_data or polygon_data.get("status") != "processed":
                logger.warning("No polygon data or status not 'processed' in process_buildings_data")
                return no_update
            
            try:
                logger.info("Processing buildings from polygon")
                
                geojson = polygon_data["geojson"]
                buildings_path = self.data_paths["buildings_path"]
                buildings_result = self.geospatial_handler.process_buildings_from_polygon(geojson, buildings_path)
                
                logger.info(f"Buildings processing result: {buildings_result}")
                
                # Normalize the status to "processed" for consistency
                if buildings_result.get("status") == "saved":
                    buildings_result["status"] = "processed"
                
                return buildings_result
                
            except Exception as e:
                logger.error(f"Error processing buildings: {e}")
                return {"status": "error", "message": str(e)}
        
        @self.app.callback(
            Output("filtered-buildings", "data"),
            Input("apply-filters-btn", "n_clicks"),
            [
                State("exclude-zero-heat-demand", "value"),
                State("min-heat-demand", "value"),
                State("max-heat-demand", "value"),
                State("street-filter", "value"),
                State("postcode-filter", "value"),
                State("city-filter", "value"),
                State("building-use-filter", "value")
            ],
            prevent_initial_call=True
        )
        def apply_building_filters(n_clicks, exclude_zero_value, min_heat_demand, max_heat_demand,
                                 selected_streets, selected_postcodes, selected_cities, selected_building_uses):
            """Apply building filters and save filtered results."""
            if not n_clicks:
                return no_update
            
            try:
                logger.info("Applying building filters")
                
                # Build filter criteria from UI inputs
                filter_criteria = {}
                
                # Get base filters from config
                base_filters = self.config.building_filters
                if base_filters:
                    filter_criteria.update(base_filters)
                
                # Override with UI values
                filter_criteria["exclude_zero_heat_demand"] = bool(exclude_zero_value and "exclude" in exclude_zero_value)
                
                # Set min heat demand (default to 0 if empty)
                if min_heat_demand is not None and min_heat_demand != "":
                    filter_criteria["min_heat_demand"] = min_heat_demand
                else:
                    filter_criteria["min_heat_demand"] = 0
                
                # Set max heat demand (default to infinity if empty)
                if max_heat_demand is not None and max_heat_demand != "":
                    filter_criteria["max_heat_demand"] = max_heat_demand
                else:
                    filter_criteria["max_heat_demand"] = float('inf')
                
                # Add new filter criteria - only if not empty
                if selected_streets and len(selected_streets) > 0:
                    filter_criteria["streets"] = selected_streets
                
                if selected_postcodes and len(selected_postcodes) > 0:
                    filter_criteria["postcodes"] = selected_postcodes
                
                if selected_cities and len(selected_cities) > 0:
                    filter_criteria["cities"] = selected_cities
                
                if selected_building_uses and len(selected_building_uses) > 0:
                    filter_criteria["building_uses"] = selected_building_uses
                
                logger.info(f"Filter criteria: {filter_criteria}")
                
                # Load and filter buildings with custom criteria
                filtered_buildings, streets = self.building_filter.load_and_filter_buildings(filter_criteria)
                
                if filtered_buildings is None:
                    return {"status": "error", "message": "Could not load buildings data"}
                
                if filtered_buildings.empty:
                    return {"status": "empty", "message": "No buildings match the current filters"}
                
                # Save filtered buildings
                save_result = self.building_filter.save_filtered_buildings(filtered_buildings)
                
                return {
                    **save_result,
                    "filter_applied": True,
                    "filter_criteria": filter_criteria
                }

            except Exception as e:
                logger.error(f"Error applying building filters: {e}")
                return {"status": "error", "message": str(e)}
        
        @self.app.callback(
            Output("building-use-filter", "value"),
            Input("building-use-filter", "options"),
            prevent_initial_call=True
        )
        def set_default_building_uses(building_use_options):
            """Automatically select all building uses by default."""
            if not building_use_options:
                return []
            
            # Return all available building use values to select them by default
            all_values = [option["value"] for option in building_use_options]
            logger.info(f"Auto-selected {len(all_values)} building uses by default")
            return all_values
        
        @self.app.callback(
            [
                Output("street-filter", "options", allow_duplicate=True),
                Output("postcode-filter", "options", allow_duplicate=True),
                Output("city-filter", "options", allow_duplicate=True),
                Output("building-use-filter", "options", allow_duplicate=True),
                Output("street-filter", "value", allow_duplicate=True),
                Output("postcode-filter", "value", allow_duplicate=True),
                Output("city-filter", "value", allow_duplicate=True),
                Output("building-use-filter", "value", allow_duplicate=True),
                Output("filter-options-store", "data", allow_duplicate=True)
            ],
            Input("start-measurement-btn", "n_clicks"),
            prevent_initial_call=True
        )
        def clear_filter_options_on_measurement(n_clicks):
            """Clear all filter options when starting area selection."""
            logger.info("Area Selection started - clearing filter options")
            
            empty_options = []
            empty_values = []
            empty_store = {}
            
            return (empty_options, empty_options, empty_options, empty_options,
                   empty_values, empty_values, empty_values, empty_values, empty_store)