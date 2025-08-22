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
from heat_source_handler import HeatSourceHandler

logger = logging.getLogger(__name__)


class MapCallbacks(BaseCallback):
    """Handles callbacks related to map interactions and layer management."""
    
    def __init__(self, app, config):
        """Initialize with Dash app and configuration."""
        super().__init__(app, config)
        self.network_constructor = NetworkConstructor(config)
        self.heat_source_handler = HeatSourceHandler(config)
    
    def _register_callbacks(self):
        """Register map-related callbacks."""
        
        @self.app.callback(
            [Output("data-layers", "children"), Output("network-status", "children", allow_duplicate=True)],
            [Input("layer-toggles", "value"), Input("network-data", "data"), Input("filtered-buildings", "data"), Input("heat-sources-data", "data")],
        )
        def update_map_layers(selected_layers, network_data, filtered_buildings_data, heat_sources_data):
            """Update map layers based on toggle states."""
            if selected_layers is None:
                selected_layers = []
            
            show_streets = "streets" in selected_layers
            show_buildings = "buildings" in selected_layers
            show_filtered = "filtered" in selected_layers
            show_network = "network" in selected_layers
            show_filtered_network = "filtered_network" in selected_layers
            show_heat_sources = "heat_sources" in selected_layers
            show_pressure = "pressure" in selected_layers
            
            logger.info(f"Updating layers: streets={show_streets}, buildings={show_buildings}, filtered={show_filtered}, network={show_network}, filtered_network={show_filtered_network}")
            
            network_status = ""
            
            # If network layer is requested, ensure GeoJSON exists
            if show_network:
                conversion_result = self._ensure_network_geojson_exists()
                if conversion_result:
                    if conversion_result.get("converted"):
                        network_status = html.Div([
                            html.P("Network converted from GraphML to GeoJSON", className="success-message"),
                            html.P(f"Features: {conversion_result.get('total_features', 0)}", className="info-message")
                        ])
                    elif conversion_result.get("error"):
                        network_status = html.Div(
                            f"Network conversion error: {conversion_result.get('message')}", 
                            className="error-message"
                        )
            
            # If filtered network layer is requested, ensure GeoJSON exists
            if show_filtered_network:
                conversion_result = self._ensure_filtered_network_geojson_exists()
                if conversion_result:
                    if conversion_result.get("converted"):
                        network_status = html.Div([
                            html.P("Filtered Network converted from GraphML to GeoJSON", className="success-message"),
                            html.P(f"Features: {conversion_result.get('total_features', 0)}", className="info-message")
                        ])
                    elif conversion_result.get("error"):
                        network_status = html.Div(
                            f"Filtered Network conversion error: {conversion_result.get('message')}", 
                            className="error-message"
                        )
            
            layers = self._build_data_layers(show_streets, show_buildings, show_filtered, show_network, show_filtered_network, show_heat_sources, show_pressure)
            return layers, network_status

        @self.app.callback(
            Output("layer-toggles", "value", allow_duplicate=True),
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
        def auto_enable_network_layers(network_data, current_selected_layers):
            """Auto-enable network layers when network is generated or optimized."""
            if not network_data or not isinstance(network_data, dict):
                return no_update
            
            updated_layers = (current_selected_layers or []).copy()
            
            # Check if network was just generated successfully
            if network_data.get("status") == "success":
                # If network has optimization stats, enable filtered network layer
                if (network_data.get("optimization_stats") and
                    network_data.get("optimization_stats", {}).get("status") == "success"):
                    if "filtered_network" not in updated_layers:
                        updated_layers.append("filtered_network")
                        logger.info("Auto-enabling filtered network layer after successful network optimization")
                        return updated_layers
                else:
                    # Otherwise, enable regular network layer
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
            Output("layer-toggles", "value", allow_duplicate=True),
            Input("heat-sources-data", "data"),
            State("layer-toggles", "value"),
            prevent_initial_call=True
        )
        def auto_enable_heat_sources_layer(heat_sources_data, current_selected_layers):
            """Auto-enable heat sources layer when a heat source is added."""
            if not heat_sources_data or not isinstance(heat_sources_data, dict):
                return no_update
            
            # Auto-enable when a heat source is added (indicated by "updated" or "timestamp")
            if heat_sources_data.get("updated") or heat_sources_data.get("timestamp"):
                updated_layers = (current_selected_layers or []).copy()
                if "heat_sources" not in updated_layers:
                    updated_layers.append("heat_sources")
                    logger.info("Auto-enabling heat sources layer after heat source creation")
                    return updated_layers
            
            return no_update

        @self.app.callback(
            Output("map-zoom-info", "children"),
            Input("map", "zoom")
        )
        def update_zoom_info(zoom):
            """Display current zoom level."""
            return f"Zoom: {zoom}" if zoom else "Zoom: Unknown"
    
    def _build_data_layers(self, show_streets, show_buildings, show_filtered, show_network=False, show_filtered_network=False, show_heat_sources=False, show_pressure=False):
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
        
        if show_filtered_network:
            filtered_network_layer = self._create_filtered_network_layer()
            if filtered_network_layer is not None:
                layers.append(filtered_network_layer)
                logger.info("Added filtered heating network layer to map")
        
        if show_heat_sources:
            heat_sources_layer = self._create_heat_sources_layer()
            if heat_sources_layer is not None:
                layers.append(heat_sources_layer)
                logger.info("Added heat sources layer to map")
        if show_pressure:
            pressure_layer = self._create_pressure_layer()
            if pressure_layer is not None:
                layers.append(pressure_layer)
                logger.info("Added pressure layer to map")
        
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
        regular_network_path = self.data_paths.get("network_path", "./data/heating_network.geojson")
        
        return self._create_layer_from_file(
            regular_network_path,
            "heating-network-layer",
            {"color": "orange", "weight": 2, "opacity": 0.8}
        )
    
    def _create_filtered_network_layer(self):
        """Create filtered heating network layer from saved data."""
        filtered_network_path = self.data_paths.get("filtered_network_path", "./data/filtered_heating_network.geojson")
        
        return self._create_layer_from_file(
            filtered_network_path,
            "filtered-heating-network-layer",
            {"color": "red", "weight": 3, "opacity": 0.9}  # Different style for optimized network
        )
    
    def _create_heat_sources_layer(self):
        """Create heat sources layer from saved data."""
        heat_sources_path = self.data_paths.get("heat_sources_path", "./data/heat_sources.geojson")
        
        # Check if file exists and has valid content
        try:
            if not Path(heat_sources_path).exists():
                logger.debug(f"Heat sources file does not exist: {heat_sources_path}")
                return None
            
            # Check if file has content
            file_size = Path(heat_sources_path).stat().st_size
            if file_size == 0:
                logger.debug(f"Heat sources file is empty: {heat_sources_path}")
                return None
            
            # Try to read and check if it has features
            gdf = gpd.read_file(heat_sources_path)
            if gdf.empty:
                logger.debug(f"Heat sources file has no features: {heat_sources_path}")
                return None
            
            logger.info(f"Creating heat sources layer with {len(gdf)} heat sources")
            
        except Exception as e:
            logger.debug(f"Cannot read heat sources file: {heat_sources_path}, error: {e}")
            return None
        
        return self._create_layer_from_file(
            heat_sources_path,
            "heat-sources-layer",
            {"color": "orange", "fillColor": "orange", "radius": 8, "weight": 2, "fillOpacity": 0.8}
        )

    def _create_pressure_layer(self):
        """Create a pipe pressure visualization layer using per-pipe Polylines.

        Avoids passing Python functions (not JSON serializable) by precomputing
        colors client-side. Adds a LayerGroup with colored polylines. Each
        polyline includes a title attribute (Leaflet tooltip on hover) with
        pressure details.
        """
        try:
            pipe_results_path = "./data/pandapipes/pipe_results.geojson"
            if not Path(pipe_results_path).exists():
                logger.debug("Pressure layer skipped: pipe_results.geojson not found")
                return None
            gdf = gpd.read_file(pipe_results_path)
            if gdf.empty or "p_avg_bar" not in gdf.columns:
                logger.debug("Pressure layer skipped: missing p_avg_bar")
                return None
            if gdf.crs and str(gdf.crs) != "EPSG:4326":
                gdf = gdf.to_crs("EPSG:4326")

            p_min = float(gdf["p_avg_bar"].min())
            p_max = float(gdf["p_avg_bar"].max())
            span = (p_max - p_min) if p_max > p_min else 1.0

            def color_for(p):
                try:
                    norm = (float(p) - p_min) / span
                except Exception:
                    norm = 0.0
                norm = max(0.0, min(1.0, norm))
                r = int(255 * norm)
                b = int(255 * (1 - norm))
                g = 30
                return f"rgb({r},{g},{b})"

            polylines = []
            for idx, row in gdf.iterrows():
                geom = row["geometry"]
                if geom is None:
                    continue
                try:
                    coords = list(geom.coords)
                except Exception:
                    continue
                # Leaflet expects (lat, lon)
                positions = [(y, x) for x, y in coords]
                p_avg = row.get("p_avg_bar")
                def _fmt(val):
                    return f"{val:.3f}" if isinstance(val, (int, float)) else "?"
                p_from_val = row.get('p_from_bar')
                p_to_val = row.get('p_to_bar')
                if isinstance(p_avg, (int, float)):
                    tooltip_text = (
                        f"p_avg={_fmt(p_avg)} bar\n"
                        f"p_from={_fmt(p_from_val)} bar, p_to={_fmt(p_to_val)} bar"
                    )
                else:
                    tooltip_text = "p_avg=?"
                polylines.append(dl.Polyline(
                    id=f"pressure-poly-{idx}",
                    positions=positions,
                    color=color_for(p_avg),
                    weight=4,
                    opacity=0.85,
                    children=[dl.Tooltip(tooltip_text)]
                ))

            if not polylines:
                logger.debug("Pressure layer skipped: no valid polylines generated")
                return None
            logger.info(f"Pressure layer created with {len(polylines)} polylines (p_min={p_min:.3f}, p_max={p_max:.3f} bar)")
            return dl.LayerGroup(id="pressure-layer", children=polylines)
        except Exception as e:
            logger.error(f"Error creating pressure layer: {e}")
            return None
    
    def _ensure_network_geojson_exists(self):
        """Ensure network GeoJSON file exists by converting from GraphML if needed."""
        try:
            # Check for filtered network first
            filtered_graphml_path = self.data_paths.get("filtered_network_graphml_path", "./data/filtered_heating_network.graphml")
            filtered_geojson_path = self.data_paths.get("filtered_network_path", "./data/filtered_heating_network.geojson")
            
            # If filtered network exists, use it
            if Path(filtered_graphml_path).exists():
                graphml_path = filtered_graphml_path
                geojson_path = filtered_geojson_path
                logger.info("Using filtered network for visualization")
            else:
                # Fall back to regular network
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
    
    def _ensure_filtered_network_geojson_exists(self):
        """Ensure filtered network GeoJSON file exists by converting from GraphML if needed."""
        try:
            filtered_graphml_path = self.data_paths.get("filtered_network_graphml_path", "./data/filtered_heating_network.graphml")
            filtered_geojson_path = self.data_paths.get("filtered_network_path", "./data/filtered_heating_network.geojson")
            
            graphml_file = Path(filtered_graphml_path)
            geojson_file = Path(filtered_geojson_path)
            
            # Check if GraphML exists
            if not graphml_file.exists():
                logger.warning(f"Filtered GraphML file not found: {filtered_graphml_path}")
                return {"error": True, "message": f"Filtered GraphML file not found: {filtered_graphml_path}"}
            
            # Check if GeoJSON needs to be created or updated
            should_convert = False
            
            if not geojson_file.exists():
                logger.info("Filtered GeoJSON file doesn't exist, converting from GraphML")
                should_convert = True
            else:
                # Check if GraphML is newer than GeoJSON
                graphml_mtime = graphml_file.stat().st_mtime
                geojson_mtime = geojson_file.stat().st_mtime
                
                if graphml_mtime > geojson_mtime:
                    logger.info("Filtered GraphML file is newer than GeoJSON, updating")
                    should_convert = True
            
            # Convert GraphML to GeoJSON if needed
            if should_convert:
                logger.info(f"Converting filtered GraphML to GeoJSON: {filtered_graphml_path} -> {filtered_geojson_path}")
                result = self.network_constructor.build_network_geojson_from_graphml(
                    graphml_path=filtered_graphml_path,
                    output_path=filtered_geojson_path
                )
                
                if result.get("status") == "success":
                    logger.info(f"Successfully converted filtered GraphML to GeoJSON with {result.get('total_features', 0)} features")
                    return {"converted": True, "total_features": result.get('total_features', 0)}
                else:
                    logger.error(f"Failed to convert filtered GraphML to GeoJSON: {result.get('message', 'Unknown error')}")
                    return {"error": True, "message": result.get('message', 'Unknown error')}
            else:
                logger.debug("Filtered GeoJSON file is up to date")
                return None
                
        except Exception as e:
            logger.error(f"Error ensuring filtered network GeoJSON exists: {e}")
            return {"error": True, "message": str(e)}