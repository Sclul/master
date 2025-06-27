"""Building clustering functionality for merging buildings without addresses."""
import logging
from typing import Dict, Any, Optional, Tuple, List
from pathlib import Path
import numpy as np # type: ignore
import geopandas as gpd # type: ignore
from shapely.geometry import Point, MultiPolygon, Polygon # type: ignore
from shapely.ops import unary_union # type: ignore
from sklearn.neighbors import NearestNeighbors # type: ignore
import pandas as pd # type: ignore

logger = logging.getLogger(__name__)


class BuildingClusterer:
    """Handles clustering of buildings without addresses to nearest buildings with addresses."""
    
    def __init__(self, config):
        """Initialize with configuration."""
        self.config = config
        self.data_paths = config.data_paths
        self.heat_demand_column = "heat_demand"
        
    def has_complete_address(self, building_row: pd.Series) -> bool:
        """Check if a building has a complete address."""
        required_fields = ['addr:street', 'addr:housenumber']
        
        # Check if all required fields exist and are not null/empty
        for field in required_fields:
            if field not in building_row.index or pd.isna(building_row[field]) or str(building_row[field]).strip() == '':
                return False
        
        return True
    
    def get_representative_point_from_geometry(self, geometry) -> Tuple[float, float]:
        """Get representative point coordinates from geometry."""
        if geometry and not geometry.is_empty:
            # Ensure the geometry is valid
            if not geometry.is_valid:
                geometry = geometry.buffer(0)
            if geometry and not geometry.is_empty and geometry.is_valid:
                rp = geometry.representative_point()
                return (rp.x, rp.y)
        return (None, None)
    
    def find_nearest_building_with_address(self, buildings_without_address: gpd.GeoDataFrame, 
                                         buildings_with_address: gpd.GeoDataFrame) -> Dict[int, int]:
        """Find nearest building with address for each building without address."""
        if buildings_without_address.empty or buildings_with_address.empty:
            return {}
        
        # Get representative points for buildings without addresses
        points_without_address = []
        valid_indices_without = []
        
        for idx, building in buildings_without_address.iterrows():
            x, y = self.get_representative_point_from_geometry(building.geometry)
            if x is not None and y is not None:
                points_without_address.append([x, y])
                valid_indices_without.append(idx)
        
        # Get representative points for buildings with addresses
        points_with_address = []
        valid_indices_with = []
        
        for idx, building in buildings_with_address.iterrows():
            x, y = self.get_representative_point_from_geometry(building.geometry)
            if x is not None and y is not None:
                points_with_address.append([x, y])
                valid_indices_with.append(idx)
        
        if not points_without_address or not points_with_address:
            logger.warning("No valid points found for clustering")
            return {}
        
        # Use NearestNeighbors to find closest buildings
        nn = NearestNeighbors(n_neighbors=1, algorithm='ball_tree')
        nn.fit(points_with_address)
        
        distances, indices = nn.kneighbors(points_without_address)
        
        # Create mapping from building without address to building with address
        mapping = {}
        for i, (distance, nearest_idx) in enumerate(zip(distances, indices)):
            building_without_idx = valid_indices_without[i]
            building_with_idx = valid_indices_with[nearest_idx[0]]
            mapping[building_without_idx] = building_with_idx
            
            logger.debug(f"Building {building_without_idx} -> Building {building_with_idx} (distance: {distance[0]:.2f}m)")
        
        return mapping
    
    def merge_geometries(self, geometries: List):
        """Merge multiple geometries into a MultiPolygon preserving individual shapes."""
        try:
            # Filter out invalid or empty geometries
            valid_geometries = []
            for geom in geometries:
                if geom and not geom.is_empty:
                    if not geom.is_valid:
                        geom = geom.buffer(0)  # Attempt to fix invalid geometry
                    if geom and not geom.is_empty and geom.is_valid:
                        # Ensure we have Polygon objects
                        if isinstance(geom, Polygon):
                            valid_geometries.append(geom)
                        elif isinstance(geom, MultiPolygon):
                            # If it's already a MultiPolygon, add all its polygons
                            valid_geometries.extend(list(geom.geoms))
            
            if not valid_geometries:
                return None
            
            if len(valid_geometries) == 1:
                return valid_geometries[0]
            
            # Create MultiPolygon from all individual polygons
            # This preserves each original building polygon
            multipolygon = MultiPolygon(valid_geometries)
            
            return multipolygon
            
        except Exception as e:
            logger.error(f"Error merging geometries: {e}")
            return None
    
    def aggregate_heat_demand(self, heat_demands: List) -> float:
        """Aggregate heat demand values from multiple buildings."""
        valid_demands = []
        for demand in heat_demands:
            if demand is not None and not pd.isna(demand):
                try:
                    valid_demands.append(float(demand))
                except (ValueError, TypeError):
                    continue
        
        return sum(valid_demands) if valid_demands else 0.0
    
    def cluster_buildings(self, buildings_gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
        """Cluster buildings without addresses to nearest buildings with addresses."""
        if buildings_gdf.empty:
            logger.warning("Empty buildings GeoDataFrame provided")
            return buildings_gdf
        
        original_count = len(buildings_gdf)
        logger.info(f"Starting clustering with {original_count} buildings")
        
        # Separate buildings with and without addresses
        buildings_with_address = buildings_gdf[buildings_gdf.apply(self.has_complete_address, axis=1)].copy()
        buildings_without_address = buildings_gdf[~buildings_gdf.apply(self.has_complete_address, axis=1)].copy()
        
        logger.info(f"Buildings with complete addresses: {len(buildings_with_address)}")
        logger.info(f"Buildings without complete addresses: {len(buildings_without_address)}")
        
        if buildings_without_address.empty:
            logger.info("No buildings without addresses found - no clustering needed")
            return buildings_gdf
        
        if buildings_with_address.empty:
            logger.warning("No buildings with addresses found - cannot cluster")
            return buildings_gdf
        
        # Find nearest building with address for each building without address
        mapping = self.find_nearest_building_with_address(buildings_without_address, buildings_with_address)
        
        if not mapping:
            logger.warning("No valid mappings found - returning original data")
            return buildings_gdf
        
        # Group buildings without addresses by their nearest building with address
        clusters = {}
        for building_without_idx, building_with_idx in mapping.items():
            if building_with_idx not in clusters:
                clusters[building_with_idx] = []
            clusters[building_with_idx].append(building_without_idx)
        
        # Create the clustered GeoDataFrame
        clustered_buildings = []
        
        # Add buildings with addresses that don't have any clusters
        for idx, building in buildings_with_address.iterrows():
            if idx not in clusters:
                # No buildings to merge - keep as is
                clustered_buildings.append(building.to_dict())
            else:
                # Merge with clustered buildings
                geometries_to_merge = [building.geometry]
                heat_demands_to_aggregate = []
                
                # Add heat demand from the main building
                if self.heat_demand_column in building.index and not pd.isna(building[self.heat_demand_column]):
                    heat_demands_to_aggregate.append(building[self.heat_demand_column])
                
                # Add geometries and heat demands from buildings without addresses
                for clustered_idx in clusters[idx]:
                    clustered_building = buildings_without_address.loc[clustered_idx]
                    geometries_to_merge.append(clustered_building.geometry)
                    
                    if self.heat_demand_column in clustered_building.index and not pd.isna(clustered_building[self.heat_demand_column]):
                        heat_demands_to_aggregate.append(clustered_building[self.heat_demand_column])
                
                # Create merged building
                merged_building = building.to_dict()
                merged_building['geometry'] = self.merge_geometries(geometries_to_merge)
                merged_building[self.heat_demand_column] = self.aggregate_heat_demand(heat_demands_to_aggregate)
                merged_building['clustered_buildings_count'] = len(clusters[idx]) + 1  # +1 for the main building
                
                clustered_buildings.append(merged_building)
        
        # Create new GeoDataFrame from clustered buildings
        if clustered_buildings:
            clustered_gdf = gpd.GeoDataFrame(clustered_buildings, crs=buildings_gdf.crs)
            
            # Update representative points for clustered geometries
            def get_representative_point_coords(geom):
                if geom and not geom.is_empty:
                    if not geom.is_valid:
                        geom = geom.buffer(0)
                    if geom and not geom.is_empty and geom.is_valid:
                        rp = geom.representative_point()
                        return {"coordinates": [rp.x, rp.y]}
                return None
            
            clustered_gdf["representative_point"] = clustered_gdf["geometry"].apply(get_representative_point_coords)
            
            final_count = len(clustered_gdf)
            clustered_count = sum(1 for idx in clusters if clusters[idx])
            buildings_merged = original_count - final_count
            
            logger.info(f"Clustering complete: {original_count} -> {final_count} buildings")
            logger.info(f"Created {clustered_count} clusters, merged {buildings_merged} buildings")
            
            return clustered_gdf
        else:
            logger.warning("No clustered buildings created - returning original data")
            return buildings_gdf
    
    def cluster_and_save_buildings(self, input_path: Optional[str] = None, 
                                 output_path: Optional[str] = None) -> Dict[str, Any]:
        """Load buildings, apply clustering, and save the result."""
        try:
            # Set default paths
            if input_path is None:
                input_path = self.data_paths["buildings_path"]
            if output_path is None:
                output_path = self.data_paths["buildings_path"]  # Overwrite original by default
            
            # Check if input file exists
            if not Path(input_path).exists():
                return {
                    "status": "error", 
                    "message": f"Input file not found: {input_path}"
                }
            
            # Load buildings data
            logger.info(f"Loading buildings from {input_path}")
            buildings_gdf = gpd.read_file(input_path)
            
            if buildings_gdf.empty:
                return {
                    "status": "error", 
                    "message": "No buildings data found in input file"
                }
            
            # Apply clustering
            clustered_gdf = self.cluster_buildings(buildings_gdf)
            
            # Save clustered buildings
            output_file = Path(output_path)
            output_file.parent.mkdir(parents=True, exist_ok=True)
            
            clustered_gdf.to_file(output_path, driver="GeoJSON")
            
            logger.info(f"Clustered buildings saved to {output_path}")
            
            # Generate summary
            original_count = len(buildings_gdf)
            final_count = len(clustered_gdf)
            reduction = original_count - final_count
            
            summary = {
                "status": "success",
                "original_count": original_count,
                "final_count": final_count,
                "buildings_merged": reduction,
                "reduction_percentage": round((reduction / original_count) * 100, 1) if original_count > 0 else 0,
                "output_path": output_path
            }
            
            return summary
            
        except Exception as e:
            logger.error(f"Error in cluster_and_save_buildings: {e}")
            return {
                "status": "error",
                "message": str(e)
            }
    
    def get_clustering_statistics(self, buildings_gdf: gpd.GeoDataFrame) -> Dict[str, Any]:
        """Get statistics about the clustering potential of buildings data."""
        try:
            if buildings_gdf.empty:
                return {"message": "No buildings data available"}
            
            total_buildings = len(buildings_gdf)
            buildings_with_address = buildings_gdf[buildings_gdf.apply(self.has_complete_address, axis=1)]
            buildings_without_address = buildings_gdf[~buildings_gdf.apply(self.has_complete_address, axis=1)]
            
            with_address_count = len(buildings_with_address)
            without_address_count = len(buildings_without_address)
            
            stats = {
                "total_buildings": total_buildings,
                "buildings_with_complete_address": with_address_count,
                "buildings_without_complete_address": without_address_count,
                "address_coverage_percentage": round((with_address_count / total_buildings) * 100, 1) if total_buildings > 0 else 0,
                "potential_clustering_reduction": without_address_count,
                "estimated_final_count": with_address_count
            }
            
            # Add heat demand statistics if available
            if self.heat_demand_column in buildings_gdf.columns:
                heat_data_with_address = buildings_with_address[self.heat_demand_column].dropna()
                heat_data_without_address = buildings_without_address[self.heat_demand_column].dropna()
                
                stats.update({
                    "heat_demand_with_address": {
                        "count": len(heat_data_with_address),
                        "total": round(heat_data_with_address.sum(), 2) if len(heat_data_with_address) > 0 else 0
                    },
                    "heat_demand_without_address": {
                        "count": len(heat_data_without_address),
                        "total": round(heat_data_without_address.sum(), 2) if len(heat_data_without_address) > 0 else 0
                    }
                })
            
            return stats
            
        except Exception as e:
            logger.error(f"Error generating clustering statistics: {e}")
            return {"message": f"Error generating statistics: {str(e)}"}
