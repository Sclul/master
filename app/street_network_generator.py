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
            
            # Connect buildings to the network
            buildings_path = self.data_paths.get("buildings_path", "./data/buildings.geojson")
            if Path(buildings_path).exists():
                buildings_gdf = gpd.read_file(buildings_path)
                if not buildings_gdf.empty:
                    G, new_nodes, net_new_edges = self._connect_buildings_with_bisection(G, buildings_gdf)
                    node_count += new_nodes
                    edge_count += net_new_edges
            else:
                logger.warning(f"Buildings file not found at {buildings_path}, skipping building connections.")

            # Clean up None values before writing to GraphML
            self._clean_graph_for_graphml(G)

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
    
    def _connect_buildings_with_bisection(self, G: nx.Graph, buildings_gdf: gpd.GeoDataFrame) -> Tuple[nx.Graph, int, int]:
        """
        Connects buildings to the nearest street segment using bisection.
        For each building, it finds the closest street edge, creates a new node on that edge,
        and connects the building to this new node.

        Args:
            G: The NetworkX graph representing the street network.
            buildings_gdf: A GeoDataFrame containing building footprints.

        Returns:
            A tuple containing the updated graph, the number of new nodes added,
            and the net number of new edges added.
        """
        new_nodes_added = 0
        net_edges_added = 0
        
        street_edges = [(u, v, data) for u, v, data in G.edges(data=True) if data.get('edge_type') == 'street_segment']
        
        if not street_edges:
            logger.warning("No street segments found in the graph to connect buildings to.")
            return G, 0, 0

        edge_lines = [LineString([Point(G.nodes[u]['x'], G.nodes[u]['y']), Point(G.nodes[v]['x'], G.nodes[v]['y'])]) for u, v, _ in street_edges]
        edges_gs = gpd.GeoSeries(edge_lines)
        
        next_node_id = max(G.nodes) + 1 if G.nodes else 0

        for idx, building in buildings_gdf.iterrows():
            building_point = building.geometry.centroid
            
            # Find the nearest street segment
            nearest_edge_idx = edges_gs.distance(building_point).idxmin()
            u, v, edge_data = street_edges[nearest_edge_idx]
            closest_edge_line = edges_gs.iloc[nearest_edge_idx]

            # Create a new node on the segment
            new_point_on_line = closest_edge_line.interpolate(closest_edge_line.project(building_point))
            
            z_node_id = next_node_id
            G.add_node(z_node_id, x=new_point_on_line.x, y=new_point_on_line.y, node_type='street_connection', street_id=edge_data.get('street_id', 'unknown'))
            next_node_id += 1
            
            building_node_id = next_node_id
            G.add_node(building_node_id, x=building_point.x, y=building_point.y, node_type='building', osmid=building.get('osmid', 'unknown'))
            next_node_id += 1
            new_nodes_added += 2
            
            # Check if the edge still exists before removing it
            if G.has_edge(u, v):
                # Remove original edge and add new ones
                G.remove_edge(u, v)
                
                dist_u_z = Point(G.nodes[u]['x'], G.nodes[u]['y']).distance(new_point_on_line)
                dist_z_v = new_point_on_line.distance(Point(G.nodes[v]['x'], G.nodes[v]['y']))
                
                # Create copies of edge_data without the length key to avoid conflicts
                edge_data_copy = {k: v for k, v in edge_data.items() if k != 'length'}
                
                G.add_edge(u, z_node_id, length=dist_u_z, **edge_data_copy)
                G.add_edge(z_node_id, v, length=dist_z_v, **edge_data_copy)
            else:
                logger.warning(f"Edge {u}-{v} not found in graph, skipping building connection for building {idx}")
            
            dist_building_z = building_point.distance(new_point_on_line)
            G.add_edge(building_node_id, z_node_id, edge_type='building_connection', length=dist_building_z)
            
            # Net change in edges is +2 (1 removed, 3 added)
            net_edges_added += 2

        logger.info(f"Connected {len(buildings_gdf)} buildings, adding {new_nodes_added} nodes and a net of {net_edges_added} edges.")
        return G, new_nodes_added, net_edges_added

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
    
    def _clean_graph_for_graphml(self, G: nx.Graph) -> None:
        """
        Remove attributes with None values from nodes and edges for GraphML compliance.
        """
        # Clean node attributes
        for node, data in G.nodes(data=True):
            none_keys = [k for k, v in data.items() if v is None]
            for k in none_keys:
                data.pop(k)
        # Clean edge attributes
        for u, v, data in G.edges(data=True):
            none_keys = [k for k, v in data.items() if v is None]
            for k in none_keys:
                data.pop(k)
