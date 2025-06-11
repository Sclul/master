"""Street processing functionality using OSMnx."""
import json
import logging
from typing import Dict, Any, Optional

import osmnx as ox # type: ignore
from shapely.geometry import shape # type: ignore
from shapely.geometry import mapping # type: ignore


logger = logging.getLogger(__name__)


class StreetProcessor:
    """Handles OSM street data processing and conversion."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize with configuration."""
        self.config = config
        self.osmnx_settings = config["osmnx_settings"]
    
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
            
            # Convert to GeoDataFrame and save
            gdf_edges = ox.graph_to_gdfs(processed_graph, nodes=False, edges=True)
            gdf_edges.to_file(streets_path, driver="GeoJSON")
            logger.info(f"Streets saved to {streets_path}")
            
            return {"status": "saved"}
            
        except Exception as e:
            logger.error(f"Error processing streets: {e}")
            return {"status": "error", "message": str(e)}
    
    def process_buildings_from_polygon(self, geojson: Dict[str, Any], buildings_path: str) -> Dict[str, str]:
        """
        Process buildings from polygon and save to file.
        
        Returns:
            Dict with status and optional message
        """
        try:
            polygon = shape(geojson["geometry"])
            
            # Get buildings from polygon
            # Ensure the 'building' tag is appropriate for your needs, or adjust as necessary
            gdf = ox.features_from_polygon(polygon, tags={"building": True})
            
            if gdf.empty:
                logger.info("No buildings found in the selected area.")
                return {"status": "no_buildings"}
            
            # Add representative point to each building
            # Ensure 'geometry' column exists and contains valid geometries
            if "geometry" in gdf.columns:
                def get_representative_point_coords(geom):
                    if geom and not geom.is_empty:
                        # Ensure the geometry is valid before getting the representative point
                        if not geom.is_valid:
                            geom = geom.buffer(0) # Attempt to fix invalid geometry
                        if geom and not geom.is_empty and geom.is_valid:
                            rp = geom.representative_point()
                            return {"coordinates": [rp.x, rp.y]}
                    return None
                gdf["representative_point"] = gdf["geometry"].apply(get_representative_point_coords)
            else:
                logger.warning("No 'geometry' column found in buildings GeoDataFrame. Skipping representative point calculation.")

            # Save to GeoJSON
            gdf.to_file(buildings_path, driver="GeoJSON")
            logger.info(f"Buildings saved to {buildings_path}")
            
            return {"status": "saved"}
            
        except Exception as e:
            logger.error(f"Error processing buildings: {e}")
            return {"status": "error", "message": str(e)}
    
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
