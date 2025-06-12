"""Street processing functionality using OSMnx."""
import json
import logging
from typing import Dict, Any, Optional

import osmnx as ox # type: ignore
import geopandas as gpd # type: ignore
import fiona # type: ignore
from shapely.geometry import shape, Point # type: ignore
from shapely.geometry import mapping # type: ignore


logger = logging.getLogger(__name__)


class StreetProcessor:
    """Handles OSM street data processing and conversion."""
    
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
    
    def create_geojson_from_coordinates(self, coordinates: list) -> Dict[str, Any]:
        """Create GeoJSON feature from coordinates."""
        return {
            "type": "Feature",
            "geometry": {
                "type": "Polygon",
                "coordinates": [coordinates],
            },
            "properties": {},
        }
    
    def save_polygon(self, geojson: Dict[str, Any], polygon_path: str) -> None:
        """Save polygon GeoJSON to file."""
        with open(polygon_path, "w") as f:
            json.dump(geojson, f, indent=2)
        logger.debug(f"Polygon saved to {polygon_path}")
    
    def process_streets_from_polygon(self, geojson: Dict[str, Any], streets_path: str) -> Dict[str, str]:
        """
        Process streets from polygon and save to file.
        
        Returns:
            Dict with status and optional message
        """
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
            
            # Save to GeoJSON
            gdf_edges.to_file(streets_path, driver="GeoJSON")
            logger.info(f"Streets saved to {streets_path} (CRS: {gdf_edges.crs})")
            
            return {"status": "saved"}
            
        except Exception as e:
            logger.error(f"Error processing streets: {e}")
            return {"status": "error", "message": str(e)}
    
    def _get_heat_demand_at_point(self, rep_point_coords: list, gdb_layer_crs: Any) -> Optional[float]:
        """
        Query GDB for heat demand value at a representative point.
        rep_point_coords: [x, y] coordinates in EPSG:5243
        """
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
            
            # Add heat demand column
            gdf[self.heat_demand_column] = heat_demands
            
            logger.info(f"Heat demand query results: {successful_queries}/{len(gdf)} buildings have heat demand data")
            
            return gdf
            
        except Exception as e:
            logger.error(f"Error adding heat demand to buildings: {e}")
            # Return original GDF if heat demand processing fails
            return gdf
    
    def process_buildings_from_polygon(self, geojson: Dict[str, Any], buildings_path: str) -> Dict[str, str]:
        """
        Process buildings from polygon and save to file.
        Automatically adds heat demand data from GDB.
        
        Returns:
            Dict with status and optional message
        """
        try:
            polygon = shape(geojson["geometry"])
            
            # Get buildings from polygon with minimal tags
            gdf = ox.features_from_polygon(polygon, tags={"building": True})
            
            if gdf.empty:
                logger.info("No buildings found in the selected area.")
                return {"status": "no_buildings"}
            
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
                logger.warning("No 'geometry' column found in buildings GeoDataFrame. Skipping representative point calculation.")
            
            # Add heat demand data automatically
            logger.info("Querying heat demand data for buildings...")
            gdf_filtered = self._add_heat_demand_to_buildings(gdf_filtered)

            # Save to GeoJSON (will be in EPSG:5243)
            gdf_filtered.to_file(buildings_path, driver="GeoJSON")
            logger.info(f"Buildings with heat demand data saved to {buildings_path} (CRS: {gdf_filtered.crs})")
            
            # Generate summary statistics
            heat_demand_stats = self._get_heat_demand_summary(gdf_filtered)
            
            return {
                "status": "saved", 
                "heat_demand_stats": heat_demand_stats
            }
            
        except Exception as e:
            logger.error(f"Error processing buildings: {e}")
            return {"status": "error", "message": str(e)}
    
    def _get_heat_demand_summary(self, gdf: gpd.GeoDataFrame) -> Dict[str, Any]:
        """Generate summary statistics for heat demand data."""
        try:
            if self.heat_demand_column not in gdf.columns:
                return {"message": "No heat demand data available"}
            
            heat_data = gdf[self.heat_demand_column].dropna()
            
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
        """
        Load streets data from file for display.
        
        Returns:
            JSON string of the data or error message
        """
        try:
            with open(streets_path, "r") as f:
                data = json.load(f)
            return json.dumps(data, indent=2)
        except FileNotFoundError:
            return "No streets saved yet."
        except Exception as e:
            return f"Error reading {streets_path}: {e}"
    
    def load_buildings_data(self, buildings_path: str) -> Optional[str]:
        """
        Load buildings data from file for display.
        
        Returns:
            JSON string of the data or error message
        """
        try:
            with open(buildings_path, "r") as f:
                data = json.load(f)
            return json.dumps(data, indent=2)
        except FileNotFoundError:
            return "No buildings saved yet."
        except Exception as e:
            return f"Error reading {buildings_path}: {e}"
