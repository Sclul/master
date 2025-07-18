"""Graph filtering and optimization for district heating networks."""
import logging
from typing import Dict, Any, Optional, List, Tuple
from pathlib import Path
from abc import ABC, abstractmethod
import networkx as nx # type: ignore
import geopandas as gpd # type: ignore
from shapely.geometry import Point # type: ignore
import numpy as np # type: ignore

logger = logging.getLogger(__name__)


class PruningAlgorithm(ABC):
    """Abstract base class for graph pruning algorithms."""
    
    @abstractmethod
    def prune(self, G: nx.Graph, **kwargs) -> Tuple[nx.Graph, Dict[str, Any]]:
        """
        Apply pruning algorithm to graph.
        
        Returns:
            Tuple of (pruned_graph, pruning_statistics)
        """
        pass


class MinimumSpanningTreePruner(PruningAlgorithm):
    """Prune graph to minimum spanning tree while preserving critical connections."""
    
    def prune(self, G: nx.Graph, preserve_critical_nodes: bool = True, **kwargs) -> Tuple[nx.Graph, Dict[str, Any]]:
        """Create minimum spanning tree of the graph."""
        if G.number_of_nodes() == 0:
            return G, {"message": "Empty graph"}
        
        # Identify critical nodes (buildings with heat demand)
        critical_nodes = set()
        if preserve_critical_nodes:
            for node, data in G.nodes(data=True):
                if (data.get('node_type') == 'building' and 
                    data.get('heat_demand', 0) > 0):
                    critical_nodes.add(node)
        
        # Create MST
        mst = nx.minimum_spanning_tree(G, weight='length')
        
        # Ensure all critical nodes are connected
        if critical_nodes:
            # Find shortest paths to connect any isolated critical nodes
            for node in critical_nodes:
                if node not in mst:
                    # Find nearest connected node
                    try:
                        path = nx.shortest_path(G, source=node, target=next(iter(mst.nodes())), weight='length')
                        # Add path edges to MST
                        for i in range(len(path) - 1):
                            if not mst.has_edge(path[i], path[i+1]):
                                edge_data = G[path[i]][path[i+1]]
                                mst.add_edge(path[i], path[i+1], **edge_data)
                    except (nx.NetworkXNoPath, StopIteration):
                        continue
        
        original_edges = G.number_of_edges()
        mst_edges = mst.number_of_edges()
        
        stats = {
            "algorithm": "minimum_spanning_tree",
            "original_edges": original_edges,
            "remaining_edges": mst_edges,
            "removed_edges": original_edges - mst_edges,
            "critical_nodes_preserved": len(critical_nodes)
        }
        
        return mst, stats


class ShortestPathOptimizationPruner(PruningAlgorithm):
    """Optimize network using shortest path algorithms."""
    
    def prune(self, G: nx.Graph, **kwargs) -> Tuple[nx.Graph, Dict[str, Any]]:
        """Optimize network by keeping only shortest paths between buildings."""
        if G.number_of_nodes() == 0:
            return G, {"message": "Empty graph"}
        
        # Find all building nodes
        building_nodes = [node for node, data in G.nodes(data=True) 
                         if data.get('node_type') == 'building']
        
        if len(building_nodes) < 2:
            return G, {"message": "Need at least 2 buildings for optimization"}
        
        # Create new graph with shortest paths between all building pairs
        optimized_graph = nx.Graph()
        
        # Add all nodes first
        for node, data in G.nodes(data=True):
            optimized_graph.add_node(node, **data)
        
        # Add shortest paths between all building pairs
        edges_added = 0
        for i, source in enumerate(building_nodes):
            for target in building_nodes[i+1:]:
                try:
                    path = nx.shortest_path(G, source=source, target=target, weight='length')
                    # Add all edges in the path
                    for j in range(len(path) - 1):
                        u, v = path[j], path[j+1]
                        if not optimized_graph.has_edge(u, v):
                            edge_data = G[u][v]
                            optimized_graph.add_edge(u, v, **edge_data)
                            edges_added += 1
                except nx.NetworkXNoPath:
                    continue
        
        # Remove isolated nodes
        isolated_nodes = [node for node in optimized_graph.nodes() 
                         if optimized_graph.degree(node) == 0]
        optimized_graph.remove_nodes_from(isolated_nodes)
        
        stats = {
            "algorithm": "shortest_path_optimization",
            "original_edges": G.number_of_edges(),
            "remaining_edges": optimized_graph.number_of_edges(),
            "removed_edges": G.number_of_edges() - optimized_graph.number_of_edges(),
            "building_nodes_connected": len(building_nodes),
            "isolated_nodes_removed": len(isolated_nodes)
        }
        
        return optimized_graph, stats




class GraphFilter:
    """Handles graph filtering and optimization operations."""
    
    def __init__(self, config):
        """Initialize with configuration."""
        self.config = config
        self.data_paths = config.data_paths
        self.filter_settings = config.graph_filters
        self.pruning_algorithms = self._register_pruning_algorithms()
        
        logger.info("GraphFilter initialized")
    
    def _register_pruning_algorithms(self) -> Dict[str, PruningAlgorithm]:
        """Register available pruning algorithms."""
        return {
            "minimum_spanning_tree": MinimumSpanningTreePruner(),
            "shortest_path_optimization": ShortestPathOptimizationPruner()
        }
    
    def filter_and_optimize_graph(self, 
                                graphml_path: Optional[str] = None,
                                output_path: Optional[str] = None,
                                max_building_connection: Optional[float] = None,
                                pruning_algorithm: Optional[str] = None,
                                pruning_params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Apply filtering and optimization to graph.
        
        Args:
            graphml_path: Input GraphML file path
            output_path: Output GraphML file path  
            max_building_connection: Maximum distance for building connections
            pruning_algorithm: Name of pruning algorithm to apply
            pruning_params: Parameters for pruning algorithm
            
        Returns:
            Dictionary with operation results and statistics
        """
        try:
            # Use defaults from config if not provided
            if graphml_path is None:
                graphml_path = self.data_paths.get("network_graphml_path", "./data/heating_network.graphml")
            if output_path is None:
                output_path = self.data_paths.get("filtered_network_graphml_path", "./data/filtered_heating_network.graphml")
            if max_building_connection is None:
                max_building_connection = self.filter_settings.get("max_building_connection_distance", 100.0)
            
            # Load GraphML
            if not Path(graphml_path).exists():
                return {"status": "error", "message": f"GraphML file not found: {graphml_path}"}
            
            G = nx.read_graphml(graphml_path)
            logger.info(f"Loaded GraphML with {G.number_of_nodes()} nodes and {G.number_of_edges()} edges")
            
            # Get initial statistics
            initial_stats = self._get_graph_statistics(G)
            
            # Apply building connection distance filter
            G_filtered, connection_stats = self._filter_building_connections(G, max_building_connection)
            
            # Apply pruning algorithm if specified
            pruning_stats = {}
            if pruning_algorithm and pruning_algorithm in self.pruning_algorithms:
                if pruning_params is None:
                    pruning_params = self.filter_settings.get("pruning_algorithms", {}).get(pruning_algorithm, {})
                
                pruner = self.pruning_algorithms[pruning_algorithm]
                G_filtered, pruning_stats = pruner.prune(G_filtered, **pruning_params)
                logger.info(f"Applied {pruning_algorithm} pruning")
            
            # Clean graph for GraphML compliance
            self._clean_graph_for_graphml(G_filtered)
            
            # Save filtered graph
            output_file = Path(output_path)
            output_file.parent.mkdir(parents=True, exist_ok=True)
            nx.write_graphml(G_filtered, output_path)
            
            # Get final statistics
            final_stats = self._get_graph_statistics(G_filtered)
            
            # Calculate reduction percentages
            node_reduction = ((initial_stats["total_nodes"] - final_stats["total_nodes"]) / initial_stats["total_nodes"] * 100) if initial_stats["total_nodes"] > 0 else 0
            edge_reduction = ((initial_stats["total_edges"] - final_stats["total_edges"]) / initial_stats["total_edges"] * 100) if initial_stats["total_edges"] > 0 else 0
            
            logger.info(f"Graph filtering complete: {initial_stats['total_nodes']} -> {final_stats['total_nodes']} nodes ({node_reduction:.1f}% reduction)")
            
            return {
                "status": "success",
                "message": f"Graph filtered and optimized successfully",
                "file_path": output_path,
                "initial_stats": initial_stats,
                "final_stats": final_stats,
                "connection_filter_stats": connection_stats,
                "pruning_stats": pruning_stats,
                "node_reduction_percentage": round(node_reduction, 1),
                "edge_reduction_percentage": round(edge_reduction, 1)
            }
            
        except Exception as e:
            logger.error(f"Error filtering and optimizing graph: {e}")
            return {"status": "error", "message": str(e)}
    
    def _filter_building_connections(self, G: nx.Graph, max_distance: float) -> Tuple[nx.Graph, Dict[str, Any]]:
        """Filter building connections by maximum distance and remove isolated building nodes."""
        G_filtered = G.copy()
        
        # Find building connections that exceed max distance
        building_connections_to_remove = []
        building_nodes_to_remove = []
        
        for u, v, data in G_filtered.edges(data=True):
            if data.get('edge_type') == 'building_connection':
                edge_length = data.get('length', 0)
                if edge_length > max_distance:
                    building_connections_to_remove.append((u, v))
                    
                    # Identify which node is the building node
                    u_type = G_filtered.nodes[u].get('node_type', '')
                    v_type = G_filtered.nodes[v].get('node_type', '')
                    
                    if u_type == 'building':
                        building_nodes_to_remove.append(u)
                    elif v_type == 'building':
                        building_nodes_to_remove.append(v)
        
        # Remove the connections and building nodes
        G_filtered.remove_edges_from(building_connections_to_remove)
        G_filtered.remove_nodes_from(building_nodes_to_remove)
        
        # Also remove any orphaned street_connection nodes
        orphaned_nodes = []
        for node in G_filtered.nodes():
            if (G_filtered.nodes[node].get('node_type') == 'street_connection' and 
                G_filtered.degree(node) == 0):
                orphaned_nodes.append(node)
        
        G_filtered.remove_nodes_from(orphaned_nodes)
        
        stats = {
            "removed_connections": len(building_connections_to_remove),
            "removed_building_nodes": len(building_nodes_to_remove),
            "removed_orphaned_nodes": len(orphaned_nodes),
            "max_distance_threshold": max_distance
        }
        
        logger.info(f"Removed {len(building_connections_to_remove)} building connections exceeding {max_distance}m")
        logger.info(f"Removed {len(building_nodes_to_remove)} building nodes and {len(orphaned_nodes)} orphaned nodes")
        
        return G_filtered, stats
    
    def _get_graph_statistics(self, G: nx.Graph) -> Dict[str, Any]:
        """Get comprehensive statistics about the graph."""
        node_types = {}
        for node_id, node_data in G.nodes(data=True):
            node_type = node_data.get('node_type', 'unknown')
            node_types[node_type] = node_types.get(node_type, 0) + 1
        
        edge_types = {}
        for source, target, edge_data in G.edges(data=True):
            edge_type = edge_data.get('edge_type', 'unknown')
            edge_types[edge_type] = edge_types.get(edge_type, 0) + 1
        
        # Calculate total heat demand
        total_heat_demand = 0
        for node_id, node_data in G.nodes(data=True):
            if node_data.get('node_type') == 'building':
                heat_demand = node_data.get('heat_demand', 0)
                if heat_demand:
                    total_heat_demand += float(heat_demand)
        
        # Network connectivity
        is_connected = nx.is_connected(G) if G.number_of_nodes() > 0 else False
        num_components = nx.number_connected_components(G) if G.number_of_nodes() > 0 else 0
        
        return {
            "total_nodes": G.number_of_nodes(),
            "total_edges": G.number_of_edges(),
            "node_types": node_types,
            "edge_types": edge_types,
            "total_heat_demand": round(total_heat_demand, 2),
            "is_connected": is_connected,
            "num_components": num_components
        }
    
    def _clean_graph_for_graphml(self, G: nx.Graph) -> None:
        """Remove attributes with None values from nodes and edges for GraphML compliance."""
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
