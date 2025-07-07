"""Network filtering functionality for district heating networks."""
import logging
from typing import Dict, Any, Optional, List, Tuple
from pathlib import Path
import pandas as pd  # type: ignore
import networkx as nx  # type: ignore

logger = logging.getLogger(__name__)


class NetworkFilter:
    """Handles filtering of district heating network graphs."""
    
    def __init__(self, config):
        """Initialize with configuration."""
        self.config = config
        self.data_paths = config.data_paths
        
        logger.info("NetworkFilter initialized")
    
    def filter_network(self, filter_criteria: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Filter the heating network graph based on specified criteria.
        
        Args:
            filter_criteria: Dictionary containing filter parameters
            
        Returns:
            Dict with status and information about the filtered network
        """
        try:
            # Load the original network
            original_graphml_path = self.data_paths.get("network_graphml_path", "./data/heating_network.graphml")
            
            if not Path(original_graphml_path).exists():
                return {
                    "status": "error",
                    "message": f"Original network file not found: {original_graphml_path}"
                }
            
            # Load the graph
            G = nx.read_graphml(original_graphml_path)
            
            if G.number_of_nodes() == 0:
                return {
                    "status": "error",
                    "message": "No nodes found in the original network"
                }
            
            logger.info(f"Loaded original network: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")
            
            # Apply filters if provided
            if filter_criteria:
                G_filtered = self._apply_filters(G, filter_criteria)
            else:
                G_filtered = G.copy()
            
            # Save filtered network
            filtered_graphml_path = self.data_paths.get("filtered_network_graphml_path", "./data/filtered_heating_network.graphml")
            result = self._save_filtered_network(G_filtered, filtered_graphml_path)
            
            # Update result with filtering statistics
            result.update({
                "original_nodes": G.number_of_nodes(),
                "original_edges": G.number_of_edges(),
                "filtered_nodes": G_filtered.number_of_nodes(),
                "filtered_edges": G_filtered.number_of_edges(),
                "nodes_removed": G.number_of_nodes() - G_filtered.number_of_nodes(),
                "edges_removed": G.number_of_edges() - G_filtered.number_of_edges()
            })
            
            return result
            
        except Exception as e:
            logger.error(f"Error filtering network: {e}")
            return {"status": "error", "message": str(e)}
    
    def _apply_filters(self, G: nx.DiGraph, filter_criteria: Dict[str, Any]) -> nx.DiGraph:
        """Apply various filters to the network graph."""
        G_filtered = G.copy()
        
        # Filter by node types
        node_types = filter_criteria.get("node_types", [])
        if node_types and len(node_types) > 0:
            G_filtered = self._filter_by_node_types(G_filtered, node_types)
        
        # Filter by edge types
        edge_types = filter_criteria.get("edge_types", [])
        if edge_types and len(edge_types) > 0:
            G_filtered = self._filter_by_edge_types(G_filtered, edge_types)
        
        # Remove unconnected nodes if requested
        exclude_unconnected = filter_criteria.get("exclude_unconnected_nodes", False)
        if exclude_unconnected:
            G_filtered = self._remove_unconnected_nodes(G_filtered)
        
        logger.info(f"Filters applied: {G.number_of_nodes()} -> {G_filtered.number_of_nodes()} nodes, "
                   f"{G.number_of_edges()} -> {G_filtered.number_of_edges()} edges")
        
        return G_filtered
    
    def _filter_by_node_types(self, G: nx.DiGraph, allowed_node_types: List[str]) -> nx.DiGraph:
        """Filter graph to include only specified node types."""
        nodes_to_remove = []
        
        for node_id, node_data in G.nodes(data=True):
            node_type = node_data.get('node_type', 'unknown')
            if node_type not in allowed_node_types:
                nodes_to_remove.append(node_id)
        
        G.remove_nodes_from(nodes_to_remove)
        logger.info(f"Removed {len(nodes_to_remove)} nodes by node type filter")
        
        return G
    
    def _filter_by_edge_types(self, G: nx.DiGraph, allowed_edge_types: List[str]) -> nx.DiGraph:
        """Filter graph to include only specified edge types."""
        edges_to_remove = []
        
        for source, target, edge_data in G.edges(data=True):
            edge_type = edge_data.get('edge_type', 'unknown')
            if edge_type not in allowed_edge_types:
                edges_to_remove.append((source, target))
        
        G.remove_edges_from(edges_to_remove)
        logger.info(f"Removed {len(edges_to_remove)} edges by edge type filter")
        
        return G
    
    def _remove_unconnected_nodes(self, G: nx.DiGraph) -> nx.DiGraph:
        """Remove nodes that have no connections (degree 0)."""
        nodes_to_remove = []
        
        for node_id in G.nodes():
            if G.degree(node_id) == 0:
                nodes_to_remove.append(node_id)
        
        G.remove_nodes_from(nodes_to_remove)
        logger.info(f"Removed {len(nodes_to_remove)} unconnected nodes")
        
        return G
    
    def _save_filtered_network(self, G_filtered: nx.DiGraph, output_path: str) -> Dict[str, Any]:
        """Save the filtered network to a GraphML file."""
        try:
            # Ensure output directory exists
            output_file = Path(output_path)
            output_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Save the filtered graph
            nx.write_graphml(G_filtered, output_path)
            
            logger.info(f"Filtered network saved to: {output_path}")
            logger.info(f"Filtered network contains {G_filtered.number_of_nodes()} nodes and {G_filtered.number_of_edges()} edges")
            
            return {
                "status": "success",
                "message": f"Filtered network saved with {G_filtered.number_of_nodes()} nodes and {G_filtered.number_of_edges()} edges",
                "file_path": output_path
            }
            
        except Exception as e:
            logger.error(f"Error saving filtered network: {e}")
            return {
                "status": "error",
                "message": f"Failed to save filtered network: {str(e)}"
            }
    
    def get_network_filter_options(self) -> Dict[str, List[str]]:
        """Get available filter options from the original network."""
        try:
            original_graphml_path = self.data_paths.get("network_graphml_path", "./data/heating_network.graphml")
            
            if not Path(original_graphml_path).exists():
                logger.warning(f"Original network file not found: {original_graphml_path}")
                return {"node_types": [], "edge_types": []}
            
            # Load the graph
            G = nx.read_graphml(original_graphml_path)
            
            # Get unique node types
            node_types = set()
            for node_id, node_data in G.nodes(data=True):
                node_type = node_data.get('node_type', 'unknown')
                node_types.add(node_type)
            
            # Get unique edge types
            edge_types = set()
            for source, target, edge_data in G.edges(data=True):
                edge_type = edge_data.get('edge_type', 'unknown')
                edge_types.add(edge_type)
            
            return {
                "node_types": sorted(list(node_types)),
                "edge_types": sorted(list(edge_types))
            }
            
        except Exception as e:
            logger.error(f"Error getting network filter options: {e}")
            return {"node_types": [], "edge_types": []}
    
    def get_network_statistics(self, graphml_path: Optional[str] = None) -> Dict[str, Any]:
        """Get statistics about a network GraphML file."""
        try:
            if graphml_path is None:
                graphml_path = self.data_paths.get("filtered_network_graphml_path", "./data/filtered_heating_network.graphml")
            
            if not Path(graphml_path).exists():
                return {
                    "status": "error",
                    "message": f"Network file not found: {graphml_path}"
                }
            
            # Load GraphML network
            G = nx.read_graphml(graphml_path)
            
            # Count nodes by type
            node_types = {}
            total_heat_demand = 0
            for node_id, node_data in G.nodes(data=True):
                node_type = node_data.get('node_type', 'unknown')
                node_types[node_type] = node_types.get(node_type, 0) + 1
                
                # Sum heat demand for building nodes
                if node_type == 'building':
                    heat_demand = node_data.get('heat_demand', 0)
                    if heat_demand:
                        total_heat_demand += float(heat_demand)
            
            # Count edges by type
            edge_types = {}
            for source, target, edge_data in G.edges(data=True):
                edge_type = edge_data.get('edge_type', 'unknown')
                edge_types[edge_type] = edge_types.get(edge_type, 0) + 1
            
            # Basic network metrics
            is_connected = nx.is_connected(G.to_undirected()) if G.number_of_nodes() > 0 else False
            num_components = nx.number_connected_components(G.to_undirected()) if G.number_of_nodes() > 0 else 0
            
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
            
        except Exception as e:
            logger.error(f"Error getting network statistics: {e}")
            return {
                "status": "error",
                "message": str(e)
            }
