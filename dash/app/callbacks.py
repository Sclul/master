"""Dash callback functions for the application."""
import logging
from dash_extensions.enrich import Input, Output, no_update # type: ignore

from street_processor import StreetProcessor


logger = logging.getLogger(__name__)


class CallbackManager:
    """Manages all Dash callbacks for the application."""
    
    def __init__(self, app, config):
        """Initialize with Dash app and configuration."""
        self.app = app
        self.config = config
        self.street_processor = StreetProcessor(config.config)
        self.data_paths = config.data_paths
        
        # Register callbacks
        self._register_callbacks()
    
    def _register_callbacks(self):
        """Register all callbacks with the Dash app."""
        
        @self.app.callback(Output("geojson-saved", "data"), Input("map", "coords"))
        def save_geojson(message):
            """Handle polygon drawing and street processing."""
            if isinstance(message, dict) and "coordinates" in message:
                coordinates = message["coordinates"]
                logger.debug(f"Polygon coordinates: {coordinates}")
                
                # Create GeoJSON from coordinates
                geojson = self.street_processor.create_geojson_from_coordinates(coordinates)
                
                # Save polygon
                self.street_processor.save_polygon(geojson, self.data_paths["polygon_path"])
                
                # Process streets and return status
                streets_status = self.street_processor.process_streets_from_polygon(
                    geojson, 
                    self.data_paths["streets_path"]
                )
                
                # Process buildings
                buildings_status = self.street_processor.process_buildings_from_polygon(
                    geojson,
                    self.data_paths["buildings_path"]
                )
                logger.info(f"Building processing status: {buildings_status}")
                
                return streets_status # The main status returned to update_log is still from streets
            
            return no_update
        
        @self.app.callback(Output("log", "children"), Input("geojson-saved", "data"))
        def update_log(status):
            """Update log display based on processing status."""
            if status is not None and isinstance(status, dict):
                if status.get("status") == "no_streets":
                    return "No streets found in the selected area."
                if status.get("status") == "error":
                    return f"Error: {status.get('message')}"
            
            # Load and display streets data
            return self.street_processor.load_streets_data(self.data_paths["streets_path"])
