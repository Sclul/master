"""Geospatial data handling functionality using OSMnx and GeoPandas."""
import json
import logging
from typing import Dict, Any, Optional, List, Union
from pathlib import Path

import osmnx as ox # type: ignore
import geopandas as gpd # type: ignore
import fiona # type: ignore
import pandas as pd
from shapely.geometry import shape, Point # type: ignore
from shapely.geometry import mapping # type: ignore
from building_clusterer import BuildingClusterer # type: ignore


logger = logging.getLogger(__name__)


class GeospatialHandler:
    """Handles OSM data extraction, coordinate transformations, and heat demand queries."""
    
    def __init__(self, config):
        """Initialize with configuration."""
        self.config = config
        self.osmnx_settings = config.osmnx_settings
        
        # Heat demand configuration
        heat_config = config.heat_demand
        self.gdb_path = heat_config.get("gdb_path", "/gdb/GDB.gdb")
        self.gdb_layer = heat_config.get("gdb_layer", "Raumwaermebedarf_ist")
        self.heat_demand_column = heat_config.get("heat_demand_column", "RW")
        
        # Coordinate system configuration
        crs_config = config.coordinate_system
        self.target_crs = crs_config.get("target_crs", "EPSG:5243")
        self.input_crs = crs_config.get("input_crs", "EPSG:4326")
        
        # Data directory path
        self.data_dir = Path(config.data_paths.get("data_dir", "data"))
        
        # Initialize building clusterer
        self.building_clusterer = BuildingClusterer(config)
        
        
    def clear_data_directory(self) -> Dict[str, Any]:
        """Clear all files in the data directory and pandapipes subdirectory."""
        try:
            if self.data_dir.exists():
                # Remove all files
                for item in self.data_dir.iterdir():
                    if item.is_file():
                        item.unlink()
                        logger.debug(f"Removed file: {item}")

                # Also clear pandapipes subdirectory
                pandapipes_result = self.clear_pandapipes_directory()
                logger.debug(f"Pandapipes clearing result: {pandapipes_result}")
                
                logger.info(f"Data directory cleared: {self.data_dir}")
                return {"status": "success", "message": f"Data directory {self.data_dir} cleared"}
            else:
                logger.info(f"Data directory does not exist: {self.data_dir}")
                return {"status": "info", "message": f"Data directory {self.data_dir} does not exist"}
        except Exception as e:
            logger.error(f"Error clearing data directory: {e}")
            return {"status": "error", "message": str(e)}

    def clear_pandapipes_directory(self) -> Dict[str, Any]:
        """Clear all files inside the configured pandapipes dump directory (e.g. data/pandapipes).

        This does NOT remove the directory itself, only its file contents. Subdirectories (if any)
        are skipped for safety.
        """
        try:
            dump_dir_cfg = self.config.pandapipes.get("output_paths", {}).get("pandapipes_dump_dir", "./data/pandapipes/")
            dump_path = Path(dump_dir_cfg)
            if dump_path.exists() and dump_path.is_dir():
                removed = 0
                for item in dump_path.iterdir():
                    if item.is_file():
                        item.unlink()
                        removed += 1
                        logger.debug(f"Removed pandapipes file: {item}")
                logger.info(f"Pandapipes directory cleared ({removed} files): {dump_path}")
                return {"status": "success", "message": f"Pandapipes directory {dump_path} cleared"}
            else:
                logger.info(f"Pandapipes directory does not exist: {dump_path}")
                return {"status": "info", "message": f"Pandapipes directory {dump_path} does not exist"}
        except Exception as e:
            logger.error(f"Error clearing pandapipes directory: {e}")
            return {"status": "error", "message": str(e)}
               
    
    def create_geojson_from_coordinates(self, coordinates: Union[Dict, List]) -> Dict[str, Any]:
        """Create GeoJSON feature from coordinates."""
        # Handle the specific format: {"coordinates": [[lng, lat], [lng, lat], ...]}
        if isinstance(coordinates, dict) and "coordinates" in coordinates:
            coord_list = coordinates["coordinates"]
        else:
            coord_list = coordinates
        
        # Ensure polygon is closed
        if len(coord_list) > 0 and coord_list[0] != coord_list[-1]:
            coord_list.append(coord_list[0])
        
        return {
            "type": "Feature",
            "geometry": {
                "type": "Polygon",
                "coordinates": [coord_list],  # Note: single array wrap for exterior ring
            },
            "properties": {},
        }
    
    def save_polygon(self, geojson: Dict[str, Any], polygon_path: str) -> None:
        """Save polygon GeoJSON to file."""
        with open(polygon_path, "w") as f:
            json.dump(geojson, f, indent=2)
        logger.debug(f"Polygon saved to {polygon_path}")
    
    def process_streets_from_polygon(self, geojson: Dict[str, Any], streets_path: str) -> Dict[str, str]:
        """Process streets from polygon and save to file."""
        try:
            polygon = shape(geojson["geometry"])
            
            # Get street network from polygon
            G = ox.graph_from_polygon(
                polygon, 
                network_type=self.osmnx_settings["network_type"], 
                truncate_by_edge=True
            )
            
            if len(G.edges) == 0:
                logger.error("No streets found in the selected area.")
                return {"status": "no_streets"}
            
            # Process the graph
            processed_graph = self._process_graph(G)
            
            # Convert to GeoDataFrame and transform to target CRS
            gdf_edges = ox.graph_to_gdfs(processed_graph, nodes=False, edges=True)
            
            # Transform to EPSG:5243
            gdf_edges = gdf_edges.to_crs(self.target_crs)
            
            # Filter to keep only essential columns: geometry, highway, name, length
            essential_columns = ['geometry']
            desired_columns = ['highway', 'name', 'length']
            
            # Add desired columns if they exist in the GeoDataFrame
            available_columns = essential_columns + [col for col in desired_columns if col in gdf_edges.columns]
            
            # Create filtered GeoDataFrame with only essential data
            gdf_filtered = gdf_edges[available_columns].copy()
            
            # Ensure 'name' column is a string, handling lists and None values
            if 'name' in gdf_filtered.columns:
                gdf_filtered['name'] = gdf_filtered['name'].apply(
                    lambda x: ', '.join(x) if isinstance(x, list) else x
                ).fillna('').astype(str)

            # Save filtered GeoJSON
            gdf_filtered.to_file(streets_path, driver="GeoJSON")
            logger.info(f"Streets saved to {streets_path} with columns: {available_columns} (CRS: {gdf_filtered.crs})")
            
            logger.info(f"Street extraction complete: {len(gdf_filtered):,} segments saved")
            
            return {"status": "saved"}
            
        except Exception as e:
            logger.error(f"Error processing streets: {e}")
            return {"status": "error", "message": str(e)}
    
    def _get_heat_demand_at_point(self, rep_point_coords: list, gdb_layer_crs: Any) -> Optional[float]:
        """Query GDB for heat demand value at a representative point."""
        try:
            # Create Point geometry from coordinates (already in EPSG:5243)
            point_geom = Point(rep_point_coords[0], rep_point_coords[1])
            point_gdf = gpd.GeoDataFrame([{'geometry': point_geom}], crs=self.target_crs)
            
            # Transform to GDB CRS if needed
            if gdb_layer_crs and str(point_gdf.crs).lower() != str(gdb_layer_crs).lower():
                point_gdf = point_gdf.to_crs(gdb_layer_crs)
            
            query_geom = point_gdf.geometry.iloc[0]
            
            # Query GDB layer
            intersecting_gdf = gpd.read_file(self.gdb_path, layer=self.gdb_layer, mask=query_geom)
            
            if not intersecting_gdf.empty:
                # Find features that actually contain the point
                containing_features = intersecting_gdf[intersecting_gdf.geometry.contains(query_geom)]
                if not containing_features.empty:
                    if self.heat_demand_column in containing_features.columns:
                        value = containing_features.iloc[0][self.heat_demand_column]
                        return float(value) if value is not None else None
                    else:
                        logger.warning(f"Column '{self.heat_demand_column}' not found in GDB layer")
            
            return None
            
        except Exception as e:
            logger.debug(f"Error querying heat demand for point {rep_point_coords}: {e}")
            return None
    
    def _add_heat_demand_to_buildings(self, gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
        """Add heat demand values to buildings GeoDataFrame."""
        try:
            # Import here to avoid circular import
            from utils.progress_tracker import progress_tracker
            
            # Start progress tracking for heat demand querying
            total_buildings = len(gdf)
            progress_tracker.start(f"Querying heat demand for buildings...", total_items=total_buildings)
            
            # Get GDB layer CRS
            gdb_layer_crs = None
            try:
                with fiona.open(self.gdb_path, layer=self.gdb_layer) as source:
                    gdb_layer_crs = source.crs
                logger.debug(f"GDB layer CRS: {gdb_layer_crs}")
            except Exception as e:
                logger.warning(f"Could not get GDB CRS: {e}")
            
            # Add heat demand values
            heat_demands = []
            successful_queries = 0
            
            for index, building in gdf.iterrows():
                rep_point_data = building.get('representative_point')
                
                if rep_point_data and isinstance(rep_point_data, dict) and 'coordinates' in rep_point_data:
                    coords = rep_point_data['coordinates']
                    heat_demand = self._get_heat_demand_at_point(coords, gdb_layer_crs)
                    heat_demands.append(heat_demand)
                    
                    if heat_demand is not None:
                        successful_queries += 1
                else:
                    heat_demands.append(None)
                
                # Update progress every 100 buildings or on last building
                current_building = len(heat_demands)
                if current_building % 100 == 0 or current_building == total_buildings:
                    progress_percent = int((current_building / total_buildings) * 100)
                    progress_tracker.update(progress_percent, 
                                          f"Queried heat demand: {current_building:,}/{total_buildings:,} buildings ({successful_queries:,} with data)",
                                          processed_items=current_building)
            
            # Complete progress tracking
            progress_tracker.complete(f"Heat demand query complete: {successful_queries:,}/{total_buildings:,} buildings with data")
            
            # Add heat demand column with consistent name
            gdf["heat_demand"] = heat_demands
            
            logger.info(f"Heat demand query results: {successful_queries}/{len(gdf)} buildings have heat demand data")
            
            return gdf
            
        except Exception as e:
            logger.error(f"Error adding heat demand to buildings: {e}")
            # Import here to avoid circular import
            from utils.progress_tracker import progress_tracker
            progress_tracker.error(f"Heat demand query failed: {str(e)}")
            # Return original GDF if heat demand processing fails
            return gdf
    
    def process_buildings_from_polygon(self, geojson: Dict[str, Any], buildings_path: str) -> Dict[str, str]:
        """Process buildings from polygon and save to file."""
        try:
            polygon = shape(geojson["geometry"])
            
            # Import here to avoid circular import
            from utils.progress_tracker import progress_tracker
            
            # Estimate building count based on area (rough approximation)
            area_km2 = polygon.area * 111 * 111  # Convert to rough km²
            estimated_buildings = int(area_km2 * 300)  # Rough estimate: 300 buildings per km²
            
            progress_tracker.start(f"Extracting buildings from {area_km2:.1f} km² area...", total_items=estimated_buildings)
            
            # Query buildings from OpenStreetMap
            logger.info("Querying OpenStreetMap for buildings...")
            
            # Get buildings from polygon with minimal tags
            gdf = ox.features_from_polygon(polygon, tags={"building": True})
            
            if gdf.empty:
                logger.info("No buildings found in the selected area.")
                return {"status": "no_buildings"}
            
            # Log building count found
            actual_building_count = len(gdf)
            progress_tracker.update_items_processed(actual_building_count, f"Processing {actual_building_count:,} buildings...")
            logger.info(f"Processing {actual_building_count:,} buildings...")
            
            # Keep only essential columns
            essential_columns = ['geometry', 'building']
            
            # Add address columns if they exist
            address_columns = [
                'addr:street', 'addr:housenumber', 'addr:postcode', 'addr:city'
            ]
            
            # Add building use columns if they exist
            use_columns = ['building:use', 'building:levels']
            
            # Combine all desired columns
            desired_columns = essential_columns + address_columns + use_columns
            
            # Filter to only keep columns that exist in the GeoDataFrame
            available_columns = [col for col in desired_columns if col in gdf.columns]
            
            # Create filtered GeoDataFrame with only essential data
            gdf_filtered = gdf[available_columns].copy()
            
            # Ensure input CRS is set (OSMnx typically returns data in EPSG:4326)
            if gdf_filtered.crs is None:
                gdf_filtered.set_crs(self.input_crs, inplace=True)
                logger.debug(f"Set input CRS to {self.input_crs} for buildings data")
            
            # Transform to target CRS (EPSG:5243)
            gdf_filtered = gdf_filtered.to_crs(self.target_crs)
            logger.info(f"Transformed buildings to {self.target_crs}")
            
            # Add representative point to each building (now in EPSG:5243)
            if "geometry" in gdf_filtered.columns:
                def get_representative_point_coords(geom):
                    if geom and not geom.is_empty:
                        # Ensure the geometry is valid before getting the representative point
                        if not geom.is_valid:
                            geom = geom.buffer(0)  # Attempt to fix invalid geometry
                        if geom and not geom.is_empty and geom.is_valid:
                            rp = geom.representative_point()
                            return {"coordinates": [rp.x, rp.y]}
                    return None
                gdf_filtered["representative_point"] = gdf_filtered["geometry"].apply(get_representative_point_coords)
            else:
                logger.warning("No 'geometry' column found in buildings GeoDataFrame.")
            
            # Add heat demand data automatically
            logger.info("Querying heat demand data for buildings...")
            
            # Import here to avoid circular import (only for heat demand progress)
            from utils.progress_tracker import progress_tracker
            
            gdf_filtered = self._add_heat_demand_to_buildings(gdf_filtered)

            # Apply building clustering if enabled in configuration
            clustering_config = self.config.config.get("building_clustering", {})
            clustering_stats = None
            if clustering_config.get("auto_apply", False):
                logger.info("Applying building clustering (auto-enabled)...")
                building_count_before = len(gdf_filtered)
                gdf_filtered = self.building_clusterer.cluster_buildings(gdf_filtered)
                building_count_after = len(gdf_filtered)
                clustering_stats = {
                    "before_count": building_count_before,
                    "after_count": building_count_after,
                    "merged_count": building_count_before - building_count_after
                }
            else:
                logger.info("Building clustering disabled in configuration")

            # Save to GeoJSON (will be in EPSG:5243)
            progress_tracker.update(95, "Saving building data...")
            gdf_filtered.to_file(buildings_path, driver="GeoJSON")
            logger.info(f"Buildings with heat demand data saved to {buildings_path} (CRS: {gdf_filtered.crs})")
            
            # Generate summary statistics
            heat_demand_stats = self._get_heat_demand_summary(gdf_filtered)
            
            # Complete the progress tracker at 100%
            progress_tracker.complete(f"Building extraction complete: {len(gdf_filtered):,} buildings processed")
            logger.info(f"Building extraction complete: {len(gdf_filtered):,} buildings processed")
            
            # Add clustering statistics if clustering was applied
            result_data = {
                "status": "saved", 
                "heat_demand_stats": heat_demand_stats
            }
            
            if clustering_stats:
                result_data["clustering_stats"] = clustering_stats
            
            return result_data
            
        except Exception as e:
            logger.error(f"Error processing buildings: {e}")
            return {"status": "error", "message": str(e)}
    
    def _get_heat_demand_summary(self, gdf: gpd.GeoDataFrame) -> Dict[str, Any]:
        """Generate summary statistics for heat demand data."""
        try:
            if "heat_demand" not in gdf.columns:
                return {"message": "No heat demand data available"}
            
            heat_data = gdf["heat_demand"].dropna()
            
            if len(heat_data) == 0:
                return {"message": "No valid heat demand values found"}
            
            stats = {
                "total_buildings": len(gdf),
                "buildings_with_data": len(heat_data),
                "coverage_percentage": round((len(heat_data) / len(gdf)) * 100, 1),
                "mean_heat_demand": round(heat_data.mean(), 2),
                "median_heat_demand": round(heat_data.median(), 2),
                "min_heat_demand": round(heat_data.min(), 2),
                "max_heat_demand": round(heat_data.max(), 2),
                "total_heat_demand": round(heat_data.sum(), 2)
            }
            
            return stats
            
        except Exception as e:
            logger.error(f"Error generating heat demand summary: {e}")
            return {"message": f"Error generating summary: {str(e)}"}
    
    def _process_graph(self, graph):
        """Process the OSM graph with projection and consolidation."""
        # Project the graph to a suitable CRS for distance calculations
        G_proj = ox.project_graph(graph)
        
        # Consolidate intersections
        G_consolidated = ox.simplification.consolidate_intersections(
            G_proj, 
            tolerance=self.osmnx_settings["consolidation_tolerance"], 
            rebuild_graph=True, 
            dead_ends=True
        )
        
        # Convert to undirected graph
        G_undirected = ox.convert.to_undirected(G_consolidated)
        
        return G_undirected
    
    def load_streets_data(self, streets_path: str) -> Optional[str]:
        """Load streets data from file for display."""
        try:
            with open(streets_path, "r") as f:
                data = json.load(f)
            return json.dumps(data, indent=2)
        except FileNotFoundError:
            return "No streets saved yet."
    
    def load_buildings_data(self, buildings_path: str) -> Optional[str]:
        """Load buildings data from file for display."""
        try:
            with open(buildings_path, "r") as f:
                data = json.load(f)
            return json.dumps(data, indent=2)
        except FileNotFoundError:
            return "No buildings saved yet."
