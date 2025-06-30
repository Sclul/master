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
            Input("geojson-saved", "data"),
            prevent_initial_call=True
        )
        def update_filter_options(geojson_data):
            """Update dropdown options based on loaded building data."""
            if not geojson_data:
                empty_options = []
                return empty_options, empty_options, empty_options, empty_options, {}
            
            try:
                # Load buildings data to get filter options
                buildings_gdf, _ = self.building_filter.load_geospatial_data()
                
                if buildings_gdf is None or buildings_gdf.empty:
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
            Output("geojson-saved", "data"),
            Input("map", "coords"),
            prevent_initial_call=True
        )
        def process_polygon_data(coords):
            """Process polygon data from map coordinates."""
            if not coords:
                return no_update
            
            try:
                logger.info("Processing polygon coordinates from map")
                
                self.geospatial_handler.clear_data_directory()

                # Create GeoJSON from coordinates
                geojson = self.geospatial_handler.create_geojson_from_coordinates(coords)
                
                # Save polygon
                polygon_path = self.data_paths["polygon_path"]
                self.geospatial_handler.save_polygon(geojson, polygon_path)
                
                # Process streets
                streets_path = self.data_paths["streets_path"]
                streets_result = self.geospatial_handler.process_streets_from_polygon(geojson, streets_path)
                
                # Process buildings
                buildings_path = self.data_paths["buildings_path"]
                buildings_result = self.geospatial_handler.process_buildings_from_polygon(geojson, buildings_path)
                
                return {
                    "streets": streets_result,
                    "buildings": buildings_result
                }
                
            except Exception as e:
                logger.error(f"Error processing polygon: {e}")
                return {
                    "streets": {"status": "error", "message": str(e)},
                    "buildings": {"status": "error", "message": str(e)}
                }
        
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