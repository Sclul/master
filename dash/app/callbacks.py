"""Dash callback functions for the application."""
import logging
from dash_extensions.enrich import Input, Output, no_update # type: ignore
from dash import html # type: ignore

from geospatial_handler import GeospatialHandler


logger = logging.getLogger(__name__)


class CallbackManager:
    """Manages all Dash callbacks for the application."""
    
    def __init__(self, app, config):
        """Initialize with Dash app and configuration."""
        self.app = app
        self.config = config
        self.geospatial_handler = GeospatialHandler(config)
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
                geojson = self.geospatial_handler.create_geojson_from_coordinates(coordinates)
                # Save polygon
                self.geospatial_handler.save_polygon(geojson, self.data_paths["polygon_path"])

                # Process streets and return status
                streets_status = self.geospatial_handler.process_streets_from_polygon(
                    geojson,
                    self.data_paths["streets_path"]
                )
                
                # Process buildings
                buildings_status = self.geospatial_handler.process_buildings_from_polygon(
                    geojson,
                    self.data_paths["buildings_path"]
                )
                logger.info(f"Building processing status: {buildings_status}")
                
                return {"streets": streets_status, "buildings": buildings_status}
            
            return no_update
        
        @self.app.callback(Output("log", "children"), Input("geojson-saved", "data"))
        def update_log(status_data):
            """Update log display based on processing status."""
            if status_data is not None and isinstance(status_data, dict):
                streets_status = status_data.get("streets", {})
                buildings_status = status_data.get("buildings", {})
                
                messages = []
                
                # Check streets status
                if streets_status.get("status") == "no_streets":
                    messages.append("❌ No streets found in the selected area.")
                elif streets_status.get("status") == "error":
                    messages.append(f"❌ Streets error: {streets_status.get('message')}")
                elif streets_status.get("status") == "saved":
                    messages.append("✅ Streets processed successfully")
                
                # Check buildings status
                if buildings_status.get("status") == "no_buildings":
                    messages.append("❌ No buildings found in the selected area.")
                elif buildings_status.get("status") == "error":
                    messages.append(f"❌ Buildings error: {buildings_status.get('message')}")
                elif buildings_status.get("status") == "saved":
                    messages.append("✅ Buildings processed successfully")
                    
                    # Add heat demand statistics if available
                    heat_stats = buildings_status.get("heat_demand_stats", {})
                    if isinstance(heat_stats, dict) and "total_buildings" in heat_stats:
                        messages.append(f"📊 Heat demand data: {heat_stats['buildings_with_data']}/{heat_stats['total_buildings']} buildings ({heat_stats['coverage_percentage']}% coverage)")
                        if heat_stats.get("total_heat_demand"):
                            messages.append(f"🔥 Total heat demand: {heat_stats['total_heat_demand']} kWh")
                
                
                return [html.Div(message) for message in messages] if messages else "Processing completed"
            
            return "Ready to process polygon data"
