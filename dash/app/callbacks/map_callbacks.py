"""Callbacks for map interactions and layer management."""
import logging
import json
import geopandas as gpd # type: ignore
import dash_leaflet as dl # type: ignore
from dash_extensions.enrich import Input, Output # type: ignore

from .base_callback import BaseCallback

logger = logging.getLogger(__name__)


class MapCallbacks(BaseCallback):
    """Handles callbacks related to map interactions and layer management."""
    
    def _register_callbacks(self):
        """Register map-related callbacks."""
        
        @self.app.callback(
            Output("data-layers", "children"),
            Input("layer-toggles", "value"),
        )
        def update_map_layers(selected_layers):
            """Update map layers based on toggle states."""
            if selected_layers is None:
                selected_layers = []
            
            show_streets = "streets" in selected_layers
            show_buildings = "buildings" in selected_layers
            show_filtered = "filtered" in selected_layers
            
            logger.info(f"Updating layers: streets={show_streets}, buildings={show_buildings}, filtered={show_filtered}")
            
            return self._build_data_layers(show_streets, show_buildings, show_filtered)
        
        @self.app.callback(
            Output("map-zoom-info", "children"),
            Input("map", "zoom")
        )
        def update_zoom_info(zoom):
            """Display current zoom level."""
            return f"Zoom: {zoom}" if zoom else "Zoom: Unknown"
    
    def _build_data_layers(self, show_streets, show_buildings, show_filtered):
        """Build only the data layers (not base map components)."""
        layers = []
        
        if show_streets:
            street_layer = self._create_streets_layer()
            if street_layer is not None:
                layers.append(street_layer)
                logger.info("Added streets layer to map")
        
        if show_buildings:
            buildings_layer = self._create_buildings_layer()
            if buildings_layer is not None:
                layers.append(buildings_layer)
                logger.info("Added buildings layer to map")
        
        if show_filtered:
            filtered_layer = self._create_filtered_buildings_layer()
            if filtered_layer is not None:
                layers.append(filtered_layer)
                logger.info("Added filtered buildings layer to map")
        
        logger.info(f"Total data layers built: {len(layers)}")
        return layers
    
    def _create_layer_from_file(self, file_path, layer_id, style_options):
        """Generic method to create a layer from a GeoJSON file."""
        try:
            # Read and reproject data
            gdf = gpd.read_file(file_path)
            
            if gdf.crs and str(gdf.crs) != "EPSG:4326":
                gdf = gdf.to_crs("EPSG:4326")
                logger.debug(f"Reprojected {layer_id} from {gdf.crs} to EPSG:4326")
            
            # Convert to GeoJSON dict
            geojson_data = json.loads(gdf.to_json())
            
            logger.info(f"Creating {layer_id} with {len(geojson_data.get('features', []))} features")
            
            return dl.GeoJSON(
                data=geojson_data,
                options={"style": style_options},
                id=layer_id
            )
        except FileNotFoundError:
            logger.debug(f"{layer_id} file not found: {file_path}")
            return None
        except Exception as e:
            logger.error(f"Error creating {layer_id}: {e}")
            return None
    
    def _create_streets_layer(self):
        """Create streets layer from saved data."""
        return self._create_layer_from_file(
            self.data_paths["streets_path"],
            "streets-layer",
            {"color": "blue", "weight": 3, "opacity": 0.7}
        )
    
    def _create_buildings_layer(self):
        """Create buildings layer from saved data."""
        return self._create_layer_from_file(
            self.data_paths["buildings_path"],
            "buildings-layer",
            {"color": "red", "weight": 1, "fillOpacity": 0.3}
        )
    
    def _create_filtered_buildings_layer(self):
        """Create filtered buildings layer from saved data."""
        return self._create_layer_from_file(
            self.data_paths["filtered_buildings_path"],
            "filtered-buildings-layer",
            {"color": "green", "weight": 2, "fillOpacity": 0.5}
        )