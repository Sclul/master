"""District heating network generation functionality."""
from typing import Dict, Any, Optional, Tuple, List
from pathlib import Path
import unicodedata
from thefuzz import fuzz # type: ignore
import pandas as pd  # type: ignore
import geopandas as gpd  # type: ignore
from shapely.geometry import Point, LineString, MultiLineString  # type: ignore
from shapely.ops import nearest_points  # type: ignore
import logging  # type: ignore
import networkx as nx # type: ignore

logger = logging.getLogger(__name__)


class DistrictHeatingNetwork:
    """Handles district heating network generation and optimization."""
    
    def __init__(self, config):
        """Initialize with configuration."""
        self.config = config
        self.data_paths = config.data_paths
        
        # Network generation settings
        self.network_settings = config.config.get("network_generation", {})
        
        logger.info("DistrictHeatingNetwork initialized")
    
    def connect_buildings_to_streets(self, use_filtered_buildings: bool = True) -> Dict[str, Any]:
        """
        Connect each building to its corresponding street with the shortest connection.
        
        Args:
            use_filtered_buildings: If True, use filtered buildings; otherwise use all buildings
            
        Returns:
            Dict with status and file path information
        """
        try:
            # Load buildings data
            if use_filtered_buildings:
                buildings_path = self.data_paths["filtered_buildings_path"]
                logger.info("Using filtered buildings for network generation")
            else:
                buildings_path = self.data_paths["buildings_path"]
                logger.info("Using all buildings for network generation")
            
            # Check if buildings file exists
            if not Path(buildings_path).exists():
                return {
                    "status": "error",
                    "message": f"Buildings file not found: {buildings_path}"
                }
            
            # Load streets data
            streets_path = self.data_paths["streets_path"]
            if not Path(streets_path).exists():
                return {
                    "status": "error",
                    "message": f"Streets file not found: {streets_path}"
                }
            
            # Load geodataframes
            buildings_gdf = gpd.read_file(buildings_path)
            streets_gdf = gpd.read_file(streets_path)
            
            if buildings_gdf.empty:
                return {
                    "status": "error",
                    "message": "No buildings data available"
                }
            
            if streets_gdf.empty:
                return {
                    "status": "error",
                    "message": "No streets data available"
                }
            
            logger.info(f"Loaded {len(buildings_gdf)} buildings and {len(streets_gdf)} streets")
            
            # Generate connections
            connection_lines = self._generate_building_street_connections(buildings_gdf, streets_gdf)
            
            if not connection_lines:
                return {
                    "status": "error",
                    "message": "No connections could be generated"
                }
            
            # Save the network as GraphML with building and junction nodes
            graphml_path = self.data_paths.get("network_graphml_path", "./data/heating_network.graphml")
            self._save_network_as_graphml(buildings_gdf, streets_gdf, connection_lines, graphml_path)
            
            logger.info(f"Network GraphML saved to: {graphml_path}")
            logger.info(f"Generated {len(connection_lines)} building connections")
            
            return {
                "status": "success",
                "message": f"Network generated with {len(connection_lines)} building connections",
                "graphml_path": graphml_path,
                "connections_count": len(connection_lines)
            }
            
        except Exception as e:
            logger.error(f"Error generating district heating network: {e}")
            return {
                "status": "error",
                "message": str(e)
            }
    
    def _generate_building_street_connections(self, buildings_gdf: gpd.GeoDataFrame,
                                           streets_gdf: gpd.GeoDataFrame) -> List[Dict[str, Any]]:
        """
        Generate connection lines from buildings to their corresponding streets.
        
        Returns:
            List of connection line features with properties
        """
        connection_lines = []
        no_address_count = 0
        no_matching_street_count = 0
        successful_matches = 0

        # Create a spatial index for all streets
        all_streets_sindex = streets_gdf.sindex
        
        for idx, building in buildings_gdf.iterrows():
            try:
                building_street = self._extract_building_street(building)
                building_point = self._get_building_representative_point(building)

                if not building_point:
                    continue

                shortest_connection = None
                
                if building_street:
                    matching_streets = self._find_matching_streets(building_street, streets_gdf)
                    
                    if not matching_streets.empty:
                        # Connect to the closest of the matched streets
                        shortest_connection = self._find_shortest_connection(building_point, matching_streets)
                        
                        if shortest_connection:
                            # Check if the connection point is a junction
                            connection_point = Point(shortest_connection['geometry'].coords[1])
                            
                            # A junction is a point where multiple streets meet. We can identify it if the connection
                            # point is an endpoint for multiple streets in the full street network.
                            possible_matches_indices = list(all_streets_sindex.intersection(connection_point.bounds))
                            possible_matches = streets_gdf.iloc[possible_matches_indices]
                            
                            # Find streets that actually contain the connection point
                            intersecting_streets = possible_matches[possible_matches.intersects(connection_point)]

                            # If more than one street intersects, it's a junction.
                            if len(intersecting_streets) > 1:
                                logger.debug(f"Junction detected for building {idx} at matched street. Finding alternative.")
                                
                                # Find the two nearest streets to the building
                                nearest_streets_indices = all_streets_sindex.nearest(building_point, return_all=True, max_distance=None, return_distance=False)
                                # The returned indices are for the input geometries, we need to map them back to the original GeoDataFrame indices
                                nearest_geometries_indices = nearest_streets_indices[1]
                                nearest_streets = streets_gdf.iloc[nearest_geometries_indices[:2]]
                                
                                # The matched street is one of them, so we find the *other* one.
                                matched_street_id = shortest_connection['properties']['street_id']
                                alternative_street = nearest_streets[nearest_streets.index.astype(str) != matched_street_id]

                                if not alternative_street.empty:
                                    # Recalculate shortest connection to the alternative street
                                    alternative_connection = self._find_shortest_connection(building_point, alternative_street)
                                    if alternative_connection:
                                        logger.debug(f"Found alternative connection for building {idx} to avoid junction.")
                                        shortest_connection = alternative_connection
                                        shortest_connection["properties"]["connection_type"] = "building_to_alternative_street"
                                    else:
                                        # Keep original connection if alternative fails
                                        shortest_connection["properties"]["connection_type"] = "building_to_matching_street_at_junction"
                                else:
                                    shortest_connection["properties"]["connection_type"] = "building_to_matching_street_at_junction"
                            else:
                                shortest_connection["properties"]["connection_type"] = "building_to_matching_street"

                            shortest_connection["properties"]["building_street"] = building_street
                            connection_lines.append(shortest_connection)
                            successful_matches += 1
                        else:
                            no_matching_street_count += 1
                    else:
                        no_matching_street_count += 1
                else:
                    no_address_count += 1

                # Fallback for buildings with no address, or where no match was found
                if not shortest_connection:
                    logger.debug(f"Building {idx} (street: {building_street or 'N/A'}) using fallback to closest street.")
                    fallback_connection = self._find_shortest_connection(building_point, streets_gdf)
                    if fallback_connection:
                        fallback_connection["properties"]["connection_type"] = "building_to_closest_street"
                        fallback_connection["properties"]["building_street"] = building_street or "N/A"
                        connection_lines.append(fallback_connection)

            except Exception as e:
                logger.warning(f"Error processing building {idx}: {e}", exc_info=True)
                continue
        
        logger.info(f"Generated {len(connection_lines)} building-to-street connections")
        logger.info(f"Street name matches: {successful_matches}, No address: {no_address_count}, No matching street: {no_matching_street_count}")
        return connection_lines
    
    def _pre_process_street_names(self, streets_gdf: gpd.GeoDataFrame) -> pd.Series:
        """Pre-process and cache street names for faster matching."""
        if not hasattr(self, '_cached_street_names'):
            self._cached_street_names: Dict[str, pd.Series] = {}

        # Create a unique cache key based on the streets GeoDataFrame's hash
        try:
            cache_key = pd.util.hash_pandas_object(streets_gdf).sum()
        except TypeError:
            # Fallback for non-hashable types
            cache_key = str(streets_gdf)

        if cache_key in self._cached_street_names:
            return self._cached_street_names[cache_key]

        street_fields = ['name', 'addr:street']
        all_street_names = []

        for field in street_fields:
            if field in streets_gdf.columns:
                # Explode lists/tuples into separate rows and handle NaNs
                streets_exploded = streets_gdf.explode(field)
                
                # Normalize names
                normalized_names = streets_exploded[field].dropna().apply(self._normalize_street_name)
                all_street_names.append(normalized_names)

        if not all_street_names:
            # Return an empty Series with the correct index
            return pd.Series(dtype=str, index=streets_gdf.index)

        # Concatenate all normalized names and drop duplicates at the same index
        processed_series = pd.concat(all_street_names).groupby(level=0).first()
        
        # Cache the result
        self._cached_street_names[cache_key] = processed_series
        
        return processed_series

    def _extract_building_street(self, building_row: pd.Series) -> Optional[str]:
        """Extract street name from building data."""
        # Check common street address fields
        street_fields = ['addr:street', 'street', 'addr_street', 'Street']
        
        for field in street_fields:
            if field in building_row and pd.notna(building_row[field]):
                return str(building_row[field])
        
        return None
    
    def _normalize_street_name(self, street_name: str) -> str:
        """Normalize street name for better matching."""
        if not isinstance(street_name, str):
            return ""
        name = street_name.lower().strip()
        name = unicodedata.normalize('NFC', name)
        name = name.replace('ß', 'ss')
        name = name.replace('str.', 'strasse')
        name = name.replace('str ', 'strasse ')
        name = name.replace('straße', 'strasse')
        return name

    def _find_matching_streets(self, building_street: str, streets_gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
        """Find streets that match the building's street address using fuzzy matching."""
        
        # Normalize building street name
        building_street_lower = self._normalize_street_name(building_street)
        
        # Get pre-processed street names
        normalized_street_names = self._pre_process_street_names(streets_gdf)
        
        if normalized_street_names.empty:
            return gpd.GeoDataFrame()

        # Calculate fuzzy scores
        scores = normalized_street_names.apply(
            lambda street_name: fuzz.partial_ratio(building_street_lower, street_name)
        )
        
        # Find the best match
        best_match_idx = scores.idxmax()
        best_match_score = scores.max()

        if best_match_score > 85:  # Use a more permissive threshold with partial_ratio
            logger.debug(f"Best fuzzy match for '{building_street_lower}': '{normalized_street_names.loc[best_match_idx]}' (Score: {best_match_score})")
            return streets_gdf.loc[[best_match_idx]]
            
        return gpd.GeoDataFrame()

    def _get_building_representative_point(self, building_row: pd.Series) -> Optional[Point]:
        """Get the representative point of a building's geometry."""
        try:
            # First try to use the pre-computed representative_point from the geojson
            if 'representative_point' in building_row and pd.notna(building_row['representative_point']):
                rep_point_data = building_row['representative_point']
                
                # Handle the case where representative_point is stored as a dictionary
                if isinstance(rep_point_data, dict) and 'coordinates' in rep_point_data:
                    coords = rep_point_data['coordinates']
                    if len(coords) >= 2:
                        return Point(coords[0], coords[1])
                
                # Handle the case where it's already a Point geometry
                elif hasattr(rep_point_data, 'x') and hasattr(rep_point_data, 'y'):
                    return rep_point_data
            
            # Fallback to geometry centroid if representative_point is not available
            geometry = building_row.geometry
            if geometry and not geometry.is_empty:
                # Use centroid for polygons, or the point itself for points
                if hasattr(geometry, 'centroid'):
                    return geometry.centroid
                else:
                    return geometry
                    
        except Exception as e:
            logger.debug(f"Error getting building representative point: {e}")
        
        return None
    
    def _find_shortest_connection(self, building_point: Point, 
                                streets_gdf: gpd.GeoDataFrame) -> Optional[Dict[str, Any]]:
        """Find the shortest connection from building to matching streets."""
        shortest_distance = float('inf')
        best_connection = None
        
        for idx, street in streets_gdf.iterrows():
            try:
                street_geometry = street.geometry
                if not street_geometry or street_geometry.is_empty:
                    continue
                
                # Find nearest points between building and street
                nearest_geoms = nearest_points(building_point, street_geometry)
                connection_line = LineString([nearest_geoms[0], nearest_geoms[1]])
                
                distance = connection_line.length
                
                if distance < shortest_distance:
                    shortest_distance = distance
                    
                    # Get street name safely
                    street_name = "Unknown"
                    for name_field in ['name', 'highway', 'street_name', 'addr:street']:
                        if name_field in street.index and pd.notna(street[name_field]):
                            street_name = str(street[name_field])
                            break
                    
                    best_connection = {
                        "geometry": connection_line,
                        "properties": {
                            "connection_type": "building_to_street",
                            "distance": round(distance, 2),
                            "street_name": street_name,
                            "street_id": str(idx)
                        }
                    }
                    
            except Exception as e:
                logger.debug(f"Error calculating connection to street {idx}: {e}")
                continue
        
        return best_connection

    def _save_network_as_graphml(self, buildings_gdf: gpd.GeoDataFrame, 
                               streets_gdf: gpd.GeoDataFrame,
                               connection_lines: List[Dict[str, Any]], 
                               graphml_path: str) -> None:
        """Save the heating network as GraphML with building and junction nodes."""
        try:
            # Create a directed graph
            G = nx.DiGraph()
            
            # Create GeoDataFrame for connections if they exist
            if connection_lines:
                connection_geometries = [conn["geometry"] for conn in connection_lines]
                connection_properties = [conn["properties"] for conn in connection_lines]
                connections_gdf = gpd.GeoDataFrame(
                    connection_properties, 
                    geometry=connection_geometries,
                    crs=streets_gdf.crs
                )
            else:
                connections_gdf = gpd.GeoDataFrame()
            
            # Node ID counters
            node_id = 0
            building_node_mapping = {}
            street_junction_mapping = {}
            
            # Add building nodes
            for idx, building in buildings_gdf.iterrows():
                try:
                    # Get building representative point
                    building_point = self._get_building_representative_point(building)
                    
                    if building_point:
                        # Extract building properties
                        heat_demand = building.get('heat_demand', 0) if 'heat_demand' in building.index else 0
                        street_address = self._extract_building_street(building) or "Unknown"
                        
                        # Add building node
                        G.add_node(node_id,
                                 node_type='building',
                                 building_id=str(idx),
                                 x=building_point.x,
                                 y=building_point.y,
                                 heat_demand=float(heat_demand) if pd.notna(heat_demand) else 0.0,
                                 street_address=street_address,
                                 geometry_type=str(type(building.geometry).__name__) if hasattr(building, 'geometry') else 'Unknown'
                                )
                        
                        building_node_mapping[idx] = node_id
                        node_id += 1
                        
                except Exception as e:
                    logger.debug(f"Error processing building {idx} for GraphML: {e}")
                    continue
            
            # Create junction nodes from street intersections
            junction_coords = set()
            
            # Collect all street endpoints and intersections
            for idx, street in streets_gdf.iterrows():
                try:
                    geometry = street.geometry
                    if geometry and not geometry.is_empty:
                        if isinstance(geometry, LineString):
                            # Add start and end points
                            start_point = Point(geometry.coords[0])
                            end_point = Point(geometry.coords[-1])
                            junction_coords.add((round(start_point.x, 6), round(start_point.y, 6)))
                            junction_coords.add((round(end_point.x, 6), round(end_point.y, 6)))
                        elif isinstance(geometry, MultiLineString):
                            # Handle MultiLineString
                            for line in geometry.geoms:
                                start_point = Point(line.coords[0])
                                end_point = Point(line.coords[-1])
                                junction_coords.add((round(start_point.x, 6), round(start_point.y, 6)))
                                junction_coords.add((round(end_point.x, 6), round(end_point.y, 6)))
                except Exception as e:
                    logger.debug(f"Error processing street {idx} for junctions: {e}")
                    continue
            
            # Add junction nodes
            for coord in junction_coords:
                G.add_node(node_id,
                         node_type='junction',
                         junction_id=f"j_{node_id}",
                         x=coord[0],
                         y=coord[1],
                         degree=0  # Will be updated based on connections
                        )
                street_junction_mapping[coord] = node_id
                node_id += 1
            
            # Add street edges between junctions
            for idx, street in streets_gdf.iterrows():
                try:
                    geometry = street.geometry
                    if geometry and not geometry.is_empty:
                        street_name = street.get('name', f"street_{idx}")
                        highway_type = street.get('highway', 'unknown')
                        length = geometry.length if hasattr(geometry, 'length') else 0
                        
                        if isinstance(geometry, LineString):
                            start_coord = (round(geometry.coords[0][0], 6), round(geometry.coords[0][1], 6))
                            end_coord = (round(geometry.coords[-1][0], 6), round(geometry.coords[-1][1], 6))
                            
                            start_node = street_junction_mapping.get(start_coord)
                            end_node = street_junction_mapping.get(end_coord)
                            
                            if start_node is not None and end_node is not None and start_node != end_node:
                                G.add_edge(start_node, end_node,
                                         edge_type='street',
                                         street_id=str(idx),
                                         name=str(street_name),
                                         highway=str(highway_type),
                                         length=float(length),
                                         geometry_wkt=geometry.wkt
                                        )
                        elif isinstance(geometry, MultiLineString):
                            # Handle MultiLineString by connecting sequential line segments
                            for line in geometry.geoms:
                                start_coord = (round(line.coords[0][0], 6), round(line.coords[0][1], 6))
                                end_coord = (round(line.coords[-1][0], 6), round(line.coords[-1][1], 6))
                                
                                start_node = street_junction_mapping.get(start_coord)
                                end_node = street_junction_mapping.get(end_coord)
                                
                                if start_node is not None and end_node is not None and start_node != end_node:
                                    G.add_edge(start_node, end_node,
                                             edge_type='street',
                                             street_id=str(idx),
                                             name=str(street_name),
                                             highway=str(highway_type),
                                             length=float(line.length),
                                             geometry_wkt=line.wkt
                                            )
                except Exception as e:
                    logger.debug(f"Error processing street edge {idx}: {e}")
                    continue
            
            # Add building-to-street connection edges
            for idx, connection in connections_gdf.iterrows():
                try:
                    geometry = connection.geometry
                    if geometry and isinstance(geometry, LineString):
                        # Find the building that this connection belongs to
                        building_id = connection.get('building_id')
                        street_name = connection.get('street_name', 'Unknown')
                        distance = connection.get('distance', geometry.length)
                        
                        # Get connection endpoints
                        start_point = Point(geometry.coords[0])
                        end_point = Point(geometry.coords[-1])
                        
                        # Find closest building node
                        closest_building_node = None
                        min_building_dist = float('inf')
                        
                        for building_idx, building_node_id in building_node_mapping.items():
                            building_node_data = G.nodes[building_node_id]
                            building_point = Point(building_node_data['x'], building_node_data['y'])
                            
                            dist_start = start_point.distance(building_point)
                            dist_end = end_point.distance(building_point)
                            min_dist = min(dist_start, dist_end)
                            
                            if min_dist < min_building_dist:
                                min_building_dist = min_dist
                                closest_building_node = building_node_id
                        
                        # Find closest junction node
                        closest_junction_node = None
                        min_junction_dist = float('inf')
                        
                        for coord, junction_node_id in street_junction_mapping.items():
                            junction_point = Point(coord[0], coord[1])
                            
                            dist_start = start_point.distance(junction_point)
                            dist_end = end_point.distance(junction_point)
                            min_dist = min(dist_start, dist_end)
                            
                            if min_dist < min_junction_dist:
                                min_junction_dist = min_dist
                                closest_junction_node = junction_node_id
                        
                        # Add connection edge if we found both nodes
                        if closest_building_node is not None and closest_junction_node is not None:
                            G.add_edge(closest_building_node, closest_junction_node,
                                     edge_type='connection',
                                     connection_id=str(idx),
                                     distance=float(distance),
                                     street_name=str(street_name),
                                     geometry_wkt=geometry.wkt
                                    )
                            
                except Exception as e:
                    logger.debug(f"Error processing connection edge {idx}: {e}")
                    continue
            
            # Update junction node degrees
            for node_id in G.nodes():
                if G.nodes[node_id].get('node_type') == 'junction':
                    G.nodes[node_id]['degree'] = G.degree(node_id)
            
            # Save to GraphML
            nx.write_graphml(G, graphml_path)
            
            logger.info(f"GraphML network saved with {G.number_of_nodes()} nodes and {G.number_of_edges()} edges")
            logger.info(f"Network composition: {len(building_node_mapping)} buildings, {len(street_junction_mapping)} junctions")
            
        except Exception as e:
            logger.error(f"Error saving network as GraphML: {e}")
            raise
