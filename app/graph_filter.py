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
        """Create minimum spanning tree that connects all buildings with minimal infrastructure."""
        
        if G.number_of_nodes() == 0:
            return G, {"message": "Empty graph"}
        
        # Step 1: Identify building nodes
        building_nodes = [n for n, data in G.nodes(data=True) 
                        if data.get('node_type') == 'building']
        
        if len(building_nodes) < 2:
            return G, {"message": f"Need at least 2 buildings, found {len(building_nodes)}"}
        
        # DEBUG: Check building connectivity
        logger.info(f"Total buildings found: {len(building_nodes)}")
        
        # Check if buildings are connected to the network
        connected_buildings = []
        isolated_buildings = []
        for building in building_nodes:
            if G.degree(building) > 0:
                connected_buildings.append(building)
            else:
                isolated_buildings.append(building)
        
        logger.info(f"Connected buildings: {len(connected_buildings)}")
        logger.info(f"Isolated buildings: {len(isolated_buildings)}")
        
        # Check connected components before MST
        if not nx.is_connected(G):
            components = list(nx.connected_components(G))
            logger.info(f"Graph has {len(components)} connected components")
            
            # Log component sizes and building counts
            for i, component in enumerate(components):
                buildings_in_component = [n for n in component if G.nodes[n].get('node_type') == 'building']
                logger.info(f"Component {i}: {len(component)} nodes, {len(buildings_in_component)} buildings")
        
        # Step 2: Ensure all edges have weights (use 'length' attribute)
        for u, v, data in G.edges(data=True):
            if 'length' not in data or data['length'] is None:
                # Fallback to geometric distance if length missing
                pos_u = (G.nodes[u].get('x', 0), G.nodes[u].get('y', 0))
                pos_v = (G.nodes[v].get('x', 0), G.nodes[v].get('y', 0))
                data['length'] = ((pos_u[0] - pos_v[0])**2 + (pos_u[1] - pos_v[1])**2)**0.5
        
        # Step 3: Get largest connected component
        if not nx.is_connected(G):
            # Get all connected components
            components = list(nx.connected_components(G))
            # Find the largest component
            largest_component = max(components, key=len)
            # Create subgraph with largest component
            G = G.subgraph(largest_component).copy()
        
        # Step 4: Create MST using edge lengths as weights
        mst_edges = list(nx.minimum_spanning_tree(G, weight='length').edges(data=True))
        
        # Step 5: Build MST graph
        mst_graph = nx.Graph()
        
        # Add all nodes from largest component
        for node, data in G.nodes(data=True):
            mst_graph.add_node(node, **data)
        
        # Add MST edges
        total_length = 0
        for u, v, data in mst_edges:
            mst_graph.add_edge(u, v, **data)
            total_length += data.get('length', 0)
        
        # Step 6: Remove end nodes that are not buildings
        nodes_before_cleanup = mst_graph.number_of_nodes()
        removed_end_nodes = self._remove_non_building_end_nodes(mst_graph)
        nodes_after_cleanup = mst_graph.number_of_nodes()
        
        logger.info(f"MST cleanup: {nodes_before_cleanup} -> {nodes_after_cleanup} nodes ({removed_end_nodes} end nodes removed)")
        
        # Step 7: Calculate statistics
        original_length = sum(data.get('length', 0) for _, _, data in G.edges(data=True))
        connected_buildings = len([n for n in building_nodes if mst_graph.has_node(n)])
        
        stats = {
            "original_nodes": G.number_of_nodes(),
            "original_edges": G.number_of_edges(), 
            "mst_nodes": mst_graph.number_of_nodes(),
            "mst_edges": mst_graph.number_of_edges(),
            "total_buildings": len(building_nodes),
            "connected_buildings": connected_buildings,
            "removed_end_nodes": removed_end_nodes,
            "total_length": total_length,
            "original_total_length": original_length,
            "length_reduction": original_length - total_length,
            "reduction_percentage": ((original_length - total_length) / original_length * 100) if original_length > 0 else 0
        }
        
        return mst_graph, stats

    def _remove_non_building_end_nodes(self, G: nx.Graph) -> int:
        """
        Remove end nodes (degree = 1) that are not buildings.
        Continues iteratively until no more non-building end nodes exist.
        
        Args:
            G: Graph to modify in-place
            
        Returns:
            Number of nodes removed
        """
        removed_count = 0
        
        while True:
            # Find end nodes that are not buildings
            end_nodes_to_remove = []
            
            for node in G.nodes():
                if G.degree(node) == 1:  # End node (degree = 1)
                    node_type = G.nodes[node].get('node_type', 'unknown')
                    if node_type != 'building':
                        end_nodes_to_remove.append(node)
            
            # If no more end nodes to remove, we're done
            if not end_nodes_to_remove:
                break
            
            # Remove the end nodes
            G.remove_nodes_from(end_nodes_to_remove)
            removed_count += len(end_nodes_to_remove)
            
            logger.info(f"Removed {len(end_nodes_to_remove)} non-building end nodes")
        
        logger.info(f"Total non-building end nodes removed: {removed_count}")
        return removed_count



class AllBuildingConnectionsPruner(PruningAlgorithm):
    """Ensure all buildings are connected via optimal paths."""
    
    def prune(self, G: nx.Graph, **kwargs) -> Tuple[nx.Graph, Dict[str, Any]]:
        """Optimize network by keeping only shortest paths between buildings."""
        
        if G.number_of_nodes() == 0:
            return G, {"message": "Empty graph"}
        
        # Step 1: Identify building nodes
        building_nodes = [node for node, data in G.nodes(data=True) 
                         if data.get('node_type') == 'building']
        
        if len(building_nodes) < 2:
            return G, {"message": "Need at least 2 buildings for optimization"}
        
        # DEBUG: Check building connectivity
        logger.info(f"Total buildings found: {len(building_nodes)}")
        
        # Check if buildings are connected to the network
        connected_buildings = []
        isolated_buildings = []
        for building in building_nodes:
            if G.degree(building) > 0:
                connected_buildings.append(building)
            else:
                isolated_buildings.append(building)
        
        logger.info(f"Connected buildings: {len(connected_buildings)}")
        logger.info(f"Isolated buildings: {len(isolated_buildings)}")
        
        # Check connected components before optimization
        if not nx.is_connected(G):
            components = list(nx.connected_components(G))
            logger.info(f"Graph has {len(components)} connected components")
            
            # Log component sizes and building counts
            for i, component in enumerate(components):
                buildings_in_component = [n for n in component if G.nodes[n].get('node_type') == 'building']
                logger.info(f"Component {i}: {len(component)} nodes, {len(buildings_in_component)} buildings")
        
        # Step 2: Ensure all edges have weights (use 'length' attribute)
        for u, v, data in G.edges(data=True):
            if 'length' not in data or data['length'] is None:
                # Fallback to geometric distance if length missing
                pos_u = (G.nodes[u].get('x', 0), G.nodes[u].get('y', 0))
                pos_v = (G.nodes[v].get('x', 0), G.nodes[v].get('y', 0))
                data['length'] = ((pos_u[0] - pos_v[0])**2 + (pos_u[1] - pos_v[1])**2)**0.5
        
        # Step 3: Create new graph with shortest paths between all building pairs
        optimized_graph = nx.Graph()
        
        # Add all nodes first
        for node, data in G.nodes(data=True):
            optimized_graph.add_node(node, **data)
        
        logger.info(f"Added {optimized_graph.number_of_nodes()} nodes to optimized graph")
        
        # Step 4: Add shortest paths between all building pairs
        edges_added = 0
        total_building_pairs = len(building_nodes) * (len(building_nodes) - 1) // 2
        successful_paths = 0
        failed_paths = 0
        
        logger.info(f"Calculating shortest paths for {total_building_pairs} building pairs")
        
        for i, source in enumerate(building_nodes):
            for target in building_nodes[i+1:]:
                try:
                    path = nx.shortest_path(G, source=source, target=target, weight='length')
                    successful_paths += 1
                    
                    # Add all edges in the path
                    for j in range(len(path) - 1):
                        u, v = path[j], path[j+1]
                        if not optimized_graph.has_edge(u, v):
                            edge_data = G[u][v]
                            optimized_graph.add_edge(u, v, **edge_data)
                            edges_added += 1
                except nx.NetworkXNoPath:
                    failed_paths += 1
                    continue
        
        logger.info(f"Path calculation complete: {successful_paths} successful, {failed_paths} failed")
        logger.info(f"Added {edges_added} edges from shortest paths")
        
        # Step 5: Remove isolated nodes
        nodes_before_cleanup = optimized_graph.number_of_nodes()
        isolated_nodes = [node for node in optimized_graph.nodes() 
                         if optimized_graph.degree(node) == 0]
        optimized_graph.remove_nodes_from(isolated_nodes)
        nodes_after_cleanup = optimized_graph.number_of_nodes()
        
        logger.info(f"Isolated node cleanup: {nodes_before_cleanup} -> {nodes_after_cleanup} nodes ({len(isolated_nodes)} isolated nodes removed)")
        
        # Step 6: Calculate statistics
        original_length = sum(data.get('length', 0) for _, _, data in G.edges(data=True))
        total_length = sum(data.get('length', 0) for _, _, data in optimized_graph.edges(data=True))
        connected_buildings_final = len([n for n in building_nodes if optimized_graph.has_node(n)])
        
        stats = {
            "algorithm": "all_building_connections",
            "original_nodes": G.number_of_nodes(),
            "original_edges": G.number_of_edges(),
            "optimized_nodes": optimized_graph.number_of_nodes(),
            "optimized_edges": optimized_graph.number_of_edges(),
            "total_buildings": len(building_nodes),
            "connected_buildings": connected_buildings_final,
            "building_pairs_calculated": total_building_pairs,
            "successful_paths": successful_paths,
            "failed_paths": failed_paths,
            "edges_added": edges_added,
            "isolated_nodes_removed": len(isolated_nodes),
            "total_length": total_length,
            "original_total_length": original_length,
            "length_reduction": original_length - total_length,
            "reduction_percentage": ((original_length - total_length) / original_length * 100) if original_length > 0 else 0
        }
        
        return optimized_graph, stats


class SteinerTreePruner(PruningAlgorithm):
    """Create Steiner tree connecting all buildings with minimal total infrastructure cost."""
    
    def prune(self, G: nx.Graph, **kwargs) -> Tuple[nx.Graph, Dict[str, Any]]:
        """Create Steiner tree that connects all buildings using minimum cost infrastructure."""
        
        if G.number_of_nodes() == 0:
            return G, {"message": "Empty graph"}
        
        # Step 1: Identify building nodes (terminal nodes for Steiner tree)
        building_nodes = [n for n, data in G.nodes(data=True) 
                         if data.get('node_type') == 'building']
        
        if len(building_nodes) < 2:
            return G, {"message": f"Need at least 2 buildings for Steiner tree, found {len(building_nodes)}"}
        
        # DEBUG: Check building connectivity
        logger.info(f"Total buildings found: {len(building_nodes)}")
        
        # Check if buildings are connected to the network
        connected_buildings = []
        isolated_buildings = []
        for building in building_nodes:
            if G.degree(building) > 0:
                connected_buildings.append(building)
            else:
                isolated_buildings.append(building)
        
        logger.info(f"Connected buildings: {len(connected_buildings)}")
        logger.info(f"Isolated buildings: {len(isolated_buildings)}")
        
        # Check connected components before Steiner tree construction
        if not nx.is_connected(G):
            components = list(nx.connected_components(G))
            logger.info(f"Graph has {len(components)} connected components")
            
            # Log component sizes and building counts
            for i, component in enumerate(components):
                buildings_in_component = [n for n in component if G.nodes[n].get('node_type') == 'building']
                logger.info(f"Component {i}: {len(component)} nodes, {len(buildings_in_component)} buildings")
        
        # Step 2: Ensure all edges have weights (use 'length' attribute)
        for u, v, data in G.edges(data=True):
            if 'length' not in data or data['length'] is None:
                # Fallback to geometric distance if length missing
                pos_u = (G.nodes[u].get('x', 0), G.nodes[u].get('y', 0))
                pos_v = (G.nodes[v].get('x', 0), G.nodes[v].get('y', 0))
                data['length'] = ((pos_u[0] - pos_v[0])**2 + (pos_u[1] - pos_v[1])**2)**0.5
        
        # Step 3: Work with largest connected component if graph is disconnected
        original_graph = G
        if not nx.is_connected(G):
            components = list(nx.connected_components(G))
            largest_component = max(components, key=len)
            G = G.subgraph(largest_component).copy()
            logger.info(f"Working with largest component: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")
            
            # Update building nodes to only include those in largest component
            building_nodes = [n for n in building_nodes if n in largest_component]
            logger.info(f"Buildings in largest component: {len(building_nodes)}")
        
        # Step 4: Approximate Steiner tree using shortest paths
        steiner_graph = nx.Graph()
        
        # Add all nodes from the working graph
        for node, data in G.nodes(data=True):
            steiner_graph.add_node(node, **data)
        
        logger.info(f"Added {steiner_graph.number_of_nodes()} nodes to Steiner tree graph")
        
        # Step 5: Build distance matrix between all building pairs
        building_distances = {}
        building_paths = {}
        total_pairs = len(building_nodes) * (len(building_nodes) - 1) // 2
        successful_paths = 0
        failed_paths = 0
        
        logger.info(f"Calculating shortest paths between {total_pairs} building pairs for Steiner tree")
        
        for i, source in enumerate(building_nodes):
            for target in building_nodes[i+1:]:
                try:
                    path = nx.shortest_path(G, source=source, target=target, weight='length')
                    distance = nx.shortest_path_length(G, source=source, target=target, weight='length')
                    
                    building_distances[(source, target)] = distance
                    building_paths[(source, target)] = path
                    successful_paths += 1
                    
                except nx.NetworkXNoPath:
                    failed_paths += 1
                    logger.debug(f"No path found between buildings {source} and {target}")
                    continue
        
        logger.info(f"Distance calculation complete: {successful_paths} successful, {failed_paths} failed")
        
        # Step 6: Use MST heuristic for Steiner tree approximation
        # Create complete graph of buildings with shortest path distances
        building_complete_graph = nx.Graph()
        building_complete_graph.add_nodes_from(building_nodes)
        
        for (source, target), distance in building_distances.items():
            building_complete_graph.add_edge(source, target, weight=distance)
        
        # Find MST of building complete graph
        if building_complete_graph.number_of_edges() > 0:
            mst_edges = list(nx.minimum_spanning_tree(building_complete_graph, weight='weight').edges())
            logger.info(f"Building MST has {len(mst_edges)} edges connecting {len(building_nodes)} buildings")
        else:
            mst_edges = []
            logger.warning("No edges in building complete graph - cannot construct Steiner tree")
        
        # Step 7: Add shortest paths for each MST edge to Steiner tree
        edges_added = 0
        steiner_nodes_used = set()
        
        for source, target in mst_edges:
            path_key = (source, target) if (source, target) in building_paths else (target, source)
            if path_key in building_paths:
                path = building_paths[path_key]
                
                # Add all edges in the shortest path
                for j in range(len(path) - 1):
                    u, v = path[j], path[j+1]
                    if not steiner_graph.has_edge(u, v):
                        edge_data = G[u][v]
                        steiner_graph.add_edge(u, v, **edge_data)
                        edges_added += 1
                
                # Track Steiner nodes (intermediate nodes)
                for node in path:
                    steiner_nodes_used.add(node)
        
        logger.info(f"Added {edges_added} edges from {len(mst_edges)} shortest paths")
        logger.info(f"Steiner tree uses {len(steiner_nodes_used)} total nodes ({len(building_nodes)} buildings + {len(steiner_nodes_used) - len(building_nodes)} Steiner nodes)")
        
        # Step 8: Remove unused nodes (nodes not part of any shortest path)
        nodes_before_cleanup = steiner_graph.number_of_nodes()
        unused_nodes = [node for node in steiner_graph.nodes() 
                       if node not in steiner_nodes_used]
        steiner_graph.remove_nodes_from(unused_nodes)
        nodes_after_cleanup = steiner_graph.number_of_nodes()
        
        logger.info(f"Node cleanup: {nodes_before_cleanup} -> {nodes_after_cleanup} nodes ({len(unused_nodes)} unused nodes removed)")
        
        # Step 9: Remove non-building end nodes iteratively
        nodes_before_end_cleanup = steiner_graph.number_of_nodes()
        removed_end_nodes = self._remove_non_building_end_nodes(steiner_graph)
        nodes_after_end_cleanup = steiner_graph.number_of_nodes()
        
        logger.info(f"End node cleanup: {nodes_before_end_cleanup} -> {nodes_after_end_cleanup} nodes ({removed_end_nodes} non-building end nodes removed)")
        
        # Step 10: Calculate comprehensive statistics
        original_length = sum(data.get('length', 0) for _, _, data in original_graph.edges(data=True))
        steiner_length = sum(data.get('length', 0) for _, _, data in steiner_graph.edges(data=True))
        connected_buildings_final = len([n for n in building_nodes if steiner_graph.has_node(n)])
        
        # Calculate Steiner tree efficiency metrics
        steiner_nodes_count = len([n for n in steiner_graph.nodes() 
                                 if steiner_graph.nodes[n].get('node_type') != 'building'])
        
        logger.info(f"Final Steiner tree statistics:")
        logger.info(f"  - Total length: {steiner_length:.2f}")
        logger.info(f"  - Connected buildings: {connected_buildings_final}/{len(building_nodes)}")
        logger.info(f"  - Steiner nodes: {steiner_nodes_count}")
        logger.info(f"  - Tree connectivity: {nx.is_connected(steiner_graph) if steiner_graph.number_of_nodes() > 0 else False}")
        
        stats = {
            "algorithm": "steiner_tree",
            "original_nodes": original_graph.number_of_nodes(),
            "original_edges": original_graph.number_of_edges(),
            "steiner_nodes": steiner_graph.number_of_nodes(),
            "steiner_edges": steiner_graph.number_of_edges(),
            "total_buildings": len(building_nodes),
            "connected_buildings": connected_buildings_final,
            "steiner_nodes_count": steiner_nodes_count,
            "building_pairs_calculated": total_pairs,
            "successful_paths": successful_paths,
            "failed_paths": failed_paths,
            "mst_edges_used": len(mst_edges),
            "edges_added_from_paths": edges_added,
            "unused_nodes_removed": len(unused_nodes),
            "removed_end_nodes": removed_end_nodes,
            "total_length": steiner_length,
            "original_total_length": original_length,
            "length_reduction": original_length - steiner_length,
            "reduction_percentage": ((original_length - steiner_length) / original_length * 100) if original_length > 0 else 0,
            "node_reduction_percentage": ((original_graph.number_of_nodes() - steiner_graph.number_of_nodes()) / original_graph.number_of_nodes() * 100) if original_graph.number_of_nodes() > 0 else 0,
            "edge_reduction_percentage": ((original_graph.number_of_edges() - steiner_graph.number_of_edges()) / original_graph.number_of_edges() * 100) if original_graph.number_of_edges() > 0 else 0
        }
        
        return steiner_graph, stats
    
    def _remove_non_building_end_nodes(self, G: nx.Graph) -> int:
        """
        Remove end nodes (degree = 1) that are not buildings.
        Continues iteratively until no more non-building end nodes exist.
        
        Args:
            G: Graph to modify in-place
            
        Returns:
            Number of nodes removed
        """
        removed_count = 0
        
        while True:
            # Find end nodes that are not buildings
            end_nodes_to_remove = []
            
            for node in G.nodes():
                if G.degree(node) == 1:  # End node (degree = 1)
                    node_type = G.nodes[node].get('node_type', 'unknown')
                    if node_type != 'building':
                        end_nodes_to_remove.append(node)
            
            # If no more end nodes to remove, we're done
            if not end_nodes_to_remove:
                break
            
            # Remove the end nodes
            G.remove_nodes_from(end_nodes_to_remove)
            removed_count += len(end_nodes_to_remove)
            
            logger.info(f"Removed {len(end_nodes_to_remove)} non-building end nodes")
        
        logger.info(f"Total non-building end nodes removed: {removed_count}")
        return removed_count


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
            "all_building_connections": AllBuildingConnectionsPruner(),
            "steiner_tree": SteinerTreePruner()
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
                logger.info(f"Applying pruning algorithm: {pruning_algorithm}")
                if pruning_params is None:
                    pruning_params = self.filter_settings.get("pruning_algorithms", {}).get(pruning_algorithm, {})
                
                # Ensure pruning_params is never None
                if pruning_params is None:
                    pruning_params = {}
                
                logger.info(f"Pruning parameters: {pruning_params}")
                pruner = self.pruning_algorithms[pruning_algorithm]
                G_filtered, pruning_stats = pruner.prune(G_filtered, **pruning_params)
                logger.info(f"Applied {pruning_algorithm} pruning")
            else:
                logger.info(f"No pruning algorithm specified (got: {pruning_algorithm})")
                logger.info(f"Available algorithms: {list(self.pruning_algorithms.keys())}")
            
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
        """Filter building connections by maximum distance but NEVER remove building nodes."""
        G_filtered = G.copy()
        
        # Find building connections that exceed max distance
        building_connections_to_remove = []
        
        for u, v, data in G_filtered.edges(data=True):
            if data.get('edge_type') == 'building_connection':
                edge_length = data.get('length', 0)
                if edge_length > max_distance:
                    building_connections_to_remove.append((u, v))
        
        # Remove only the connections, NOT the building nodes
        G_filtered.remove_edges_from(building_connections_to_remove)
        
        # Remove any orphaned street_connection nodes (but never building nodes)
        orphaned_nodes = []
        for node in G_filtered.nodes():
            node_type = G_filtered.nodes[node].get('node_type', '')
            if node_type == 'street_connection' and G_filtered.degree(node) == 0:
                orphaned_nodes.append(node)
        
        G_filtered.remove_nodes_from(orphaned_nodes)
        
        stats = {
            "removed_connections": len(building_connections_to_remove),
            "removed_building_nodes": 0,  # Never remove building nodes
            "removed_orphaned_nodes": len(orphaned_nodes),
            "max_distance_threshold": max_distance
        }
        
        logger.info(f"Removed {len(building_connections_to_remove)} building connections exceeding {max_distance}m")
        logger.info(f"Removed 0 building nodes (never remove buildings) and {len(orphaned_nodes)} orphaned street nodes")
        
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
