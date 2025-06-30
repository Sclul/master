"""District heating network generation functionality."""
import logging
import json
from typing import Dict, Any, Optional, Tuple, List
from pathlib import Path
import geopandas as gpd  # type: ignore
import pandas as pd  # type: ignore
from shapely.geometry import Point, LineString, MultiLineString  # type: ignore
from shapely.ops import nearest_points  # type: ignore

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
            
            # Combine streets with connection lines
            combined_network = self._combine_streets_and_connections(streets_gdf, connection_lines)
            
            # Save the combined network
            output_path = self.data_paths.get("network_path", "./data/heating_network.geojson")
            combined_network.to_file(output_path, driver="GeoJSON")
            
            logger.info(f"District heating network saved to: {output_path}")
            logger.info(f"Network contains {len(combined_network)} features ({len(connection_lines)} connections)")
            
            return {
                "status": "success",
                "message": f"Network generated with {len(connection_lines)} building connections",
                "file_path": output_path,
                "connections_count": len(connection_lines),
                "total_features": len(combined_network)
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
        
        for idx, building in buildings_gdf.iterrows():
            try:
                # Get building address information
                building_street = self._extract_building_street(building)
                
                if not building_street:
                    no_address_count += 1
                    logger.debug(f"Building {idx} has no street address, connecting to closest street")
                    
                    # Get building representative point
                    building_point = self._get_building_representative_point(building)
                    
                    if building_point:
                        # Connect to closest street regardless of name
                        shortest_connection = self._find_shortest_connection(building_point, streets_gdf)
                        
                        if shortest_connection:
                            # Mark this as a generic connection
                            shortest_connection["properties"]["connection_type"] = "building_to_closest_street"
                            shortest_connection["properties"]["building_street"] = "N/A"
                            connection_lines.append(shortest_connection)
                    continue
                
                # First try to find matching street(s) by name
                matching_streets = self._find_matching_streets(building_street, streets_gdf)
                
                # Get building representative point
                building_point = self._get_building_representative_point(building)
                
                if not building_point:
                    continue
                
                if not matching_streets.empty:
                    # Found matching street(s), connect to the closest one
                    shortest_connection = self._find_shortest_connection(building_point, matching_streets)
                    if shortest_connection:
                        shortest_connection["properties"]["connection_type"] = "building_to_matching_street"
                        shortest_connection["properties"]["building_street"] = building_street
                        connection_lines.append(shortest_connection)
                        successful_matches += 1
                else:
                    # No matching street found, connect to closest street anyway
                    no_matching_street_count += 1
                    logger.debug(f"No matching street found for building at {building_street}, connecting to closest")
                    
                    shortest_connection = self._find_shortest_connection(building_point, streets_gdf)
                    if shortest_connection:
                        shortest_connection["properties"]["connection_type"] = "building_to_closest_street"
                        shortest_connection["properties"]["building_street"] = building_street
                        connection_lines.append(shortest_connection)
                    
            except Exception as e:
                logger.warning(f"Error processing building {idx}: {e}")
                continue
        
        logger.info(f"Generated {len(connection_lines)} building-to-street connections")
        logger.info(f"Street name matches: {successful_matches}, No address: {no_address_count}, No matching street: {no_matching_street_count}")
        return connection_lines
    
    def _extract_building_street(self, building_row: pd.Series) -> Optional[str]:
        """Extract street name from building data."""
        # Check common street address fields
        street_fields = ['addr:street', 'street', 'addr_street', 'Street']
        
        for field in street_fields:
            if field in building_row and pd.notna(building_row[field]):
                return str(building_row[field]).strip()
        
        return None
    
    def _find_matching_streets(self, building_street: str, streets_gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
        """Find streets that match the building's street address."""
        # Check common street name fields in streets data
        street_fields = ['name', 'highway', 'street_name', 'addr:street']
        
        matching_streets = gpd.GeoDataFrame()
        
        for field in street_fields:
            if field in streets_gdf.columns:
                # Case-insensitive partial matching
                mask = streets_gdf[field].astype(str).str.contains(
                    building_street, case=False, na=False, regex=False
                )
                matches = streets_gdf[mask]
                
                if not matches.empty:
                    matching_streets = pd.concat([matching_streets, matches]).drop_duplicates()
        
        return matching_streets
    
    def _get_building_representative_point(self, building_row: pd.Series) -> Optional[Point]:
        """Get a representative point for the building geometry."""
        try:
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
    
    def _combine_streets_and_connections(self, streets_gdf: gpd.GeoDataFrame, 
                                       connection_lines: List[Dict[str, Any]]) -> gpd.GeoDataFrame:
        """Combine streets and connection lines into a single GeoDataFrame."""
        
        # Create GeoDataFrame for connections
        if connection_lines:
            connection_geometries = [conn["geometry"] for conn in connection_lines]
            connection_properties = [conn["properties"] for conn in connection_lines]
            
            connections_gdf = gpd.GeoDataFrame(
                connection_properties, 
                geometry=connection_geometries,
                crs=streets_gdf.crs
            )
            
            # Add a type column to distinguish streets from connections
            streets_gdf_copy = streets_gdf.copy()
            streets_gdf_copy['feature_type'] = 'street'
            connections_gdf['feature_type'] = 'connection'
            
            # Ensure both DataFrames have compatible columns
            # Add missing columns with default values
            for col in connections_gdf.columns:
                if col not in streets_gdf_copy.columns and col != 'geometry':
                    streets_gdf_copy[col] = None
            
            for col in streets_gdf_copy.columns:
                if col not in connections_gdf.columns and col != 'geometry':
                    connections_gdf[col] = None
            
            # Combine both GeoDataFrames
            combined_gdf = pd.concat([streets_gdf_copy, connections_gdf], ignore_index=True)
            combined_gdf = gpd.GeoDataFrame(combined_gdf, crs=streets_gdf.crs)
            
        else:
            # If no connections, just return streets with feature_type column
            combined_gdf = streets_gdf.copy()
            combined_gdf['feature_type'] = 'street'
        
        return combined_gdf
