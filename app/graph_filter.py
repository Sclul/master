"""Graph filtering and optimization for district heating networks."""
import logging
from typing import Dict, Any, Optional, List, Tuple
from pathlib import Path
from abc import ABC, abstractmethod
import networkx as nx # type: ignore
import geopandas as gpd # type: ignore
from shapely.geometry import Point, LineString # type: ignore
import numpy as np # type: ignore

logger = logging.getLogger(__name__)


def remove_non_building_end_nodes(G: nx.Graph) -> int:
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
                if node_type != 'building' and node_type != 'heat_source':
                    end_nodes_to_remove.append(node)
        
        # If no more end nodes to remove, we're done
        if not end_nodes_to_remove:
            break
        
        # Remove the end nodes
        G.remove_nodes_from(end_nodes_to_remove)
        removed_count += len(end_nodes_to_remove)
        
        logger.debug(f"Removed {len(end_nodes_to_remove)} non-building end nodes")
    
    if removed_count > 0:
        logger.info(f"Total non-building end nodes removed: {removed_count}")
    return removed_count


class PruningAlgorithm(ABC):
    """Abstract base class for graph pruning algorithms."""
    
    @abstractmethod
    def prune(self, G: nx.Graph, **kwargs) -> Tuple[nx.Graph, Dict[str, Any]]:
        """
        Apply pruning algorithm to graph.
        
        Returns:
            Tuple of (pruned_graph, pruning_statistics)
        """
        ...


class MinimumSpanningTreePruner(PruningAlgorithm):
    """Prune graph to minimum spanning tree while preserving critical connections."""
    
    def prune(self, G: nx.Graph, preserve_critical_nodes: bool = True, **kwargs) -> Tuple[nx.Graph, Dict[str, Any]]:
        """Create minimum spanning tree that connects all buildings and heat sources with minimal infrastructure."""
        
        if G.number_of_nodes() == 0:
            return G, {"message": "Empty graph"}
        
        # Step 1: Identify building and heat source nodes (terminal nodes)
        building_nodes = [n for n, data in G.nodes(data=True) 
                        if data.get('node_type') == 'building']
        heat_source_nodes = [n for n, data in G.nodes(data=True) 
                           if data.get('node_type') == 'heat_source']
        terminal_nodes = building_nodes + heat_source_nodes
        
        if len(terminal_nodes) < 2:
            return G, {"message": f"Need at least 2 terminal nodes (buildings + heat sources), found {len(terminal_nodes)}"}
        
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
        removed_end_nodes = remove_non_building_end_nodes(mst_graph)
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
        removed_end_nodes = remove_non_building_end_nodes(steiner_graph)
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


class LoopEnhancedMSTPruner(PruningAlgorithm):
    """Create MST and strategically add loops to improve mass flow distribution in long branches."""
    
    def prune(self, G: nx.Graph, max_loops_to_add: int = 5000, 
              min_branch_length_m: float = 100.0, 
              prefer_edge_disjoint: bool = True, **kwargs) -> Tuple[nx.Graph, Dict[str, Any]]:
        """
        Create MST then add strategic loops to improve hydraulic performance.
        
        Args:
            G: Input graph
            max_loops_to_add: Maximum number of loops to create
            min_branch_length_m: Only enhance branches longer than this threshold
            prefer_edge_disjoint: Prefer loops that create edge-disjoint paths
            
        Returns:
            Tuple of (optimized_graph, statistics)
        """
        if G.number_of_nodes() == 0:
            return G, {"message": "Empty graph"}
        
        # Step 1: Create base MST using existing pruner
        logger.info("Step 1: Creating base MST")
        mst_pruner = MinimumSpanningTreePruner()
        mst_graph, mst_stats = mst_pruner.prune(G, preserve_critical_nodes=True)
        
        if mst_graph.number_of_nodes() == 0:
            return mst_graph, {**mst_stats, "message": "MST creation failed"}
        
        logger.info(f"Base MST: {mst_graph.number_of_nodes()} nodes, {mst_graph.number_of_edges()} edges")
        
        # Step 2: Identify heat sources and buildings
        heat_source_nodes = [n for n, data in mst_graph.nodes(data=True) 
                            if data.get('node_type') == 'heat_source']
        building_nodes = [n for n, data in mst_graph.nodes(data=True) 
                         if data.get('node_type') == 'building']
        
        if not heat_source_nodes:
            logger.warning("No heat sources found in MST")
            return mst_graph, {**mst_stats, "loops_added": 0, "message": "No heat sources"}
        
        if not building_nodes:
            logger.warning("No buildings found in MST")
            return mst_graph, {**mst_stats, "loops_added": 0, "message": "No buildings"}
        
        logger.info(f"Found {len(heat_source_nodes)} heat sources and {len(building_nodes)} buildings")
        
        # Step 3: Ensure edge weights exist
        for u, v, data in G.edges(data=True):
            if 'length' not in data or data['length'] is None:
                pos_u = (G.nodes[u].get('x', 0), G.nodes[u].get('y', 0))
                pos_v = (G.nodes[v].get('x', 0), G.nodes[v].get('y', 0))
                data['length'] = ((pos_u[0] - pos_v[0])**2 + (pos_u[1] - pos_v[1])**2)**0.5
        
        # Step 4: Analyze branches from heat sources
        logger.info("Step 2: Analyzing branches from heat sources")
        branch_info = self._analyze_branches(mst_graph, heat_source_nodes, building_nodes)
        
        long_branches = [b for b in branch_info if b['length'] >= min_branch_length_m]
        logger.info(f"Found {len(long_branches)} branches longer than {min_branch_length_m}m")
        
        # Step 5: Find candidate loop edges (edges in original graph but not in MST)
        logger.info("Step 3: Identifying candidate loop edges")
        mst_edges = set(mst_graph.edges())
        candidate_loops = []
        
        for u, v, data in G.edges(data=True):
            edge = (u, v) if (u, v) in mst_edges else (v, u)
            reverse_edge = (v, u)
            
            # Skip if edge already in MST
            if edge in mst_edges or reverse_edge in mst_edges:
                continue
            
            # Skip if either node not in MST (disconnected component)
            if not (mst_graph.has_node(u) and mst_graph.has_node(v)):
                continue
            
            # This edge would create a loop
            candidate_loops.append((u, v, data))
        
        logger.info(f"Found {len(candidate_loops)} candidate loop edges")
        
        if not candidate_loops:
            logger.warning("No candidate loops found - MST is already optimal")
            return mst_graph, {
                **mst_stats,
                "loops_added": 0,
                "candidate_loops_found": 0,
                "long_branches": len(long_branches)
            }
        
        # Step 6: Score and rank loops
        logger.info("Step 4: Scoring loops by hydraulic benefit")
        loop_scores = self._score_loops(mst_graph, candidate_loops, building_nodes, heat_source_nodes)
        
        # Sort by score (highest first)
        loop_scores.sort(key=lambda x: x['score'], reverse=True)
        
        logger.info(f"Top 5 loop scores: {[round(ls['score'], 2) for ls in loop_scores[:5]]}")
        
        # Step 7: Add loops iteratively
        logger.info(f"Step 5: Adding up to {max_loops_to_add} loops")
        loops_added = 0
        total_loop_length = 0
        added_edges = []
        
        for loop_info in loop_scores[:max_loops_to_add]:
            u, v, edge_data, score = loop_info['u'], loop_info['v'], loop_info['edge_data'], loop_info['score']
            avg_junctions = loop_info.get('avg_junctions', 0)
            paths_analyzed = loop_info.get('paths_analyzed', 0)
            
            # Add the loop edge to MST
            mst_graph.add_edge(u, v, **edge_data)
            loops_added += 1
            edge_length = edge_data.get('length', 0)
            total_loop_length += edge_length
            added_edges.append((u, v, edge_length, score, avg_junctions, paths_analyzed))
            
            if loops_added % 100 == 0:
                logger.info(f"Added {loops_added} loops so far...")
        
        logger.info(f"Loop addition complete: {loops_added} loops added")
        logger.info(f"Total loop length added: {total_loop_length:.2f}m")
        
        # Step 8: Verify network properties
        final_is_connected = nx.is_connected(mst_graph)
        final_components = nx.number_connected_components(mst_graph)
        
        # Check for actual loops (cycles)
        try:
            cycle_basis = nx.cycle_basis(mst_graph)
            num_cycles = len(cycle_basis)
            logger.info(f"Network now has {num_cycles} independent cycles")
        except:
            num_cycles = 0
            logger.warning("Could not compute cycle basis")
        
        # Step 9: Calculate comprehensive statistics
        original_length = sum(data.get('length', 0) for _, _, data in G.edges(data=True))
        mst_length = mst_stats.get('total_length', 0)
        final_length = sum(data.get('length', 0) for _, _, data in mst_graph.edges(data=True))
        
        stats = {
            "algorithm": "loop_enhanced_mst",
            "original_nodes": G.number_of_nodes(),
            "original_edges": G.number_of_edges(),
            "mst_nodes": mst_stats.get('mst_nodes', 0),
            "mst_edges": mst_stats.get('mst_edges', 0),
            "final_nodes": mst_graph.number_of_nodes(),
            "final_edges": mst_graph.number_of_edges(),
            "total_buildings": len(building_nodes),
            "total_heat_sources": len(heat_source_nodes),
            "connected_buildings": len([n for n in building_nodes if mst_graph.has_node(n)]),
            "branches_analyzed": len(branch_info),
            "long_branches": len(long_branches),
            "candidate_loops_found": len(candidate_loops),
            "loops_added": loops_added,
            "independent_cycles": num_cycles,
            "total_loop_length_m": round(total_loop_length, 2),
            "mst_length_m": round(mst_length, 2),
            "final_length_m": round(final_length, 2),
            "original_length_m": round(original_length, 2),
            "length_increase_from_mst": round(final_length - mst_length, 2),
            "length_increase_percentage": round((final_length - mst_length) / mst_length * 100, 2) if mst_length > 0 else 0,
            "is_connected": final_is_connected,
            "num_components": final_components,
            "top_loops_added": [{"u": u, "v": v, "length_m": round(length, 2), "score": round(score, 2),
                                "avg_junctions": round(junctions, 2), "paths_helped": paths} 
                               for u, v, length, score, junctions, paths in added_edges[:10]]
        }
        
        logger.info(f"Loop-Enhanced MST complete:")
        logger.info(f"  - MST length: {mst_length:.2f}m")
        logger.info(f"  - Final length: {final_length:.2f}m (+{final_length - mst_length:.2f}m, +{stats['length_increase_percentage']:.1f}%)")
        logger.info(f"  - Loops added: {loops_added}")
        logger.info(f"  - Independent cycles: {num_cycles}")
        
        return mst_graph, stats
    
    def _analyze_branches(self, G: nx.Graph, heat_source_nodes: List, building_nodes: List) -> List[Dict[str, Any]]:
        """
        Analyze all paths from heat sources to buildings to identify branch characteristics.
        
        Returns:
            List of branch info dicts with path length, buildings served, etc.
        """
        branches = []
        
        for heat_source in heat_source_nodes:
            for building in building_nodes:
                try:
                    path = nx.shortest_path(G, source=heat_source, target=building, weight='length')
                    path_length = nx.shortest_path_length(G, source=heat_source, target=building, weight='length')
                    
                    # Get heat demand for this building
                    heat_demand = G.nodes[building].get('heat_demand', 0.0)
                    try:
                        heat_demand = float(heat_demand)
                    except (ValueError, TypeError):
                        heat_demand = 0.0
                    
                    branches.append({
                        'heat_source': heat_source,
                        'building': building,
                        'path': path,
                        'length': path_length,
                        'heat_demand': heat_demand,
                        'path_nodes': len(path)
                    })
                except nx.NetworkXNoPath:
                    continue
        
        return branches
    
    def _score_loops(self, G: nx.Graph, candidate_loops: List[Tuple], 
                     building_nodes: List, heat_source_nodes: List) -> List[Dict[str, Any]]:
        """
        Score candidate loop edges by their potential to improve hydraulic performance.
        
        Scoring criteria:
        - Number of buildings that would gain a 2nd path
        - Total heat demand of buildings that would benefit
        - Number of junctions (nodes) on path between source and sink (fewer is better)
        - Centrality of loop in network
        
        Returns:
            List of scored loop dicts
        """
        scored_loops = []
        
        for u, v, edge_data in candidate_loops:
            edge_length = edge_data.get('length', 0)
            
            # Calculate how many buildings would benefit from this loop
            # A building benefits if adding this edge creates a 2nd path from heat source to building
            buildings_benefited = 0
            heat_demand_benefited = 0.0
            total_junctions_in_paths = 0  # Count junctions (nodes) in affected paths
            paths_analyzed = 0
            
            # Check if u and v are on paths from heat sources to buildings
            for building in building_nodes:
                for heat_source in heat_source_nodes:
                    try:
                        # Get current path
                        current_path = nx.shortest_path(G, source=heat_source, target=building)
                        
                        # Check if both u and v are on this path (different positions)
                        if u in current_path and v in current_path:
                            u_idx = current_path.index(u)
                            v_idx = current_path.index(v)
                            
                            # If u and v are on the same path with other nodes between them,
                            # adding edge (u,v) creates a loop that benefits this building
                            if abs(u_idx - v_idx) > 1:
                                buildings_benefited += 1
                                heat_demand = G.nodes[building].get('heat_demand', 0.0)
                                try:
                                    heat_demand = float(heat_demand)
                                except (ValueError, TypeError):
                                    heat_demand = 0.0
                                heat_demand_benefited += heat_demand
                                
                                # Count junctions (nodes) in the path segment between u and v
                                # This represents the number of "Abzweigungen" (branches/junctions) in the current path
                                segment_start = min(u_idx, v_idx)
                                segment_end = max(u_idx, v_idx)
                                num_junctions = segment_end - segment_start + 1  # Include both endpoints
                                total_junctions_in_paths += num_junctions
                                paths_analyzed += 1
                                
                                break  # Count each building only once
                    except nx.NetworkXNoPath:
                        continue
            
            # Calculate average number of junctions per affected path
            avg_junctions = total_junctions_in_paths / paths_analyzed if paths_analyzed > 0 else 1
            
            # Calculate score: benefit per junction (inverse of junctions = fewer junctions is better)
            # Higher score = more buildings/demand served per junction avoided
            # Using avg_junctions as denominator: fewer junctions in path = higher score
            if avg_junctions > 0:
                score = (buildings_benefited * 10.0 + heat_demand_benefited / 1000.0) / avg_junctions
            else:
                score = 0.0
            
            scored_loops.append({
                'u': u,
                'v': v,
                'edge_data': edge_data,
                'score': score,
                'buildings_benefited': buildings_benefited,
                'heat_demand_benefited': heat_demand_benefited,
                'edge_length': edge_length,
                'avg_junctions': avg_junctions,  # NEW: Average junctions in affected paths
                'paths_analyzed': paths_analyzed  # NEW: Number of paths this loop helps
            })
        
        return scored_loops


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
            "steiner_tree": SteinerTreePruner(),
            "loop_enhanced_mst": LoopEnhancedMSTPruner()
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
            # Import here to avoid circular import
            from utils.progress_tracker import progress_tracker
            
            # Use defaults from config if not provided
            if graphml_path is None:
                graphml_path = self.data_paths.get("network_graphml_path", "./data/heating_network.graphml")
            if output_path is None:
                output_path = self.data_paths.get("filtered_network_graphml_path", "./data/filtered_heating_network.graphml")
            if max_building_connection is None:
                max_building_connection = self.filter_settings.get("max_building_connection_distance", 100.0)
            
            progress_tracker.update(10, "Loading network data...")
            
            # Load GraphML
            if not Path(graphml_path).exists():
                return {"status": "error", "message": f"GraphML file not found: {graphml_path}"}
            
            G = nx.read_graphml(graphml_path)
            logger.info(f"Loaded GraphML with {G.number_of_nodes()} nodes and {G.number_of_edges()} edges")
            
            progress_tracker.update(20, "Analyzing network structure...")
            
            # Get initial statistics
            initial_stats = self._get_graph_statistics(G)
            
            # Store heat source information before optimization
            heat_source_nodes = [(node, data) for node, data in G.nodes(data=True) 
                                if data.get('node_type') == 'heat_source']
            logger.info(f"Found {len(heat_source_nodes)} heat sources to preserve during optimization")
            
            progress_tracker.update(30, "Filtering building connections...")
            
            # Apply building connection distance filter
            G_filtered, connection_stats = self._filter_building_connections(G, max_building_connection)
            
            progress_tracker.update(50, "Applying optimization algorithm...")
            
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
            
            progress_tracker.update(70, "Reconnecting heat sources...")
            
            # Reconnect heat sources to optimized network (exempt from distance limits)
            if heat_source_nodes:
                G_filtered = self._reconnect_heat_sources_post_optimization(G_filtered, heat_source_nodes)
                logger.info(f"Reconnected {len(heat_source_nodes)} heat sources to optimized network")
            
            progress_tracker.update(85, "Finalizing optimized network...")
            
            # Clean graph for GraphML compliance
            self._clean_graph_for_graphml(G_filtered)
            
            progress_tracker.update(95, "Saving optimized network...")
            
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
        """Filter building connections by maximum distance but NEVER remove building nodes. Heat source connections are exempt from distance limits."""
        G_filtered = G.copy()
        
        # Find building connections that exceed max distance (but exempt heat source connections)
        building_connections_to_remove = []
        
        for u, v, data in G_filtered.edges(data=True):
            if data.get('edge_type') == 'building_connection':
                edge_length = data.get('length', 0)
                if edge_length > max_distance:
                    building_connections_to_remove.append((u, v))
            # Note: heat_source_connection edges are exempt from distance limits
        
        # Remove only the connections, NOT the building nodes
        G_filtered.remove_edges_from(building_connections_to_remove)
        
        # Remove any orphaned street_connection nodes (but never building or heat source nodes)
        orphaned_nodes = []
        for node in G_filtered.nodes():
            node_type = G_filtered.nodes[node].get('node_type', '')
            if node_type == 'street_connection' and G_filtered.degree(node) == 0:
                orphaned_nodes.append(node)
        
        G_filtered.remove_nodes_from(orphaned_nodes)
        
        stats = {
            "removed_connections": len(building_connections_to_remove),
            "removed_building_nodes": 0,  # Never remove building nodes
            "removed_heat_source_nodes": 0,  # Never remove heat source nodes
            "removed_orphaned_nodes": len(orphaned_nodes),
            "max_distance_threshold": max_distance
        }
        
        logger.info(f"Removed {len(building_connections_to_remove)} building connections exceeding {max_distance}m")
        logger.info(f"Heat source connections are exempt from distance limits")
        logger.info(f"Removed 0 building/heat source nodes and {len(orphaned_nodes)} orphaned street nodes")
        
        return G_filtered, stats
    
    def _reconnect_heat_sources_post_optimization(self, G: nx.Graph, heat_source_nodes: List[Tuple]) -> nx.Graph:
        """
        Reconnect heat sources to optimized network using bisection method, no distance limits.
        Heat sources are ALWAYS connected to STREET SEGMENTS ONLY, never to building connections.
        
        Args:
            G: Optimized graph to modify
            heat_source_nodes: List of (node_id, node_data) tuples for heat sources
        
        Returns:
            Graph with heat sources reconnected
        """
        if not heat_source_nodes:
            return G
        
        logger.info(f"Reconnecting {len(heat_source_nodes)} heat sources to optimized network")
        
        # Get next available node ID (ensure it's an integer)
        if G.nodes:
            # Filter for numeric node IDs and find the maximum
            numeric_nodes = [node for node in G.nodes if isinstance(node, (int, float))]
            if numeric_nodes:
                next_node_id = int(max(numeric_nodes)) + 1
            else:
                # If no numeric nodes, start from a high number to avoid conflicts
                next_node_id = 100000
        else:
            next_node_id = 0
        successful_connections = 0
        failed_connections = 0
        
        for node_id, node_data in heat_source_nodes:
            # Skip if heat source is already in the optimized graph
            if G.has_node(node_id):
                logger.info(f"Heat source {node_id} already connected to optimized network")
                successful_connections += 1
                continue
            
            logger.info(f"Reconnecting heat source {node_id}")
            
            # Get heat source point from node data
            heat_source_point = Point(node_data.get('x', 0), node_data.get('y', 0))
            
            # Get ONLY street segment edges from optimized network - NEVER connect to building connections
            street_edges = [(u, v, data) for u, v, data in G.edges(data=True) 
                           if data.get('edge_type') == 'street_segment']
            
            if not street_edges:
                logger.warning(f"Heat source {node_id}: No street segments found in optimized network")
                failed_connections += 1
                continue
            
            # Create geometries for current edges
            edge_lines = []
            edge_info = []
            
            for u, v, data in street_edges:
                line = LineString([Point(G.nodes[u]['x'], G.nodes[u]['y']), 
                                 Point(G.nodes[v]['x'], G.nodes[v]['y'])])
                edge_lines.append(line)
                edge_info.append((u, v, data))
            
            edges_gs = gpd.GeoSeries(edge_lines)
            
            # Find the nearest edge to this heat source (no distance limit)
            distances = edges_gs.distance(heat_source_point)
            nearest_edge_idx = distances.idxmin()
            min_distance = distances.iloc[nearest_edge_idx]
            
            logger.info(f"Heat source {node_id}: Nearest edge distance = {min_distance:.2f}m (no distance limit)")
            
            u, v, edge_data = edge_info[nearest_edge_idx]
            closest_edge_line = edge_lines[nearest_edge_idx]
            
            # Create a new connection point on the nearest edge
            new_point_on_line = closest_edge_line.interpolate(closest_edge_line.project(heat_source_point))
            
            # Create new street connection node
            z_node_id = next_node_id
            G.add_node(z_node_id, 
                      x=new_point_on_line.x, 
                      y=new_point_on_line.y, 
                      node_type='street_connection', 
                      street_id=str(edge_data.get('street_id', 'unknown')))
            next_node_id += 1
            
            # Remove original edge and split into two segments
            if G.has_edge(u, v):
                G.remove_edge(u, v)
                
                # Calculate distances for new segments
                dist_u_z = Point(G.nodes[u]['x'], G.nodes[u]['y']).distance(new_point_on_line)
                dist_z_v = new_point_on_line.distance(Point(G.nodes[v]['x'], G.nodes[v]['y']))
                
                # Create copies of edge_data without the length key
                edge_data_copy = {k: v for k, v in edge_data.items() if k != 'length'}
                
                # Add new segments
                G.add_edge(u, z_node_id, length=dist_u_z, **edge_data_copy)
                G.add_edge(z_node_id, v, length=dist_z_v, **edge_data_copy)
            
            # Add heat source node back to the graph
            G.add_node(node_id, **node_data)
            
            # Connect heat source to the connection point
            dist_heat_source_z = heat_source_point.distance(new_point_on_line)
            G.add_edge(node_id, z_node_id, edge_type='heat_source_connection', length=dist_heat_source_z)
            
            logger.info(f"Heat source {node_id}: Connected to optimized network via connection point {z_node_id}")
            successful_connections += 1
        
        logger.info(f"Heat source reconnection complete: {successful_connections} successful, {failed_connections} failed")
        return G
    
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
