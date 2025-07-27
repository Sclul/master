"""Graph generator for creating GraphML from street coordinates."""
import logging
import json
from typing import Dict, Any, List, Tuple
from pathlib import Path
import geopandas as gpd  # type: ignore
import networkx as nx  # type: ignore
from shapely.geometry import LineString, Point  # type: ignore
import json
from heat_source_handler import HeatSourceHandler

logger = logging.getLogger(__name__)


class GraphGenerator:
    """Generates GraphML network with nodes for every street line string coordinate."""
    
    def __init__(self, config):
        """Initialize with configuration."""
        self.config = config
        self.data_paths = config.data_paths
        self.heat_source_handler = HeatSourceHandler(config)
        
        logger.info("GraphGenerator initialized")
    
    def generate_graph(self) -> Dict[str, Any]:
        """
        Generate GraphML network with nodes for every street coordinate.
        Automatically uses filtered buildings if they exist, otherwise falls back to regular buildings.

        Returns:
            Dict with status and file information
        """
        try:
            # Import here to avoid circular import
            from utils.progress_tracker import progress_tracker
            
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
            
            # Create network graph using u/v endpoints + all intermediate coordinates
            G = self._generate_street_network(streets_gdf)
            node_count = G.number_of_nodes()
            edge_count = G.number_of_edges()
            
            # Connect buildings to the network - this is where progress tracking happens
            # Check if filtered buildings exist, otherwise use regular buildings
            filtered_buildings_path = self.data_paths.get("filtered_buildings_path", "./data/filtered_buildings.geojson")
            regular_buildings_path = self.data_paths.get("buildings_path", "./data/buildings.geojson")
            
            if Path(filtered_buildings_path).exists():
                buildings_path = filtered_buildings_path
                logger.info(f"Using filtered buildings file: {filtered_buildings_path}")
            elif Path(regular_buildings_path).exists():
                buildings_path = regular_buildings_path
                logger.info(f"Using regular buildings file: {regular_buildings_path}")
            else:
                logger.warning(f"No buildings file found at {filtered_buildings_path} or {regular_buildings_path}, skipping building connections.")
                buildings_path = None
            
            if buildings_path:
                buildings_gdf = gpd.read_file(buildings_path)
                if not buildings_gdf.empty:
                    G, new_nodes, net_new_edges = self._connect_buildings_with_bisection(G, buildings_gdf)
                    node_count += new_nodes
                    edge_count += net_new_edges
                else:
                    logger.warning(f"Buildings file {buildings_path} is empty, skipping building connections.")

            # Connect heat sources to the network
            heat_sources_gdf = self.heat_source_handler.load_heat_sources()
            if heat_sources_gdf is not None and not heat_sources_gdf.empty:
                logger.info(f"Connecting {len(heat_sources_gdf)} heat sources to network")
                G, hs_new_nodes, hs_net_new_edges = self._connect_heat_sources_with_bisection(G, heat_sources_gdf)
                node_count += hs_new_nodes
                edge_count += hs_net_new_edges
            else:
                logger.info("No heat sources found, skipping heat source connections.")

            # Clean up None values before writing to GraphML
            self._clean_graph_for_graphml(G)
            
            # Save as GraphML
            output_path = self.data_paths.get("network_graphml_path", "./data/heating_network.graphml")
            output_file = Path(output_path)
            output_file.parent.mkdir(parents=True, exist_ok=True)
            
            nx.write_graphml(G, output_path)
            
            logger.info(f"Graph network GraphML saved to: {output_path}")
            logger.info(f"Network contains {node_count} nodes and {edge_count} edges")
            
            return {
                "status": "success",
                "message": f"Graph network generated with {node_count} nodes and {edge_count} edges",
                "file_path": output_path,
                "total_nodes": node_count,
                "total_edges": edge_count
            }
            
        except Exception as e:
            logger.error(f"Error generating graph network: {e}")
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
        Connects buildings to the nearest street segment using true bisection method.
        Each building connection splits the nearest street segment into two new segments.
        """
        from utils.progress_tracker import progress_tracker
        
        new_nodes_added = 0
        net_edges_added = 0
        
        next_node_id = max(G.nodes) + 1 if G.nodes else 0
        successful_connections = 0
        failed_connections = 0
        total_buildings = len(buildings_gdf)

        for idx, building in buildings_gdf.iterrows():
            logger.info(f"Processing building {idx}")
            
            # Update progress based on building connection percentage
            total_processed = successful_connections + failed_connections
            progress_percent = int((total_processed / total_buildings) * 100)
            progress_tracker.update(progress_percent, f"Connected {successful_connections}/{total_buildings} buildings ({progress_percent}%)")
            
            # Use representative_point coordinates from building properties instead of centroid
            rep_point_data = building.get('representative_point')
            
            # Try to extract coordinates from representative_point
            building_point = None
            if rep_point_data and isinstance(rep_point_data, str):
                try:
                    parsed_data = json.loads(rep_point_data)
                    if isinstance(parsed_data, dict) and 'coordinates' in parsed_data:
                        coords = parsed_data['coordinates']
                        if len(coords) >= 2:
                            building_point = Point(coords[0], coords[1])
                            logger.info(f"Building {idx}: Using representative point {coords}")
                except (json.JSONDecodeError, KeyError, IndexError) as e:
                    logger.warning(f"Building {idx}: Error parsing representative_point: {e}")
            
            # Fallback to centroid if representative_point is not available or invalid
            if building_point is None:
                building_point = building.geometry.centroid
                logger.info(f"Building {idx}: Falling back to centroid {building_point.x}, {building_point.y}")
            
            # Get current street edges (this updates as we add new segments)
            street_edges = [(u, v, data) for u, v, data in G.edges(data=True) if data.get('edge_type') == 'street_segment']
            
            if not street_edges:
                logger.warning(f"Building {idx}: No street segments found in current graph")
                failed_connections += 1
                # Update progress even for failed connections
                total_processed = successful_connections + failed_connections
                progress_percent = int((total_processed / total_buildings) * 100)
                progress_tracker.update(progress_percent, f"Connected {successful_connections}/{total_buildings} buildings ({progress_percent}%)")
                continue
            
            # Create geometries for current street edges
            edge_lines = []
            edge_info = []
            for u, v, data in street_edges:
                line = LineString([Point(G.nodes[u]['x'], G.nodes[u]['y']), Point(G.nodes[v]['x'], G.nodes[v]['y'])])
                edge_lines.append(line)
                edge_info.append((u, v, data))
            
            edges_gs = gpd.GeoSeries(edge_lines)
            
            # Find the nearest street segment to this building
            distances = edges_gs.distance(building_point)
            nearest_edge_idx = distances.idxmin()
            min_distance = distances.iloc[nearest_edge_idx]
            
            logger.info(f"Building {idx}: Nearest edge distance = {min_distance:.2f}m")
            
            u, v, edge_data = edge_info[nearest_edge_idx]
            closest_edge_line = edge_lines[nearest_edge_idx]
            
            # Step 1: Identify the closest segment (B-C in the example)
            logger.info(f"Building {idx}: Connecting to segment {u}-{v}")
            
            # Step 2: Create a new connection point (Z in the example)
            new_point_on_line = closest_edge_line.interpolate(closest_edge_line.project(building_point))
            
            z_node_id = next_node_id
            G.add_node(z_node_id, 
                      x=new_point_on_line.x, 
                      y=new_point_on_line.y, 
                      node_type='street_connection', 
                      street_id=edge_data.get('street_id', 'unknown'))
            next_node_id += 1
            new_nodes_added += 1
            
            # Step 3: Restructure the network - Remove original segment B-C
            if not G.has_edge(u, v):
                logger.warning(f"Building {idx}: Edge {u}-{v} not found in graph")
                failed_connections += 1
                # Update progress even for failed connections
                total_processed = successful_connections + failed_connections
                progress_percent = int((total_processed / total_buildings) * 100)
                progress_tracker.update(progress_percent, f"Connected {successful_connections}/{total_buildings} buildings ({progress_percent}%)")
                continue
            
            # Remove the original edge B-C
            G.remove_edge(u, v)
            
            # Step 4: Split into two segments: B-Z and Z-C
            dist_u_z = Point(G.nodes[u]['x'], G.nodes[u]['y']).distance(new_point_on_line)
            dist_z_v = new_point_on_line.distance(Point(G.nodes[v]['x'], G.nodes[v]['y']))
            
            # Create copies of edge_data without the length key to avoid conflicts
            edge_data_copy = {k: v for k, v in edge_data.items() if k != 'length'}
            
            # Add new segments B-Z and Z-C
            G.add_edge(u, z_node_id, length=dist_u_z, **edge_data_copy)
            G.add_edge(z_node_id, v, length=dist_z_v, **edge_data_copy)
            
            # Net change: -1 original edge + 2 new edges = +1 edge
            net_edges_added += 1;
            
            logger.info(f"Building {idx}: Split edge {u}-{v} into {u}-{z_node_id} and {z_node_id}-{v}")
            
            # Step 5: Connect the building to the new node Z
            building_node_id = next_node_id
            
            # Get heat demand from building data
            heat_demand = building.get('heat_demand', 0.0)
            if heat_demand is None or heat_demand == '':
                heat_demand = 0.0
            else:
                try:
                    heat_demand = float(heat_demand)
                except (ValueError, TypeError):
                    heat_demand = 0.0
            
            G.add_node(building_node_id, 
                      x=building_point.x, 
                      y=building_point.y, 
                      node_type='building', 
                      osmid=building.get('osmid', 'unknown'),
                      heat_demand=heat_demand)
            next_node_id += 1
            new_nodes_added += 1
            
            # Connect building to the connection point Z
            dist_building_z = building_point.distance(new_point_on_line)
            G.add_edge(building_node_id, z_node_id, edge_type='building_connection', length=dist_building_z)
            net_edges_added += 1
            
            logger.info(f"Building {idx}: Connected building {building_node_id} to connection point {z_node_id}")
            successful_connections += 1
            
            # Update progress based on buildings connected (0% to 100% range)
            progress_percent = int((successful_connections / total_buildings) * 100)
            progress_tracker.update(progress_percent, f"Connected {successful_connections}/{total_buildings} buildings ({progress_percent}%)")

        logger.info(f"Building connections complete:")
        logger.info(f"  - Successful connections: {successful_connections}")
        logger.info(f"  - Failed connections: {failed_connections}")
        logger.info(f"  - Total buildings processed: {len(buildings_gdf)}")
        logger.info(f"  - Nodes added: {new_nodes_added}")
        logger.info(f"  - Net edges added: {net_edges_added}")
        
        # Verify connectivity after building connections
        if G.number_of_nodes() > 0:
            components = list(nx.connected_components(G))
            logger.info(f"After building connections: {len(components)} connected components")
            
            building_nodes = [n for n, data in G.nodes(data=True) if data.get('node_type') == 'building']
            for i, component in enumerate(components):
                buildings_in_component = [n for n in component if n in building_nodes]
                logger.info(f"  Component {i}: {len(component)} nodes, {len(buildings_in_component)} buildings")

        return G, new_nodes_added, net_edges_added

    def _connect_heat_sources_with_bisection(self, G: nx.Graph, heat_sources_gdf: gpd.GeoDataFrame) -> Tuple[nx.Graph, int, int]:
        """
        Connects heat sources to the nearest street segment using true bisection method.
        Each heat source connection splits the nearest street segment into two new segments.
        Heat sources are treated like buildings but with different node attributes.
        """
        new_nodes_added = 0
        net_edges_added = 0
        
        next_node_id = max(G.nodes) + 1 if G.nodes else 0
        successful_connections = 0
        failed_connections = 0

        for idx, heat_source in heat_sources_gdf.iterrows():
            logger.info(f"Processing heat source {idx}")
            
            # Get heat source point from geometry
            heat_source_point = heat_source.geometry
            if not isinstance(heat_source_point, Point):
                # If geometry is not a Point, try to get centroid
                heat_source_point = heat_source.geometry.centroid
                logger.info(f"Heat source {idx}: Using centroid {heat_source_point.x}, {heat_source_point.y}")
            else:
                logger.info(f"Heat source {idx}: Using point {heat_source_point.x}, {heat_source_point.y}")
            
            # Get current street edges (this updates as we add new segments)
            street_edges = [(u, v, data) for u, v, data in G.edges(data=True) if data.get('edge_type') == 'street_segment']
            
            if not street_edges:
                logger.warning(f"Heat source {idx}: No street segments found in current graph")
                failed_connections += 1
                continue
            
            # Create geometries for current street edges
            edge_lines = []
            edge_info = []
            for u, v, data in street_edges:
                line = LineString([Point(G.nodes[u]['x'], G.nodes[u]['y']), Point(G.nodes[v]['x'], G.nodes[v]['y'])])
                edge_lines.append(line)
                edge_info.append((u, v, data))
            
            edges_gs = gpd.GeoSeries(edge_lines)
            
            # Find the nearest street segment to this heat source
            distances = edges_gs.distance(heat_source_point)
            nearest_edge_idx = distances.idxmin()
            min_distance = distances.iloc[nearest_edge_idx]
            
            logger.info(f"Heat source {idx}: Nearest edge distance = {min_distance:.2f}m")
            
            u, v, edge_data = edge_info[nearest_edge_idx]
            closest_edge_line = edge_lines[nearest_edge_idx]
            
            # Step 1: Identify the closest segment (B-C in the example)
            logger.info(f"Heat source {idx}: Connecting to segment {u}-{v}")
            
            # Step 2: Create a new connection point (Z in the example)
            new_point_on_line = closest_edge_line.interpolate(closest_edge_line.project(heat_source_point))
            
            z_node_id = next_node_id
            G.add_node(z_node_id, 
                      x=new_point_on_line.x, 
                      y=new_point_on_line.y, 
                      node_type='street_connection', 
                      street_id=edge_data.get('street_id', 'unknown'))
            next_node_id += 1
            new_nodes_added += 1
            
            # Step 3: Restructure the network - Remove original segment B-C
            if not G.has_edge(u, v):
                logger.warning(f"Heat source {idx}: Edge {u}-{v} not found in graph")
                failed_connections += 1
                continue
            
            # Remove the original edge B-C
            G.remove_edge(u, v)
            
            # Step 4: Split into two segments: B-Z and Z-C
            dist_u_z = Point(G.nodes[u]['x'], G.nodes[u]['y']).distance(new_point_on_line)
            dist_z_v = new_point_on_line.distance(Point(G.nodes[v]['x'], G.nodes[v]['y']))
            
            # Create copies of edge_data without the length key to avoid conflicts
            edge_data_copy = {k: v for k, v in edge_data.items() if k != 'length'}
            
            # Add new segments B-Z and Z-C
            G.add_edge(u, z_node_id, length=dist_u_z, **edge_data_copy)
            G.add_edge(z_node_id, v, length=dist_z_v, **edge_data_copy)
            
            # Net change: -1 original edge + 2 new edges = +1 edge
            net_edges_added += 1
            
            logger.info(f"Heat source {idx}: Split edge {u}-{v} into {u}-{z_node_id} and {z_node_id}-{v}")
            
            # Step 5: Connect the heat source to the new node Z
            heat_source_node_id = next_node_id
            
            # Get heat source properties
            heat_source_id = heat_source.get('id', f'hs_unknown_{idx}')
            annual_heat_production = heat_source.get('annual_heat_production', 0.0)
            heat_source_type = heat_source.get('heat_source_type', 'Generic')
            
            # Ensure numeric values
            try:
                annual_heat_production = float(annual_heat_production) if annual_heat_production is not None else 0.0
            except (ValueError, TypeError):
                annual_heat_production = 0.0
            
            G.add_node(heat_source_node_id, 
                      x=heat_source_point.x, 
                      y=heat_source_point.y, 
                      node_type='heat_source', 
                      heat_source_id=heat_source_id,
                      annual_heat_production=annual_heat_production,
                      heat_source_type=heat_source_type)
            next_node_id += 1
            new_nodes_added += 1
            
            # Connect heat source to the connection point Z
            dist_heat_source_z = heat_source_point.distance(new_point_on_line)
            G.add_edge(heat_source_node_id, z_node_id, edge_type='heat_source_connection', length=dist_heat_source_z)
            net_edges_added += 1
            
            logger.info(f"Heat source {idx}: Connected heat source {heat_source_node_id} to connection point {z_node_id}")
            successful_connections += 1

        logger.info(f"Heat source connections complete:")
        logger.info(f"  - Successful connections: {successful_connections}")
        logger.info(f"  - Failed connections: {failed_connections}")
        logger.info(f"  - Total heat sources processed: {len(heat_sources_gdf)}")
        logger.info(f"  - Nodes added: {new_nodes_added}")
        logger.info(f"  - Net edges added: {net_edges_added}")
        
        # Verify connectivity after heat source connections
        if G.number_of_nodes() > 0:
            components = list(nx.connected_components(G))
            logger.info(f"After heat source connections: {len(components)} connected components")
            
            heat_source_nodes = [n for n, data in G.nodes(data=True) if data.get('node_type') == 'heat_source']
            for i, component in enumerate(components):
                heat_sources_in_component = [n for n in component if n in heat_source_nodes]
                logger.info(f"  Component {i}: {len(component)} nodes, {len(heat_sources_in_component)} heat sources")

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
    
    def _generate_street_network(self, streets_gdf: gpd.GeoDataFrame) -> nx.Graph:
        """Generate single connected street network using coordinate-based nodes."""
        G = nx.Graph()
        
        logger.info(f"Processing {len(streets_gdf)} street features for coordinate-based network")
        
        # Phase 1: Extract all unique coordinates and create mapping
        coord_to_node = {}
        node_id = 0
        
        # First pass: collect all unique coordinates
        for idx, street in streets_gdf.iterrows():
            if not isinstance(street.geometry, LineString):
                logger.warning(f"Street {idx}: Invalid geometry type")
                continue
                
            coords = list(street.geometry.coords)
            for x, y in coords:
                coord_key = (x, y)
                if coord_key not in coord_to_node:
                    coord_to_node[coord_key] = node_id
                    node_id += 1
        
        logger.info(f"Found {len(coord_to_node)} unique coordinates")
        
        # Phase 2: Create nodes for all unique coordinates
        for (x, y), node_id in coord_to_node.items():
            G.add_node(node_id,
                      x=x,
                      y=y,
                      node_type='coordinate')
        
        # Phase 3: Create edges following street geometries
        edge_count = 0
        for idx, street in streets_gdf.iterrows():
            if not isinstance(street.geometry, LineString):
                continue
                
            coords = list(street.geometry.coords)
            if len(coords) < 2:
                continue
                
            street_name = street.get('name', f'Street_{idx}')
            highway_type = street.get('highway', 'residential')
            
            # Create edges between consecutive coordinates
            for i in range(len(coords) - 1):
                source_coord = coords[i]
                target_coord = coords[i + 1]
                
                source_node = coord_to_node[source_coord]
                target_node = coord_to_node[target_coord]
                
                # Calculate edge length
                point1 = Point(source_coord)
                point2 = Point(target_coord)
                edge_length = point1.distance(point2)
                
                G.add_edge(source_node, target_node,
                          edge_type='street_segment',
                          street_id=str(idx),
                          street_name=street_name,
                          highway=highway_type,
                          length=edge_length,
                          segment_index=i)
                
                edge_count += 1
        
        logger.info(f"Generated coordinate-based network: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")
        
        # Phase 4: Verify connectivity
        if G.number_of_nodes() > 0:
            components = list(nx.connected_components(G))
            logger.info(f"Network has {len(components)} connected components")
            if len(components) == 1:
                logger.info("✅ Successfully created single connected network!")
            else:
                largest_component = max(components, key=len)
                logger.info(f"Largest component: {len(largest_component)} nodes")
                for i, component in enumerate(components):
                    logger.info(f"Component {i}: {len(component)} nodes")
        
        return G
