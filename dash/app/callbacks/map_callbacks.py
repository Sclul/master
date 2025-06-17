"""Callbacks for map interactions and layer management."""
import logging
from dash_extensions.enrich import Input, Output, State, no_update # type: ignore
import dash_leaflet as dl # type: ignore
import json

from .base_callback import BaseCallback

logger = logging.getLogger(__name__)


class MapCallbacks(BaseCallback):
    """Handles callbacks related to map interactions and layer management."""
    
    def _register_callbacks(self):
        """Register map-related callbacks."""
        
        @self.app.callback(
            Output("map", "children"),
            Input("layer-toggles", "value"),
            State("map", "children")
        )
        def update_map_layers(selected_layers, current_children):
            """Update map layers based on toggle states."""
            if selected_layers is None:
                selected_layers = []
            
            show_streets = "streets" in selected_layers
            show_buildings = "buildings" in selected_layers
            show_filtered = "filtered" in selected_layers
            
            return self._build_map_layers(show_streets, show_buildings, show_filtered, current_children)
        
        @self.app.callback(
            Output("map-coordinates", "children"),
            Input("map", "click_lat_lng")
        )
        def display_clicked_coordinates(click_data):
            """Display coordinates of clicked location."""
            if click_data:
                return f"Clicked: {click_data[0]:.6f}, {click_data[1]:.6f}"
            return "Click on map to see coordinates"
        
        @self.app.callback(
            Output("map-zoom-info", "children"),
            Input("map", "zoom")
        )
        def update_zoom_info(zoom):
            """Display current zoom level."""
            if zoom:
                return f"Zoom: {zoom}"
            return "Zoom: Unknown"
    
    def _build_map_layers(self, show_streets, show_buildings, show_filtered, current_children):
        """Build map layers based on toggle states."""
        layers = []
        
        # Always include base tile layer and controls
        layers.append(dl.TileLayer(
            url=self.config.map_settings["tile_url"],
            attribution=self.config.map_settings["attribution"]
        ))
        
        measure_settings = self.config.map_settings["measure_settings"]
        layers.append(dl.MeasureControl(
            position=measure_settings["position"],
            primaryLengthUnit=measure_settings["primary_length_unit"],
            primaryAreaUnit=measure_settings["primary_area_unit"],
            activeColor=measure_settings["active_color"],
            completedColor=measure_settings["completed_color"]
        ))
        
        # Add conditional data layers
        if show_streets:
            street_layer = self._create_streets_layer()
            if street_layer:
                layers.append(street_layer)
        
        if show_buildings:
            buildings_layer = self._create_buildings_layer()
            if buildings_layer:
                layers.append(buildings_layer)
        
        if show_filtered:
            filtered_layer = self._create_filtered_buildings_layer()
            if filtered_layer:
                layers.append(filtered_layer)
        
        return layers
    
    def _create_streets_layer(self):
        """Create streets layer from saved data."""
        try:
            with open(self.data_paths["streets_path"], "r") as f:
                streets_geojson = json.load(f)
            
            return dl.GeoJSON(
                data=streets_geojson,
                options={"style": {"color": "blue", "weight": 3, "opacity": 0.7}},
                id="streets-layer"
            )
        except FileNotFoundError:
            logger.debug("Streets file not found - no streets layer added")
            return None
        except Exception as e:
            logger.error(f"Error creating streets layer: {e}")
            return None
    
    def _create_buildings_layer(self):
        """Create buildings layer from saved data."""
        try:
            with open(self.data_paths["buildings_path"], "r") as f:
                buildings_geojson = json.load(f)
            
            return dl.GeoJSON(
                data=buildings_geojson,
                options={"style": {"color": "red", "weight": 1, "fillOpacity": 0.3}},
                id="buildings-layer"
            )
        except FileNotFoundError:
            logger.debug("Buildings file not found - no buildings layer added")
            return None
        except Exception as e:
            logger.error(f"Error creating buildings layer: {e}")
            return None
    
    def _create_filtered_buildings_layer(self):
        """Create filtered buildings layer from saved data."""
        try:
            with open(self.data_paths["filtered_buildings_path"], "r") as f:
                filtered_geojson = json.load(f)
            
            return dl.GeoJSON(
                data=filtered_geojson,
                options={"style": {"color": "green", "weight": 2, "fillOpacity": 0.5}},
                id="filtered-buildings-layer"
            )
        except FileNotFoundError:
            logger.debug("Filtered buildings file not found - no filtered layer added")
            return None
        except Exception as e:
            logger.error(f"Error creating filtered buildings layer: {e}")
            return None