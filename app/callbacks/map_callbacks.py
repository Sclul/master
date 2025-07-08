"""Callbacks for map interactions and layer management."""
import logging
import json
from pathlib import Path
import geopandas as gpd # type: ignore
import dash_leaflet as dl # type: ignore
from dash_extensions.enrich import Input, Output, State, no_update # type: ignore
from dash import html # type: ignore

from .base_callback import BaseCallback
from network_constructor import NetworkConstructor

logger = logging.getLogger(__name__)


class MapCallbacks(BaseCallback):
    """Handles callbacks related to map interactions and layer management."""
    
    def __init__(self, app, config):
        """Initialize with Dash app and configuration."""
        super().__init__(app, config)
        self.network_constructor = NetworkConstructor(config)
    
    def _register_callbacks(self):
        """Register map-related callbacks."""
        
        @self.app.callback(
            [Output("data-layers", "children"), Output("network-status", "children", allow_duplicate=True)],
            [Input("layer-toggles", "value"), Input("network-data", "data"), Input("filtered-buildings", "data")],
        )
        def update_map_layers(selected_layers, network_data, filtered_buildings_data):
            """Update map layers based on toggle states."""
            if selected_layers is None:
                selected_layers = []
            
            show_streets = "streets" in selected_layers
            show_buildings = "buildings" in selected_layers
            show_filtered = "filtered" in selected_layers
            show_network = "network" in selected_layers
            
            logger.info(f"Updating layers: streets={show_streets}, buildings={show_buildings}, filtered={show_filtered}, network={show_network}")
            
            network_status = ""
            
            # If network layer is requested, ensure GeoJSON exists
            if show_network:
                conversion_result = self._ensure_network_geojson_exists()
                if conversion_result:
                    if conversion_result.get("converted"):
                        network_status = html.Div([
                            html.P("🔄 Network converted from GraphML to GeoJSON", className="success-message"),
                            html.P(f"Features: {conversion_result.get('total_features', 0)}", className="info-message")
                        ])
                    elif conversion_result.get("error"):
                        network_status = html.Div(
                            f"❌ Network conversion error: {conversion_result.get('message')}", 
                            className="error-message"
                        )
            
            layers = self._build_data_layers(show_streets, show_buildings, show_filtered, show_network)
            return layers, network_status

        @self.app.callback(
            Output("layer-toggles", "value"),
            Input("filtered-buildings", "data"),
            State("layer-toggles", "value"),
            prevent_initial_call=True
        )
        def auto_enable_filtered_layer(filtered_buildings_data, current_selected_layers):
            """Auto-enable filtered buildings layer when filters are applied."""
            if not filtered_buildings_data or not isinstance(filtered_buildings_data, dict):
                return no_update
            
            # Only auto-enable if filters were just applied successfully
            if filtered_buildings_data.get("filter_applied") and filtered_buildings_data.get("status") == "saved":
                updated_layers = (current_selected_layers or []).copy()
                if "filtered" not in updated_layers:
                    updated_layers.append("filtered")
                    logger.info("Auto-enabling filtered buildings layer after successful filter application")
                    return updated_layers
            
            return no_update

        @self.app.callback(
            Output("layer-toggles", "value", allow_duplicate=True),
            Input("network-data", "data"),
            State("layer-toggles", "value"),
            prevent_initial_call=True
        )
        def auto_enable_network_layer(network_data, current_selected_layers):
            """Auto-enable network layer when network is successfully generated."""
            if not network_data or not isinstance(network_data, dict):
                return no_update
            
            # Only auto-enable if network was just generated successfully
            if network_data.get("status") == "success":
                updated_layers = (current_selected_layers or []).copy()
                if "network" not in updated_layers:
                    updated_layers.append("network")
                    logger.info("Auto-enabling network layer after successful network generation")
                    return updated_layers
            
            return no_update

        @self.app.callback(
            Output("layer-toggles", "value", allow_duplicate=True),
            Input("streets-processed", "data"),
            State("layer-toggles", "value"),
            prevent_initial_call=True
        )
        def auto_enable_streets_layer(streets_data, current_selected_layers):
            """Auto-enable streets layer when streets are successfully processed and saved."""
            if not streets_data or not isinstance(streets_data, dict):
                return no_update
            
            # Only auto-enable if streets were just processed successfully
            if streets_data.get("status") == "saved":
                updated_layers = (current_selected_layers or []).copy()
                if "streets" not in updated_layers:
                    updated_layers.append("streets")
                    logger.info("Auto-enabling streets layer after successful street processing")
                    return updated_layers
            
            return no_update

        @self.app.callback(
            Output("map-zoom-info", "children"),
            Input("map", "zoom")
        )
        def update_zoom_info(zoom):
            """Display current zoom level."""
            return f"Zoom: {zoom}" if zoom else "Zoom: Unknown"
    
    def _build_data_layers(self, show_streets, show_buildings, show_filtered, show_network=False):
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
        
        if show_network:
            network_layer = self._create_network_layer()
            if network_layer is not None:
                layers.append(network_layer)
                logger.info("Added heating network layer to map")
        
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
    
    def _create_network_layer(self):
        """Create heating network layer from saved data."""
        return self._create_layer_from_file(
            self.data_paths.get("network_path", "./data/heating_network.geojson"),
            "heating-network-layer",
            {"color": "orange", "weight": 2, "opacity": 0.8}
        )
    
    def _ensure_network_geojson_exists(self):
        """Ensure network GeoJSON file exists by converting from GraphML if needed."""
        try:
            graphml_path = self.data_paths.get("network_graphml_path", "./data/heating_network.graphml")
            geojson_path = self.data_paths.get("network_path", "./data/heating_network.geojson")
            
            graphml_file = Path(graphml_path)
            geojson_file = Path(geojson_path)
            
            # Check if GraphML exists
            if not graphml_file.exists():
                logger.warning(f"GraphML file not found: {graphml_path}")
                return {"error": True, "message": f"GraphML file not found: {graphml_path}"}
            
            # Check if GeoJSON needs to be created or updated
            should_convert = False
            
            if not geojson_file.exists():
                logger.info("GeoJSON file doesn't exist, converting from GraphML")
                should_convert = True
            else:
                # Check if GraphML is newer than GeoJSON
                graphml_mtime = graphml_file.stat().st_mtime
                geojson_mtime = geojson_file.stat().st_mtime
                
                if graphml_mtime > geojson_mtime:
                    logger.info("GraphML file is newer than GeoJSON, updating")
                    should_convert = True
            
            # Convert GraphML to GeoJSON if needed
            if should_convert:
                logger.info(f"Converting GraphML to GeoJSON: {graphml_path} -> {geojson_path}")
                result = self.network_constructor.build_network_geojson_from_graphml(
                    graphml_path=graphml_path,
                    output_path=geojson_path
                )
                
                if result.get("status") == "success":
                    logger.info(f"Successfully converted GraphML to GeoJSON with {result.get('total_features', 0)} features")
                    return {"converted": True, "total_features": result.get('total_features', 0)}
                else:
                    logger.error(f"Failed to convert GraphML to GeoJSON: {result.get('message', 'Unknown error')}")
                    return {"error": True, "message": result.get('message', 'Unknown error')}
            else:
                logger.debug("GeoJSON file is up to date")
                return None
                
        except Exception as e:
            logger.error(f"Error ensuring network GeoJSON exists: {e}")
            return {"error": True, "message": str(e)}