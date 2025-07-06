"""District heating network generation functionality."""
from typing import Dict, Any, Optional, List
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
    
    # Constants for street matching
    STREET_FIELDS = ['addr:street', 'street', 'addr_street', 'Street']
    STREET_NAME_FIELDS = ['name', 'addr:street']
    MATCH_THRESHOLD = 85
    COORDINATE_PRECISION = 6
    
    def __init__(self, config):
        """Initialize with configuration."""
        self.config = config
        self.data_paths = config.data_paths
        self.network_settings = config.config.get("network_generation", {})
        self._cached_street_names: Dict[str, pd.Series] = {}
        
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
            # Load data
            buildings_gdf, streets_gdf = self._load_data(use_filtered_buildings)
            
            # Generate connections
            connection_lines = self._generate_building_street_connections(buildings_gdf, streets_gdf)
            
            if not connection_lines:
                return {"status": "error", "message": "No connections could be generated"}
            
            # Save network
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
            return {"status": "error", "message": str(e)}
    
    def _load_data(self, use_filtered_buildings: bool) -> tuple[gpd.GeoDataFrame, gpd.GeoDataFrame]:
        """Load buildings and streets data."""
        # Determine buildings path
        buildings_path = (self.data_paths["filtered_buildings_path"] if use_filtered_buildings 
                         else self.data_paths["buildings_path"])
        
        logger.info(f"Using {'filtered' if use_filtered_buildings else 'all'} buildings for network generation")
        
        # Validate file existence
        if not Path(buildings_path).exists():
            raise FileNotFoundError(f"Buildings file not found: {buildings_path}")
        
        streets_path = self.data_paths["streets_path"]
        if not Path(streets_path).exists():
            raise FileNotFoundError(f"Streets file not found: {streets_path}")
        
        # Load geodataframes
        buildings_gdf = gpd.read_file(buildings_path)
        streets_gdf = gpd.read_file(streets_path)
        
        # Validate data
        if buildings_gdf.empty:
            raise ValueError("No buildings data available")
        if streets_gdf.empty:
            raise ValueError("No streets data available")
        
        logger.info(f"Loaded {len(buildings_gdf)} buildings and {len(streets_gdf)} streets")
        return buildings_gdf, streets_gdf
    
    def _generate_building_street_connections(self, buildings_gdf: gpd.GeoDataFrame,
                                           streets_gdf: gpd.GeoDataFrame) -> List[Dict[str, Any]]:
        """Generate connection lines from buildings to their corresponding streets."""
        connection_lines = []
        stats = {"no_address": 0, "no_matching_street": 0, "successful_matches": 0, "distance_exceeded": 0}
        
        all_streets_sindex = streets_gdf.sindex
        
        for idx, building in buildings_gdf.iterrows():
            try:
                connection = self._process_single_building(building, idx, streets_gdf, all_streets_sindex, stats)
                if connection:
                    connection_lines.append(connection)
                    
            except Exception as e:
                logger.warning(f"Error processing building {idx}: {e}", exc_info=True)
                continue
        
        self._log_connection_stats(connection_lines, stats)
        return connection_lines
    
    def _process_single_building(self, building: pd.Series, idx: int, streets_gdf: gpd.GeoDataFrame,
                               all_streets_sindex, stats: Dict[str, int]) -> Optional[Dict[str, Any]]:
        """Process a single building to create street connection."""
        building_street = self._extract_building_street(building)
        building_point = self._get_building_representative_point(building)
        
        if not building_point:
            return None
        
        # Try to match building to named street
        if building_street:
            connection = self._try_street_name_match(building_point, building_street, idx, 
                                                   streets_gdf, all_streets_sindex, stats)
            if connection:
                return connection
        else:
            stats["no_address"] += 1
        
        # Fallback to closest street
        return self._create_fallback_connection(building_point, building_street, streets_gdf)
    
    def _try_street_name_match(self, building_point: Point, building_street: str, building_idx: int,
                             streets_gdf: gpd.GeoDataFrame, all_streets_sindex, 
                             stats: Dict[str, int]) -> Optional[Dict[str, Any]]:
        """Try to match building to a street by name."""
        matching_streets = self._find_matching_streets(building_street, streets_gdf)
        
        if matching_streets.empty:
            stats["no_matching_street"] += 1
            return None
        
        connection = self._find_shortest_connection(building_point, matching_streets)
        if not connection:
            # Check if it's due to distance or no match
            temp_connection = self._find_shortest_connection_ignore_distance(building_point, matching_streets)
            if temp_connection:
                stats["distance_exceeded"] += 1
            else:
                stats["no_matching_street"] += 1
            return None
        
        # Handle junction avoidance
        connection = self._handle_junction_avoidance(connection, building_point, building_idx,
                                                   streets_gdf, all_streets_sindex)
        
        connection["properties"]["building_street"] = building_street
        stats["successful_matches"] += 1
        return connection
    
    def _handle_junction_avoidance(self, connection: Dict[str, Any], building_point: Point,
                                 building_idx: int, streets_gdf: gpd.GeoDataFrame,
                                 all_streets_sindex) -> Dict[str, Any]:
        """Handle junction detection and alternative street selection."""
        connection_point = Point(connection['geometry'].coords[1])
        
        # Check if connection point is at a junction
        if self._is_junction(connection_point, streets_gdf, all_streets_sindex):
            logger.debug(f"Junction detected for building {building_idx}. Finding alternative.")
            
            # Try to find alternative street
            alternative_connection = self._find_alternative_street_connection(
                building_point, connection, streets_gdf, all_streets_sindex)
            
            if alternative_connection:
                logger.debug(f"Found alternative connection for building {building_idx}")
                alternative_connection["properties"]["connection_type"] = "building_to_alternative_street"
                return alternative_connection
            else:
                connection["properties"]["connection_type"] = "building_to_matching_street_at_junction"
        else:
            connection["properties"]["connection_type"] = "building_to_matching_street"
        
        return connection
    
    def _is_junction(self, point: Point, streets_gdf: gpd.GeoDataFrame, sindex) -> bool:
        """Check if a point is at a street junction."""
        possible_matches_indices = list(sindex.intersection(point.bounds))
        possible_matches = streets_gdf.iloc[possible_matches_indices]
        intersecting_streets = possible_matches[possible_matches.intersects(point)]
        return len(intersecting_streets) > 1
    
    def _find_alternative_street_connection(self, building_point: Point, original_connection: Dict[str, Any],
                                          streets_gdf: gpd.GeoDataFrame, sindex) -> Optional[Dict[str, Any]]:
        """Find alternative street connection to avoid junctions."""
        # Find two nearest streets
        nearest_indices = sindex.nearest(building_point, return_all=True, max_distance=None, return_distance=False)
        nearest_geometries_indices = nearest_indices[1]
        nearest_streets = streets_gdf.iloc[nearest_geometries_indices[:2]]
        
        # Find the street that's NOT the originally matched one
        matched_street_id = original_connection['properties']['street_id']
        alternative_street = nearest_streets[nearest_streets.index.astype(str) != matched_street_id]
        
        if not alternative_street.empty:
            return self._find_shortest_connection(building_point, alternative_street)
        
        return None
    
    def _create_fallback_connection(self, building_point: Point, building_street: Optional[str],
                                  streets_gdf: gpd.GeoDataFrame) -> Optional[Dict[str, Any]]:
        """Create fallback connection to closest street."""
        logger.debug(f"Using fallback to closest street for building (street: {building_street or 'N/A'})")
        
        connection = self._find_shortest_connection(building_point, streets_gdf)
        if connection:
            connection["properties"]["connection_type"] = "building_to_closest_street"
            connection["properties"]["building_street"] = building_street or "N/A"
            
        return connection
    
    def _log_connection_stats(self, connection_lines: List[Dict[str, Any]], stats: Dict[str, int]) -> None:
        """Log connection statistics."""
        logger.info(f"Generated {len(connection_lines)} building-to-street connections")
        logger.info(f"Street name matches: {stats['successful_matches']}, "
                   f"No address: {stats['no_address']}, "
                   f"No matching street: {stats['no_matching_street']}")
    
    def _pre_process_street_names(self, streets_gdf: gpd.GeoDataFrame) -> pd.Series:
        """Pre-process and cache street names for faster matching."""
        # Create cache key
        try:
            cache_key = pd.util.hash_pandas_object(streets_gdf).sum()
        except TypeError:
            cache_key = str(streets_gdf)

        if cache_key in self._cached_street_names:
            return self._cached_street_names[cache_key]

        # Process street names from multiple fields
        all_street_names = []
        for field in self.STREET_NAME_FIELDS:
            if field in streets_gdf.columns:
                streets_exploded = streets_gdf.explode(field)
                normalized_names = streets_exploded[field].dropna().apply(self._normalize_street_name)
                all_street_names.append(normalized_names)

        if not all_street_names:
            return pd.Series(dtype=str, index=streets_gdf.index)

        # Concatenate and cache result
        processed_series = pd.concat(all_street_names).groupby(level=0).first()
        self._cached_street_names[cache_key] = processed_series
        
        return processed_series

    def _extract_building_street(self, building_row: pd.Series) -> Optional[str]:
        """Extract street name from building data."""
        for field in self.STREET_FIELDS:
            if field in building_row and pd.notna(building_row[field]):
                return str(building_row[field])
        return None
    
    def _normalize_street_name(self, street_name: str) -> str:
        """Normalize street name for better matching."""
        if not isinstance(street_name, str):
            return ""
        
        name = street_name.lower().strip()
        name = unicodedata.normalize('NFC', name)
        
        # German-specific normalizations
        normalizations = {
            'ß': 'ss',
            'str.': 'strasse',
            'str ': 'strasse ',
            'straße': 'strasse'
        }
        
        for old, new in normalizations.items():
            name = name.replace(old, new)
            
        return name

    def _find_matching_streets(self, building_street: str, streets_gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
        """Find streets that match the building's street address using fuzzy matching."""
        building_street_normalized = self._normalize_street_name(building_street)
        normalized_street_names = self._pre_process_street_names(streets_gdf)
        
        if normalized_street_names.empty:
            return gpd.GeoDataFrame()

        # Calculate fuzzy scores and find best match
        scores = normalized_street_names.apply(
            lambda street_name: fuzz.partial_ratio(building_street_normalized, street_name)
        )
        
        best_match_idx = scores.idxmax()
        best_match_score = scores.max()

        if best_match_score > self.MATCH_THRESHOLD:
            logger.debug(f"Best fuzzy match for '{building_street_normalized}': "
                        f"'{normalized_street_names.loc[best_match_idx]}' (Score: {best_match_score})")
            return streets_gdf.loc[[best_match_idx]]
            
        return gpd.GeoDataFrame()

    def _get_building_representative_point(self, building_row: pd.Series) -> Optional[Point]:
        """Get the representative point of a building's geometry."""
        try:
            # Try pre-computed representative_point first
            if 'representative_point' in building_row and pd.notna(building_row['representative_point']):
                rep_point_data = building_row['representative_point']
                
                # Handle dictionary format
                if isinstance(rep_point_data, dict) and 'coordinates' in rep_point_data:
                    coords = rep_point_data['coordinates']
                    if len(coords) >= 2:
                        return Point(coords[0], coords[1])
                
                # Handle Point geometry
                elif hasattr(rep_point_data, 'x') and hasattr(rep_point_data, 'y'):
                    return rep_point_data
            
            # Fallback to geometry centroid
            geometry = building_row.geometry
            if geometry and not geometry.is_empty:
                return geometry.centroid if hasattr(geometry, 'centroid') else geometry
                    
        except Exception as e:
            logger.debug(f"Error getting building representative point: {e}")
        
        return None
    
    def _find_shortest_connection(self, building_point: Point, 
                                streets_gdf: gpd.GeoDataFrame) -> Optional[Dict[str, Any]]:
        """Find the shortest connection from building to matching streets."""
        shortest_distance = float('inf')
        best_connection = None
        max_distance = self.network_settings.get("max_connection_distance", float('inf'))
        
        for idx, street in streets_gdf.iterrows():
            try:
                if not street.geometry or street.geometry.is_empty:
                    continue
                
                # Find nearest points and calculate distance
                nearest_geoms = nearest_points(building_point, street.geometry)
                connection_line = LineString([nearest_geoms[0], nearest_geoms[1]])
                distance = connection_line.length
                
                if distance < shortest_distance:
                    shortest_distance = distance
                    street_name = self._get_street_name(street)
                    
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
        
        # Check if the best connection exceeds the maximum allowed distance
        if best_connection and shortest_distance > max_distance:
            logger.debug(f"Building connection rejected: distance {shortest_distance:.2f}m exceeds maximum {max_distance}m")
            return None
        
        return best_connection
    
    def _find_shortest_connection_ignore_distance(self, building_point: Point, 
                                                streets_gdf: gpd.GeoDataFrame) -> Optional[Dict[str, Any]]:
        """Find the shortest connection from building to matching streets, ignoring distance limits."""
        shortest_distance = float('inf')
        best_connection = None
        max_distance = self.network_settings.get("max_connection_distance", float('inf'))
        
        for idx, street in streets_gdf.iterrows():
            try:
                if not street.geometry or street.geometry.is_empty:
                    continue
                
                # Find nearest points and calculate distance
                nearest_geoms = nearest_points(building_point, street.geometry)
                connection_line = LineString([nearest_geoms[0], nearest_geoms[1]])
                distance = connection_line.length
                
                if distance < shortest_distance:
                    shortest_distance = distance
                    street_name = self._get_street_name(street)
                    
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
        
        # Check if the best connection exceeds the maximum allowed distance
        if best_connection and shortest_distance > max_distance:
            logger.debug(f"Building connection rejected: distance {shortest_distance:.2f}m exceeds maximum {max_distance}m")
            return None
        
        return best_connection
    
    def _get_street_name(self, street: pd.Series) -> str:
        """Safely extract street name from street data."""
        name_fields = ['name', 'highway', 'street_name', 'addr:street']
        
        for field in name_fields:
            if field in street.index and pd.notna(street[field]):
                return str(street[field])
                
        return "Unknown"

    def _save_network_as_graphml(self, buildings_gdf: gpd.GeoDataFrame, 
                               streets_gdf: gpd.GeoDataFrame,
                               connection_lines: List[Dict[str, Any]], 
                               graphml_path: str) -> None:
        """Save the heating network as GraphML with building and junction nodes."""
        try:
            # Create graph and mappings
            G = nx.DiGraph()
            node_id = 0
            
            # Add building nodes
            building_node_mapping, node_id = self._add_building_nodes(G, buildings_gdf, node_id)
            
            # Add junction nodes
            street_junction_mapping, node_id = self._add_junction_nodes(G, streets_gdf, node_id)
            
            # Add street edges
            self._add_street_edges(G, streets_gdf, street_junction_mapping)
            
            # Add building connection edges
            self._add_connection_edges(G, connection_lines, building_node_mapping, 
                                     street_junction_mapping, streets_gdf.crs)
            
            # Update junction degrees
            self._update_junction_degrees(G)
            
            # Save to file
            nx.write_graphml(G, graphml_path)
            
            logger.info(f"GraphML network saved with {G.number_of_nodes()} nodes and {G.number_of_edges()} edges")
            logger.info(f"Network composition: {len(building_node_mapping)} buildings, {len(street_junction_mapping)} junctions")
            
        except Exception as e:
            logger.error(f"Error saving network as GraphML: {e}")
            raise
    
    def _add_building_nodes(self, G: nx.DiGraph, buildings_gdf: gpd.GeoDataFrame, 
                           start_node_id: int) -> tuple[Dict, int]:
        """Add building nodes to the graph."""
        building_node_mapping = {}
        node_id = start_node_id
        
        for idx, building in buildings_gdf.iterrows():
            try:
                building_point = self._get_building_representative_point(building)
                if not building_point:
                    continue
                
                # Extract building properties
                heat_demand = building.get('heat_demand', 0) if 'heat_demand' in building.index else 0
                street_address = self._extract_building_street(building) or "Unknown"
                geometry_type = str(type(building.geometry).__name__) if hasattr(building, 'geometry') else 'Unknown'
                
                G.add_node(node_id,
                         node_type='building',
                         building_id=str(idx),
                         x=building_point.x,
                         y=building_point.y,
                         heat_demand=float(heat_demand) if pd.notna(heat_demand) else 0.0,
                         street_address=street_address,
                         geometry_type=geometry_type)
                
                building_node_mapping[idx] = node_id
                node_id += 1
                
            except Exception as e:
                logger.debug(f"Error processing building {idx} for GraphML: {e}")
                continue
        
        return building_node_mapping, node_id
    
    def _add_junction_nodes(self, G: nx.DiGraph, streets_gdf: gpd.GeoDataFrame, 
                           start_node_id: int) -> tuple[Dict, int]:
        """Add junction nodes from street endpoints."""
        junction_coords = set()
        
        # Collect all street endpoints
        for idx, street in streets_gdf.iterrows():
            try:
                geometry = street.geometry
                if not geometry or geometry.is_empty:
                    continue
                
                endpoints = self._extract_street_endpoints(geometry)
                junction_coords.update(endpoints)
                
            except Exception as e:
                logger.debug(f"Error processing street {idx} for junctions: {e}")
                continue
        
        # Add junction nodes
        street_junction_mapping = {}
        node_id = start_node_id
        
        for coord in junction_coords:
            G.add_node(node_id,
                     node_type='junction',
                     junction_id=f"j_{node_id}",
                     x=coord[0],
                     y=coord[1],
                     degree=0)
            
            street_junction_mapping[coord] = node_id
            node_id += 1
        
        return street_junction_mapping, node_id
    
    def _extract_street_endpoints(self, geometry) -> List[tuple]:
        """Extract endpoints from street geometry."""
        endpoints = []
        precision = self.COORDINATE_PRECISION
        
        if isinstance(geometry, LineString):
            start_point = Point(geometry.coords[0])
            end_point = Point(geometry.coords[-1])
            endpoints.extend([
                (round(start_point.x, precision), round(start_point.y, precision)),
                (round(end_point.x, precision), round(end_point.y, precision))
            ])
        elif isinstance(geometry, MultiLineString):
            for line in geometry.geoms:
                start_point = Point(line.coords[0])
                end_point = Point(line.coords[-1])
                endpoints.extend([
                    (round(start_point.x, precision), round(start_point.y, precision)),
                    (round(end_point.x, precision), round(end_point.y, precision))
                ])
        
        return endpoints
    
    def _add_street_edges(self, G: nx.DiGraph, streets_gdf: gpd.GeoDataFrame, 
                         street_junction_mapping: Dict) -> None:
        """Add street edges between junctions."""
        for idx, street in streets_gdf.iterrows():
            try:
                geometry = street.geometry
                if not geometry or geometry.is_empty:
                    continue
                
                street_name = street.get('name', f"street_{idx}")
                highway_type = street.get('highway', 'unknown')
                
                if isinstance(geometry, LineString):
                    self._add_single_street_edge(G, geometry, idx, street_name, highway_type, street_junction_mapping)
                elif isinstance(geometry, MultiLineString):
                    for line in geometry.geoms:
                        self._add_single_street_edge(G, line, idx, street_name, highway_type, street_junction_mapping)
                        
            except Exception as e:
                logger.debug(f"Error processing street edge {idx}: {e}")
                continue
    
    def _add_single_street_edge(self, G: nx.DiGraph, line_geometry: LineString, street_idx: int,
                               street_name: str, highway_type: str, street_junction_mapping: Dict) -> None:
        """Add a single street edge to the graph."""
        precision = self.COORDINATE_PRECISION
        
        start_coord = (round(line_geometry.coords[0][0], precision), round(line_geometry.coords[0][1], precision))
        end_coord = (round(line_geometry.coords[-1][0], precision), round(line_geometry.coords[-1][1], precision))
        
        start_node = street_junction_mapping.get(start_coord)
        end_node = street_junction_mapping.get(end_coord)
        
        if start_node is not None and end_node is not None and start_node != end_node:
            G.add_edge(start_node, end_node,
                     edge_type='street',
                     street_id=str(street_idx),
                     name=str(street_name),
                     highway=str(highway_type),
                     length=float(line_geometry.length),
                     geometry_wkt=line_geometry.wkt)
    
    def _add_connection_edges(self, G: nx.DiGraph, connection_lines: List[Dict[str, Any]],
                             building_node_mapping: Dict, street_junction_mapping: Dict, crs) -> None:
        """Add building-to-street connection edges."""
        if not connection_lines:
            return
        
        # Create connections GeoDataFrame
        connection_geometries = [conn["geometry"] for conn in connection_lines]
        connection_properties = [conn["properties"] for conn in connection_lines]
        connections_gdf = gpd.GeoDataFrame(connection_properties, geometry=connection_geometries, crs=crs)
        
        for idx, connection in connections_gdf.iterrows():
            try:
                geometry = connection.geometry
                if not geometry or not isinstance(geometry, LineString):
                    continue
                
                # Find closest building and junction nodes
                closest_building_node = self._find_closest_building_node(geometry, building_node_mapping, G)
                closest_junction_node = self._find_closest_junction_node(geometry, street_junction_mapping)
                
                if closest_building_node is not None and closest_junction_node is not None:
                    G.add_edge(closest_building_node, closest_junction_node,
                             edge_type='connection',
                             connection_id=str(idx),
                             distance=float(connection.get('distance', geometry.length)),
                             street_name=str(connection.get('street_name', 'Unknown')),
                             geometry_wkt=geometry.wkt)
                
            except Exception as e:
                logger.debug(f"Error processing connection edge {idx}: {e}")
                continue
    
    def _find_closest_building_node(self, connection_geometry: LineString, 
                                   building_node_mapping: Dict, G: nx.DiGraph) -> Optional[int]:
        """Find the closest building node to a connection geometry."""
        start_point = Point(connection_geometry.coords[0])
        end_point = Point(connection_geometry.coords[-1])
        
        closest_node = None
        min_dist = float('inf')
        
        for building_idx, node_id in building_node_mapping.items():
            node_data = G.nodes[node_id]
            building_point = Point(node_data['x'], node_data['y'])
            
            dist = min(start_point.distance(building_point), end_point.distance(building_point))
            if dist < min_dist:
                min_dist = dist
                closest_node = node_id
        
        return closest_node
    
    def _find_closest_junction_node(self, connection_geometry: LineString, 
                                   street_junction_mapping: Dict) -> Optional[int]:
        """Find the closest junction node to a connection geometry."""
        start_point = Point(connection_geometry.coords[0])
        end_point = Point(connection_geometry.coords[-1])
        
        closest_node = None
        min_dist = float('inf')
        
        for coord, node_id in street_junction_mapping.items():
            junction_point = Point(coord[0], coord[1])
            
            dist = min(start_point.distance(junction_point), end_point.distance(junction_point))
            if dist < min_dist:
                min_dist = dist
                closest_node = node_id
        
        return closest_node
    
    def _update_junction_degrees(self, G: nx.DiGraph) -> None:
        """Update junction node degrees."""
        for node_id in G.nodes():
            if G.nodes[node_id].get('node_type') == 'junction':
                G.nodes[node_id]['degree'] = G.degree(node_id)
