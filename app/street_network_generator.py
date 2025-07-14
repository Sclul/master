"""Street network generator for creating GraphML from street coordinates."""
import logging
from typing import Dict, Any, List, Tuple
from pathlib import Path
import geopandas as gpd  # type: ignore
import networkx as nx  # type: ignore
from shapely.geometry import LineString, Point  # type: ignore
import json

logger = logging.getLogger(__name__)


class StreetNetworkGenerator:
    """Generates GraphML network with nodes for every street line string coordinate."""
    
    def __init__(self, config):
        """Initialize with configuration."""
        self.config = config
        self.data_paths = config.data_paths
        
        logger.info("StreetNetworkGenerator initialized")
    
    def generate_street_network(self) -> Dict[str, Any]:
        """
        Generate GraphML network with nodes for every street coordinate.
        
        Returns:
            Dict with status and file information
        """
        try:
            # Load streets data
            streets_path = self.data_paths.get("streets_path", "./data/streets.geojson")
            
            if not Path(streets_path).exists():
                return {
                    "status": "error",
                    "message": f"Streets file not found: {streets_path}"
                }
            
            # Load streets GeoDataFrame
            streets_gdf = gpd.read_file(streets_path)
            
            if streets_gdf.empty:
                return {
                    "status": "error",
                    "message": "No streets found in the data"
                }
            
            logger.info(f"Loaded {len(streets_gdf)} street features")
            
            # Create network graph
            G = nx.Graph()
            
            # Extract coordinates and create nodes
            node_count = self._create_nodes_from_streets(G, streets_gdf)
            
            # Create edges between consecutive nodes in each street
            edge_count = self._create_edges_from_streets(G, streets_gdf)
            
            # Save as GraphML
            output_path = self.data_paths.get("network_graphml_path", "./data/heating_network.graphml")
            output_file = Path(output_path)
            output_file.parent.mkdir(parents=True, exist_ok=True)
            
            nx.write_graphml(G, output_path)
            
            logger.info(f"Street network GraphML saved to: {output_path}")
            logger.info(f"Network contains {node_count} nodes and {edge_count} edges")
            
            return {
                "status": "success",
                "message": f"Street network generated with {node_count} nodes and {edge_count} edges",
                "file_path": output_path,
                "total_nodes": node_count,
                "total_edges": edge_count
            }
            
        except Exception as e:
            logger.error(f"Error generating street network: {e}")
            return {
                "status": "error",
                "message": str(e)
            }
    
    def _create_nodes_from_streets(self, G: nx.Graph, streets_gdf: gpd.GeoDataFrame) -> int:
        """
        Create nodes for every coordinate in street line strings.
        
        Args:
            G: NetworkX graph to add nodes to
            streets_gdf: GeoDataFrame with street features
            
        Returns:
            Number of nodes created
        """
        node_id = 0
        
        for idx, street in streets_gdf.iterrows():
            geometry = street.geometry
            street_name = street.get('name', f'Street_{idx}')
            highway_type = street.get('highway', 'unknown')
            
            # Extract coordinates from LineString
            coords = self._extract_coordinates_from_geometry(geometry)
            
            # Create node for each coordinate
            for coord_idx, (x, y) in enumerate(coords):
                G.add_node(node_id, 
                          x=x, 
                          y=y, 
                          node_type='street_point',
                          street_id=str(idx),
                          street_name=street_name,
                          highway=highway_type,
                          coord_index=coord_idx,
                          total_coords=len(coords))
                node_id += 1
        
        return node_id
    
    def _create_edges_from_streets(self, G: nx.Graph, streets_gdf: gpd.GeoDataFrame) -> int:
        """
        Create edges between consecutive nodes in each street.
        
        Args:
            G: NetworkX graph to add edges to
            streets_gdf: GeoDataFrame with street features
            
        Returns:
            Number of edges created
        """
        edge_count = 0
        current_node_id = 0
        
        for idx, street in streets_gdf.iterrows():
            geometry = street.geometry
            street_name = street.get('name', f'Street_{idx}')
            highway_type = street.get('highway', 'unknown')
            
            # Extract coordinates from LineString
            coords = self._extract_coordinates_from_geometry(geometry)
            
            # Create edges between consecutive nodes
            for coord_idx in range(len(coords) - 1):
                source_node = current_node_id + coord_idx
                target_node = current_node_id + coord_idx + 1
                
                # Calculate distance between consecutive points
                point1 = Point(coords[coord_idx])
                point2 = Point(coords[coord_idx + 1])
                distance = point1.distance(point2)
                
                G.add_edge(source_node, target_node,
                          edge_type='street_segment',
                          street_id=str(idx),
                          street_name=street_name,
                          highway=highway_type,
                          length=distance,
                          segment_index=coord_idx)
                
                edge_count += 1
            
            current_node_id += len(coords)
        
        return edge_count
    
    def _extract_coordinates_from_geometry(self, geometry) -> List[Tuple[float, float]]:
        """
        Extract coordinates from LineString geometry.
        
        Args:
            geometry: Shapely LineString geometry
            
        Returns:
            List of (x, y) coordinate tuples
        """
        if isinstance(geometry, LineString):
            return list(geometry.coords)
        else:
            logger.warning(f"Unexpected geometry type: {type(geometry)}")
            return []
