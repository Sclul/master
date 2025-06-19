"""Callbacks for geospatial data processing and building filtering."""
import logging
from dash_extensions.enrich import Input, Output, State, no_update # type: ignore
from dash import html

from .base_callback import BaseCallback
from geospatial_handler import GeospatialHandler  # Remove the ..
from building_filter import BuildingFilter  # Remove the ..

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
            prevent_initial_call=True
        )
        def apply_building_filters(n_clicks):
            """Apply building filters and save filtered results."""
            if not n_clicks:
                return no_update
            
            try:
                logger.info("Applying building filters")
                
                # Load and filter buildings using default config filters
                filtered_buildings, streets = self.building_filter.load_and_filter_buildings()
                
                if filtered_buildings is None:
                    return {"status": "error", "message": "Could not load buildings data"}
                
                if filtered_buildings.empty:
                    return {"status": "empty", "message": "No buildings match the current filters"}
                
                # Save filtered buildings
                save_result = self.building_filter.save_filtered_buildings(filtered_buildings)
                
                return {
                    **save_result,
                    "filter_applied": True
                }

            except Exception as e:
                logger.error(f"Error applying building filters: {e}")
                return {"status": "error", "message": str(e)}