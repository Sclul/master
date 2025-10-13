"""Network constructor for converting GraphML to GeoJSON."""
import logging
from typing import Dict, Any, Optional
from pathlib import Path
import geopandas as gpd  # type: ignore
from shapely.geometry import LineString  # type: ignore
from shapely.wkt import loads as wkt_loads  # type: ignore
import networkx as nx  # type: ignore

logger = logging.getLogger(__name__)


class NetworkConstructor:
    """Handles network construction from GraphML to GeoJSON."""
    
    def __init__(self, config):
        """Initialize with configuration."""
        self.config = config
        self.data_paths = config.data_paths
        
        logger.info("NetworkConstructor initialized")
    
    def build_network_geojson_from_graphml(self, graphml_path: Optional[str] = None, 
                                         output_path: Optional[str] = None) -> Dict[str, Any]:
        """
        Build network GeoJSON from GraphML file.
        
        Args:
            graphml_path: Path to GraphML file (uses config default if None)
            output_path: Output path for GeoJSON (uses config default if None)
            
        Returns:
            Dict with status and file path information
        """
        if graphml_path is None:
            graphml_path = self.data_paths.get("network_graphml_path", "./data/heating_network.graphml")
        if output_path is None:
            output_path = self.data_paths.get("network_path", "./data/heating_network.geojson")

        if not Path(graphml_path).exists():
            return {
                "status": "error",
                "message": f"GraphML file not found: {graphml_path}"
            }

        try:
            G = nx.read_graphml(graphml_path)
        except (OSError, nx.NetworkXError) as exc:
            logger.error(f"Unable to read GraphML from {graphml_path}: {exc}")
            return {
                "status": "error",
                "message": f"Could not read GraphML: {exc}"
            }

        if G.number_of_nodes() == 0:
            return {
                "status": "error",
                "message": "No nodes found in GraphML file"
            }

        logger.info(f"Loaded GraphML with {G.number_of_nodes()} nodes and {G.number_of_edges()} edges")

        try:
            network_gdf = self._convert_graphml_to_geodataframe(G)
        except Exception as exc:
            logger.error(f"Failed to convert GraphML to GeoDataFrame: {exc}")
            return {
                "status": "error",
                "message": f"Could not convert GraphML: {exc}"
            }

        if network_gdf.empty:
            return {
                "status": "error",
                "message": "No features could be generated from GraphML"
            }

        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        try:
            network_gdf.to_file(output_path, driver="GeoJSON")
        except Exception as exc:
            logger.error(f"Failed to write network GeoJSON to {output_path}: {exc}")
            return {
                "status": "error",
                "message": f"Could not write GeoJSON: {exc}"
            }

        logger.info(f"Network GeoJSON saved to: {output_path}")
        logger.info(f"Network contains {len(network_gdf)} edge features (nodes excluded)")

        return {
            "status": "success",
            "message": f"Network GeoJSON generated with {len(network_gdf)} edge features (nodes excluded)",
            "file_path": output_path,
            "total_features": len(network_gdf),
            "node_count": G.number_of_nodes(),
            "edge_count": G.number_of_edges()
        }
    
    def _convert_graphml_to_geodataframe(self, G: nx.DiGraph) -> gpd.GeoDataFrame:
        """
        Convert NetworkX graph to GeoDataFrame with edge (line) features only.
        
        Args:
            G: NetworkX graph loaded from GraphML
            
        Returns:
            GeoDataFrame containing only edge features (no nodes)
        """
        features = []
        
        # Add edge features (streets and connections)
        for source, target, edge_data in G.edges(data=True):
            edge_type = edge_data.get('edge_type', 'unknown')
            
            # Get source and target node coordinates
            source_data = G.nodes[source]
            target_data = G.nodes[target]
            
            try:
                source_x = float(source_data.get('x', 0))
                source_y = float(source_data.get('y', 0))
                target_x = float(target_data.get('x', 0))
                target_y = float(target_data.get('y', 0))
            except (TypeError, ValueError) as e:
                logger.warning(f"Skipping edge {source}-{target}: invalid coordinates - {e}")
                continue
            
            # Create line geometry
            line_geom = None
            
            # Try to use stored WKT geometry if available
            geometry_wkt = edge_data.get('geometry_wkt')
            if geometry_wkt:
                try:
                    line_geom = wkt_loads(geometry_wkt)
                except Exception as e:
                    logger.debug(f"Could not parse WKT geometry for edge {source}-{target}, using fallback: {e}")
            
            # Fallback to simple line between nodes
            if line_geom is None:
                line_geom = LineString([(source_x, source_y), (target_x, target_y)])
            
            # Create feature properties
            properties = {
                'source_node': str(source),
                'target_node': str(target),
                'feature_type': 'edge',
                'edge_type': edge_type
            }
            
            # Add edge-specific properties
            if edge_type == 'street':
                properties.update({
                    'street_id': edge_data.get('street_id', ''),
                    'name': edge_data.get('name', ''),
                    'highway': edge_data.get('highway', ''),
                    'length': float(edge_data.get('length', 0))
                })
            elif edge_type == 'connection':
                properties.update({
                    'connection_id': edge_data.get('connection_id', ''),
                    'distance': float(edge_data.get('distance', 0)),
                    'street_name': edge_data.get('street_name', '')
                })
            
            features.append({
                'geometry': line_geom,
                'properties': properties
            })
        
        if not features:
            logger.warning("No features could be extracted from GraphML")
            return gpd.GeoDataFrame()
        
        # Convert to GeoDataFrame
        geometries = [feature['geometry'] for feature in features]
        properties_list = [feature['properties'] for feature in features]
        
        # Create GeoDataFrame
        gdf = gpd.GeoDataFrame(properties_list, geometry=geometries)
        
        # Set CRS - assume the GraphML coordinates are in the target CRS from config
        target_crs = self.config.coordinate_system.get("target_crs", "EPSG:5243")
        gdf.crs = target_crs
        
        logger.info(f"Converted GraphML to GeoDataFrame with {len(gdf)} edge features (nodes excluded)")
        
        # Log edge type distribution instead of feature type
        if 'edge_type' in gdf.columns:
            logger.info(f"Edge type distribution: {gdf['edge_type'].value_counts().to_dict()}")
        
        return gdf
    
    def get_network_statistics(self, graphml_path: Optional[str] = None) -> Dict[str, Any]:
        """
        Get statistics about the network from GraphML file.
        
        Args:
            graphml_path: Path to GraphML file (uses config default if None)
            
        Returns:
            Dict with network statistics
        """
        if graphml_path is None:
            graphml_path = self.data_paths.get("network_graphml_path", "./data/heating_network.graphml")

        if not Path(graphml_path).exists():
            return {
                "status": "error",
                "message": f"GraphML file not found: {graphml_path}"
            }

        try:
            G = nx.read_graphml(graphml_path)
        except (OSError, nx.NetworkXError) as exc:
            logger.error(f"Unable to read GraphML from {graphml_path}: {exc}")
            return {
                "status": "error",
                "message": f"Could not read GraphML: {exc}"
            }

        node_types = {}
        for node_id, node_data in G.nodes(data=True):
            node_type = node_data.get('node_type', 'unknown')
            node_types[node_type] = node_types.get(node_type, 0) + 1

        edge_types = {}
        for source, target, edge_data in G.edges(data=True):
            edge_type = edge_data.get('edge_type', 'unknown')
            edge_types[edge_type] = edge_types.get(edge_type, 0) + 1

        total_heat_demand = 0.0
        for node_id, node_data in G.nodes(data=True):
            if node_data.get('node_type') == 'building':
                heat_demand = node_data.get('heat_demand')
                if heat_demand:
                    total_heat_demand += float(heat_demand)

        undirected = G.to_undirected()
        is_connected = nx.is_connected(undirected)
        num_components = nx.number_connected_components(undirected)

        return {
            "status": "success",
            "total_nodes": G.number_of_nodes(),
            "total_edges": G.number_of_edges(),
            "node_types": node_types,
            "edge_types": edge_types,
            "total_heat_demand": round(total_heat_demand, 2),
            "is_connected": is_connected,
            "num_components": num_components,
            "file_path": graphml_path
        }
