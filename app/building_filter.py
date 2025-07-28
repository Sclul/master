"""Building filtering functionality."""
import json
import logging
from typing import Dict, Any, Optional, Tuple, List
from pathlib import Path

import geopandas as gpd  # type: ignore
import pandas as pd  # type: ignore

logger = logging.getLogger(__name__)


class BuildingFilter:
    """Handles building data loading and filtering operations."""
    
    def __init__(self, config):
        """Initialize with configuration."""
        self.config = config
        self.data_paths = config.data_paths
        self.heat_demand_column = "heat_demand" 
        
    def load_geospatial_data(self, show_progress: bool = False) -> Tuple[Optional[gpd.GeoDataFrame], Optional[gpd.GeoDataFrame]]:
        """Load buildings and streets data from saved files."""
        try:
            buildings_path = self.data_paths["buildings_path"]
            streets_path = self.data_paths["streets_path"]
            
            if not Path(buildings_path).exists():
                logger.error(f"Buildings file not found: {buildings_path}")
                return None, None
                
            if not Path(streets_path).exists():
                logger.error(f"Streets file not found: {streets_path}")
                return None, None
            
            buildings_gdf = gpd.read_file(buildings_path)
            streets_gdf = gpd.read_file(streets_path)
            
            logger.info(f"Loaded {len(buildings_gdf)} buildings and {len(streets_gdf)} street segments")
            
            return buildings_gdf, streets_gdf
            
        except Exception as e:
            logger.error(f"Error loading geospatial data: {e}")
            return None, None
    
    def filter_buildings(self, buildings_gdf: gpd.GeoDataFrame, 
                        filter_criteria: Optional[Dict[str, Any]] = None, show_progress: bool = True) -> gpd.GeoDataFrame:
        """Filter buildings based on criteria while preserving all data."""
        if buildings_gdf.empty:
            return buildings_gdf
        
        if filter_criteria is None:
            filter_criteria = getattr(self.config, 'building_filters', {})
        
        # Work with a copy to preserve original data
        filtered_gdf = buildings_gdf.copy()
        original_count = len(filtered_gdf)
        
        # Filter out buildings with zero heat demand
        if filter_criteria.get("exclude_zero_heat_demand", False):
            if self.heat_demand_column in filtered_gdf.columns:
                mask = (filtered_gdf[self.heat_demand_column].notna()) & \
                       (filtered_gdf[self.heat_demand_column] != 0)
                filtered_gdf = filtered_gdf[mask]
            else:
                logger.warning(f"Heat demand column '{self.heat_demand_column}' not found in buildings data")
        
        # Filter by heat demand range
        min_heat_demand = filter_criteria.get("min_heat_demand")
        max_heat_demand = filter_criteria.get("max_heat_demand")
        
        # Apply min heat demand filter (only if greater than 0)
        if min_heat_demand is not None and min_heat_demand > 0:
            if self.heat_demand_column in filtered_gdf.columns:
                mask = (filtered_gdf[self.heat_demand_column].notna()) & \
                       (filtered_gdf[self.heat_demand_column] >= min_heat_demand)
                filtered_gdf = filtered_gdf[mask]
                logger.info(f"After min heat demand filter (>= {min_heat_demand}): {len(filtered_gdf)} buildings")
        
        # Apply max heat demand filter (only if not infinity)
        if max_heat_demand is not None and max_heat_demand != float('inf'):
            if self.heat_demand_column in filtered_gdf.columns:
                mask = (filtered_gdf[self.heat_demand_column].notna()) & \
                       (filtered_gdf[self.heat_demand_column] <= max_heat_demand)
                filtered_gdf = filtered_gdf[mask]
                logger.info(f"After max heat demand filter (<= {max_heat_demand}): {len(filtered_gdf)} buildings")
        
        # Filter by building use - INCLUDE only specified uses (skip if empty)
        building_uses = filter_criteria.get("building_uses", [])
        if building_uses and len(building_uses) > 0 and any(use for use in building_uses if use):
            if "building:use" in filtered_gdf.columns:
                def should_include_building_use(use_value, include_uses):
                    # Handle "null" selection - include buildings with no specific use
                    if "null" in include_uses and pd.isna(use_value):
                        return True
                    
                    # Handle regular use values
                    if pd.isna(use_value):
                        return False  # Exclude buildings with no specific use if "null" not selected
                    
                    building_use_list = [use.strip().lower() for use in str(use_value).split(';')]
                    return any(iuse.lower() in building_use_list for iuse in include_uses if iuse != "null")
                
                # Keep buildings that should be included
                use_mask = filtered_gdf["building:use"].apply(
                    lambda x: should_include_building_use(x, building_uses)
                )
                filtered_gdf = filtered_gdf[use_mask]
                logger.info(f"Included buildings by use: {building_uses}. Remaining: {len(filtered_gdf)}")
            else:
                logger.warning("Column 'building:use' not found in buildings data")
        else:
            logger.info("No building use filter applied - including all building uses")
        
        # Filter by postcodes - INCLUDE only specified postcodes (skip if empty)
        postcodes = filter_criteria.get("postcodes", [])
        if postcodes and len(postcodes) > 0 and any(pc for pc in postcodes if pc):
            if "addr:postcode" in filtered_gdf.columns:
                postcode_mask = filtered_gdf["addr:postcode"].isin(postcodes)
                filtered_gdf = filtered_gdf[postcode_mask]
                logger.info(f"Filtered buildings by postcodes: {postcodes}. Remaining: {len(filtered_gdf)}")
            else:
                logger.warning("Column 'addr:postcode' not found in buildings data")
        else:
            logger.info("No postcode filter applied - including all postcodes")
        
        # Filter by cities - INCLUDE only specified cities (skip if empty)
        cities = filter_criteria.get("cities", [])
        if cities and len(cities) > 0 and any(city for city in cities if city):
            if "addr:city" in filtered_gdf.columns:
                city_mask = filtered_gdf["addr:city"].isin(cities)
                filtered_gdf = filtered_gdf[city_mask]
                logger.info(f"Filtered buildings by cities: {cities}. Remaining: {len(filtered_gdf)}")
            else:
                logger.warning("Column 'addr:city' not found in buildings data")
        else:
            logger.info("No city filter applied - including all cities")
        
        # Filter by streets - INCLUDE only specified streets (skip if empty)
        streets = filter_criteria.get("streets", [])
        if streets and len(streets) > 0 and any(street for street in streets if street):
            if "addr:street" in filtered_gdf.columns:
                street_mask = filtered_gdf["addr:street"].isin(streets)
                filtered_gdf = filtered_gdf[street_mask]
                logger.info(f"Filtered buildings by streets: {streets}. Remaining: {len(filtered_gdf)}")
            else:
                logger.warning("Column 'addr:street' not found in buildings data")
        else:
            logger.info("No street filter applied - including all streets")
        
        logger.info(f"Building filtering complete: {original_count} -> {len(filtered_gdf)} buildings")
        return filtered_gdf
    
    def load_and_filter_buildings(self, filter_criteria: Optional[Dict[str, Any]] = None, show_progress: bool = True) -> Tuple[Optional[gpd.GeoDataFrame], Optional[gpd.GeoDataFrame]]:
        """Load buildings and streets data, then apply filters to buildings."""
        buildings_gdf, streets_gdf = self.load_geospatial_data(show_progress=show_progress)
        
        if buildings_gdf is None or streets_gdf is None:
            return None, None
        
        filtered_buildings = self.filter_buildings(buildings_gdf, filter_criteria, show_progress=show_progress)
        return filtered_buildings, streets_gdf
    
    def save_filtered_buildings(self, filtered_buildings_gdf: gpd.GeoDataFrame, 
                               output_path: Optional[str] = None, show_progress: bool = True) -> Dict[str, Any]:
        """Save filtered buildings to a GeoJSON file."""
        try:
            if filtered_buildings_gdf.empty:
                logger.warning("No buildings to save - filtered dataset is empty")
                return {"status": "empty", "message": "No buildings to save"}
            
            if output_path is None:
                output_path = self.data_paths["filtered_buildings_path"]
            
            output_file = Path(output_path)
            output_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Ensure all data is preserved when saving
            filtered_buildings_gdf.to_file(output_path, driver="GeoJSON")
            
            logger.info(f"Filtered buildings saved to {output_path} (CRS: {filtered_buildings_gdf.crs})")
            
            return {
                "status": "saved",
                "file_path": output_path,
                "building_count": len(filtered_buildings_gdf),
                "columns": list(filtered_buildings_gdf.columns)
            }
            
        except Exception as e:
            logger.error(f"Error saving filtered buildings: {e}")
            return {"status": "error", "message": str(e)}
    
    def load_filtered_buildings_data(self, filtered_buildings_path: Optional[str] = None) -> Optional[str]:
        """Load filtered buildings data from file for display."""
        try:
            if filtered_buildings_path is None:
                filtered_buildings_path = self.data_paths["filtered_buildings_path"]
                
            with open(filtered_buildings_path, "r") as f:
                data = json.load(f)
            return json.dumps(data, indent=2)
        except FileNotFoundError:
            return "No filtered buildings saved yet."
        except Exception as e:
            return f"Error reading {filtered_buildings_path}: {e}"
    
    def get_unique_values(self, buildings_gdf: gpd.GeoDataFrame, column: str) -> List[str]:
        """Get unique values from a column for filter options."""
        if buildings_gdf.empty or column not in buildings_gdf.columns:
            return []
        
        unique_values = buildings_gdf[column].dropna().unique()
        return sorted([str(val) for val in unique_values if val])
    
    def get_filter_options(self, buildings_gdf: gpd.GeoDataFrame) -> Dict[str, List[str]]:
        """Get available filter options from buildings data."""
        if buildings_gdf.empty:
            return {}
        
        options = {}
        
        # Building uses
        if "building:use" in buildings_gdf.columns:
            uses = set()
            has_null_values = False
            
            # Check for null/empty values
            if buildings_gdf["building:use"].isna().any():
                has_null_values = True
            
            # Collect non-null values
            for use_value in buildings_gdf["building:use"].dropna():
                if pd.notna(use_value):
                    uses.update([use.strip() for use in str(use_value).split(';')])
            
            # Create sorted list and add null option if there are null values
            use_list = sorted(list(uses))
            if has_null_values:
                use_list.insert(0, "null")  # Add null at the beginning
            
            options["building_uses"] = use_list
        
        # Postcodes
        if "addr:postcode" in buildings_gdf.columns:
            options["postcodes"] = self.get_unique_values(buildings_gdf, "addr:postcode")
        
        # Cities
        if "addr:city" in buildings_gdf.columns:
            options["cities"] = self.get_unique_values(buildings_gdf, "addr:city")
        
        # Streets
        if "addr:street" in buildings_gdf.columns:
            options["streets"] = self.get_unique_values(buildings_gdf, "addr:street")
        
        return options