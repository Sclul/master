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
from utils.status_messages import status_message

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
            show_supply_temp = "supply_temp" in selected_layers
            show_supply_pressure = "supply_pressure" in selected_layers
            show_supply_mass_flow = "supply_mass_flow" in selected_layers
            show_return_temp = "return_temp" in selected_layers
            show_return_pressure = "return_pressure" in selected_layers
            show_return_mass_flow = "return_mass_flow" in selected_layers
            
            logger.info(f"Updating layers: streets={show_streets}, buildings={show_buildings}, filtered={show_filtered}, network={show_network}, filtered_network={show_filtered_network}")
            
            network_status = no_update  # Don't clear status by default
            
            # If network layer is requested, ensure GeoJSON exists
            if show_network:
                conversion_result = self._ensure_network_geojson_exists()
                # Only show status if there's an error (don't show success message for routine conversion)
                if conversion_result and conversion_result.get("error"):
                    network_status = status_message.error(
                        "Network conversion error",
                        details=conversion_result.get('message')
                    )
            
            # If filtered network layer is requested, ensure GeoJSON exists
            if show_filtered_network:
                conversion_result = self._ensure_filtered_network_geojson_exists()
                # Only show status if there's an error (don't show success message for routine conversion)
                if conversion_result and conversion_result.get("error"):
                    network_status = status_message.error(
                        "Filtered Network conversion error",
                        details=conversion_result.get('message')
                    )
            
            layers = self._build_data_layers(
                show_streets, show_buildings, show_filtered, show_network, show_filtered_network, 
                show_heat_sources,
                show_supply_temp, show_supply_pressure, show_supply_mass_flow,
                show_return_temp, show_return_pressure, show_return_mass_flow
            )
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
            Input("buildings-processed", "data"),
            State("layer-toggles", "value"),
            prevent_initial_call=True
        )
        def auto_enable_buildings_layer(buildings_data, current_selected_layers):
            """Auto-enable buildings layer when buildings are successfully processed."""
            if not buildings_data or not isinstance(buildings_data, dict):
                return no_update
            
            # Only auto-enable if buildings were just processed successfully
            if buildings_data.get("status") == "processed":
                updated_layers = (current_selected_layers or []).copy()
                if "buildings" not in updated_layers:
                    updated_layers.append("buildings")
                    logger.info("Auto-enabling buildings layer after successful building extraction")
                    return updated_layers
            
            return no_update

        @self.app.callback(
            Output("layer-toggles", "value", allow_duplicate=True),
            Input("network-data", "data"),
            State("layer-toggles", "value"),
            prevent_initial_call=True
        )
        def manage_network_layers(network_data, current_selected_layers):
            """Auto-enable network layers and disable streets, buildings, and filtered buildings when network is generated or optimized."""
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
                    # Otherwise, enable regular network layer and disable streets, buildings, and filtered buildings
                    changes_made = False
                    if "network" not in updated_layers:
                        updated_layers.append("network")
                        logger.info("Auto-enabling network layer after successful network generation")
                        changes_made = True
                    if "streets" in updated_layers:
                        updated_layers.remove("streets")
                        logger.info("Auto-disabling streets layer after successful network generation")
                        changes_made = True
                    if "buildings" in updated_layers:
                        updated_layers.remove("buildings")
                        logger.info("Auto-disabling buildings layer after successful network generation")
                        changes_made = True
                    if "filtered" in updated_layers:
                        updated_layers.remove("filtered")
                        logger.info("Auto-disabling filtered buildings layer after successful network generation")
                        changes_made = True
                    if changes_made:
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
            if heat_sources_data is None:
                return no_update
            
            # Auto-enable when heat sources exist (list is not empty)
            # heat_sources_data is a list of heat source dicts
            if isinstance(heat_sources_data, list) and len(heat_sources_data) > 0:
                updated_layers = (current_selected_layers or []).copy()
                if "heat_sources" not in updated_layers:
                    updated_layers.append("heat_sources")
                    logger.info("Auto-enabling heat sources layer after heat source creation")
                    return updated_layers
            
            return no_update

        @self.app.callback(
            Output("layer-toggles", "value", allow_duplicate=True),
            Input("sim-run-state-store", "data"),
            State("layer-toggles", "value"),
            prevent_initial_call=True
        )
        def switch_to_supply_temp_after_pipeflow(pipeflow_state, current_selected_layers):
            """Switch to supply temperature layer when pipeflow completes successfully."""
            if not pipeflow_state or not isinstance(pipeflow_state, dict):
                return no_update
            
            # Check if pipeflow just completed successfully
            if pipeflow_state.get("completed") and pipeflow_state.get("converged"):
                updated_layers = (current_selected_layers or []).copy()
                
                # Remove network layers
                if "network" in updated_layers:
                    updated_layers.remove("network")
                if "filtered_network" in updated_layers:
                    updated_layers.remove("filtered_network")
                
                # Enable only supply_temp if not already enabled
                if "supply_temp" not in updated_layers:
                    updated_layers.append("supply_temp")
                
                logger.info("Auto-switching to supply temperature layer after successful pipeflow")
                return updated_layers
            
            return no_update

        @self.app.callback(
            Output("map-zoom-info", "children"),
            Input("map", "zoom")
        )
        def update_zoom_info(zoom):
            """Display current zoom level."""
            return f"Zoom: {zoom}" if zoom else "Zoom: Unknown"
    
    def _build_data_layers(self, show_streets, show_buildings, show_filtered, show_network=False, show_filtered_network=False, show_heat_sources=False,
                          show_supply_temp=False, show_supply_pressure=False, show_supply_mass_flow=False,
                          show_return_temp=False, show_return_pressure=False, show_return_mass_flow=False):
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
        
        # Six new circuit-specific layers
        if show_supply_temp:
            supply_temp_layer = self._create_circuit_layer("supply_temp", "Supply Temperature")
            if supply_temp_layer is not None:
                layers.append(supply_temp_layer)
                logger.info("Added supply temperature layer to map")
        
        if show_supply_pressure:
            supply_pressure_layer = self._create_circuit_layer("supply_pressure", "Supply Pressure")
            if supply_pressure_layer is not None:
                layers.append(supply_pressure_layer)
                logger.info("Added supply pressure layer to map")
        
        if show_supply_mass_flow:
            supply_mass_flow_layer = self._create_circuit_layer("supply_mass_flow", "Supply Mass Flow")
            if supply_mass_flow_layer is not None:
                layers.append(supply_mass_flow_layer)
                logger.info("Added supply mass flow layer to map")
        
        if show_return_temp:
            return_temp_layer = self._create_circuit_layer("return_temp", "Return Temperature")
            if return_temp_layer is not None:
                layers.append(return_temp_layer)
                logger.info("Added return temperature layer to map")
        
        if show_return_pressure:
            return_pressure_layer = self._create_circuit_layer("return_pressure", "Return Pressure")
            if return_pressure_layer is not None:
                layers.append(return_pressure_layer)
                logger.info("Added return pressure layer to map")
        
        if show_return_mass_flow:
            return_mass_flow_layer = self._create_circuit_layer("return_mass_flow", "Return Mass Flow")
            if return_mass_flow_layer is not None:
                layers.append(return_mass_flow_layer)
                logger.info("Added return mass flow layer to map")
        
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
        """Create buildings layer from saved data with cluster highlighting on hover."""
        try:
            file_path = self.data_paths["buildings_path"]
            
            # Read and reproject data
            gdf = gpd.read_file(file_path)
            
            if gdf.crs and str(gdf.crs) != "EPSG:4326":
                gdf = gdf.to_crs("EPSG:4326")
                logger.debug(f"Reprojected buildings from {gdf.crs} to EPSG:4326")
            
            # Convert to GeoJSON dict
            geojson_data = json.loads(gdf.to_json())
            
            logger.info(f"Creating buildings layer with {len(geojson_data.get('features', []))} features")
            
            # Create layer with hover style to highlight clusters
            return dl.GeoJSON(
                data=geojson_data,
                id="buildings-layer",
                options={"style": {"color": "red", "weight": 1, "fillOpacity": 0.3}},
                # Highlight on hover - makes cluster boundaries more visible
                hoverStyle={"weight": 3, "color": "#DC143C", "fillOpacity": 0.7}
            )
                
        except FileNotFoundError:
            logger.debug(f"buildings-layer file not found: {file_path}")
            return None
        except Exception as e:
            logger.error(f"Error creating buildings-layer: {e}")
            return None
    
    def _create_filtered_buildings_layer(self):
        """Create filtered buildings layer from saved data with cluster highlighting on hover."""
        try:
            file_path = self.data_paths["filtered_buildings_path"]
            
            # Read and reproject data
            gdf = gpd.read_file(file_path)
            
            if gdf.crs and str(gdf.crs) != "EPSG:4326":
                gdf = gdf.to_crs("EPSG:4326")
                logger.debug(f"Reprojected filtered buildings from {gdf.crs} to EPSG:4326")
            
            # Convert to GeoJSON dict
            geojson_data = json.loads(gdf.to_json())
            
            logger.info(f"Creating filtered buildings layer with {len(geojson_data.get('features', []))} features")
            
            # Create layer with hover style to highlight clusters
            return dl.GeoJSON(
                data=geojson_data,
                id="filtered-buildings-layer",
                options={"style": {"color": "green", "weight": 2, "fillOpacity": 0.5}},
                # Highlight on hover - makes cluster boundaries more visible
                hoverStyle={"weight": 4, "color": "#00FF00", "fillOpacity": 0.7}
            )
                
        except FileNotFoundError:
            logger.debug(f"filtered-buildings-layer file not found: {file_path}")
            return None
        except Exception as e:
            logger.error(f"Error creating filtered-buildings-layer: {e}")
            return None
    
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
    
    def _create_circuit_layer(self, layer_type, layer_name):
        """Create a circuit-specific visualization layer (supply/return temp, pressure, mass flow).
        
        Args:
            layer_type: One of "supply_temp", "supply_pressure", "supply_mass_flow", 
                       "return_temp", "return_pressure", "return_mass_flow"
            layer_name: Display name for logging
        
        Returns:
            dl.LayerGroup with colored polylines or None if data unavailable
        """
        try:
            # Determine circuit and metric from layer_type (e.g., "supply_temp", "return_pressure")
            parts = layer_type.split("_", 1)
            if len(parts) != 2:
                logger.warning(f"Invalid layer type format: {layer_type}")
                return None
            
            circuit_name, metric_name = parts  # e.g., ("supply", "temp"), ("return", "pressure")
            
            # Map to consolidated circuit GeoJSON file
            circuit_path_key = f"{circuit_name}_circuit_geojson"
            default_path = f"./data/pandapipes/{circuit_name}_circuit.geojson"
            layer_path = self.data_paths.get("pandapipes", {}).get("output_paths", {}).get(circuit_path_key, default_path)
            
            if not Path(layer_path).exists():
                logger.debug(f"{layer_name} layer skipped: {layer_path} not found")
                return None
            
            gdf = gpd.read_file(layer_path)
            if gdf.empty:
                logger.debug(f"{layer_name} layer skipped: no features")
                return None
            
            # Map metric name to column and unit
            metric_mapping = {
                "temp": ("t_avg_k", "°C"),
                "pressure": ("p_avg_bar", "bar"),
                "mass_flow": ("mdot_kg_per_s", "kg/s")
            }
            
            if metric_name not in metric_mapping:
                logger.warning(f"Unknown metric name: {metric_name}")
                return None
            
            metric_col, unit = metric_mapping[metric_name]
            
            if metric_col not in gdf.columns:
                logger.debug(f"{layer_name} layer skipped: missing {metric_col} column")
                return None
            
            # Get metric range from consolidated file's metadata columns
            metric_min_col = f"{metric_col}_min"
            metric_max_col = f"{metric_col}_max"
            
            if metric_min_col in gdf.columns and metric_max_col in gdf.columns:
                metric_min = gdf[metric_min_col].iloc[0]
                metric_max = gdf[metric_max_col].iloc[0]
            else:
                # Fallback to calculating from data
                metric_min = gdf[metric_col].min()
                metric_max = gdf[metric_col].max()
            
            # Convert temperature from Kelvin to Celsius for display
            if metric_name == "temp":
                metric_min = metric_min - 273.15
                metric_max = metric_max - 273.15
            
            span = (metric_max - metric_min) if metric_max > metric_min else 1.0
            
            # Convert to EPSG:4326 for Leaflet
            if gdf.crs and str(gdf.crs) != "EPSG:4326":
                gdf = gdf.to_crs("EPSG:4326")
            
            def color_for(value):
                """Generate color based on metric value."""
                try:
                    norm = (float(value) - metric_min) / span
                except Exception:
                    norm = 0.5
                norm = max(0.0, min(1.0, norm))
                
                # Color gradient: blue (low) -> green (mid) -> yellow -> red (high)
                if norm < 0.5:
                    # Blue to green
                    r = 0
                    g = int(255 * (norm * 2))
                    b = int(255 * (1 - norm * 2))
                else:
                    # Green to red
                    r = int(255 * ((norm - 0.5) * 2))
                    g = int(255 * (1 - (norm - 0.5) * 2))
                    b = 0
                
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
                
                metric_value = row.get(metric_col)
                
                # Convert temperature from Kelvin to Celsius for display
                if metric_name == "temp" and isinstance(metric_value, (int, float)):
                    metric_value = metric_value - 273.15
                
                def _fmt(val):
                    return f"{val:.2f}" if isinstance(val, (int, float)) else "?"
                
                if isinstance(metric_value, (int, float)):
                    tooltip_text = f"{layer_name}: {_fmt(metric_value)} {unit}"
                else:
                    tooltip_text = f"{layer_name}: N/A"
                
                polylines.append(dl.Polyline(
                    id=f"{layer_type}-poly-{idx}",
                    positions=positions,
                    color=color_for(metric_value),
                    weight=3,
                    opacity=0.8,
                    children=[dl.Tooltip(tooltip_text)]
                ))
            
            if not polylines:
                logger.debug(f"{layer_name} layer skipped: no valid polylines generated")
                return None
            
            logger.info(f"{layer_name} layer created with {len(polylines)} polylines ({metric_col}: {metric_min:.2f}-{metric_max:.2f} {unit})")
            return dl.LayerGroup(id=f"{layer_type}-layer", children=polylines)
        except Exception as e:
            logger.error(f"Error creating {layer_name} layer: {e}")
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