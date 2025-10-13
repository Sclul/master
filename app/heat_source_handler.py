"""Heat source management functionality."""
from typing import Dict, Any, Optional, List
from pathlib import Path
import geopandas as gpd  # type: ignore
import pandas as pd  # type: ignore
from shapely.geometry import Point  # type: ignore
import json
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class HeatSourceHandler:
    """Handles heat source data management and operations."""
    
    def __init__(self, config):
        """Initialize with configuration."""
        self.config = config
        self.data_paths = config.data_paths
        self.heat_sources_path = self.data_paths.get("heat_sources_path", "./data/heat_sources.geojson")
        
        logger.info("HeatSourceHandler initialized")
    
    def load_heat_sources(self) -> gpd.GeoDataFrame:
        """Load existing heat sources from GeoJSON file."""
        if not Path(self.heat_sources_path).exists():
            logger.info("No existing heat sources file found")
            return self._create_empty_heat_sources_gdf()
        
        heat_sources_gdf = gpd.read_file(self.heat_sources_path)
        
        if heat_sources_gdf.empty:
            logger.info("Heat sources file is empty")
            return self._create_empty_heat_sources_gdf()
        
        logger.info(f"Loaded {len(heat_sources_gdf)} heat sources")
        return heat_sources_gdf
    
    def _create_empty_heat_sources_gdf(self) -> gpd.GeoDataFrame:
        """Create an empty GeoDataFrame with proper heat source schema."""
        target_crs = self.config.coordinate_system.get("target_crs", "EPSG:5243")
        return gpd.GeoDataFrame(
            columns=[
                'id', 'annual_heat_production', 'heat_source_type'
            ],
            geometry=gpd.GeoSeries(name='geometry', dtype='geometry'),
            crs=target_crs
        )
    
    def add_heat_source(self, latitude: float, longitude: float, 
                       annual_heat_production: float = 1000.0,
                       heat_source_type: str = "Generic") -> Dict[str, Any]:
        """
        Add a new heat source at the specified coordinates.
        
        Args:
            latitude: Latitude of the heat source
            longitude: Longitude of the heat source  
            annual_heat_production: Annual heat production in kW/year
            heat_source_type: Type of heat source
            
        Returns:
            Dictionary with operation results
        """
        try:
            # Load existing heat sources
            heat_sources_gdf = self.load_heat_sources()
            
            # Create new heat source
            heat_source_id = f"hs_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{len(heat_sources_gdf) + 1}"
            
            new_heat_source = {
                'id': heat_source_id,
                'annual_heat_production': float(annual_heat_production),
                'heat_source_type': str(heat_source_type),
                'geometry': Point(longitude, latitude)
            }
            
            # Create DataFrame for new heat source in WGS84 first
            new_df = gpd.GeoDataFrame([new_heat_source], crs="EPSG:4326")
            
            # Transform to target CRS (EPSG:5243)
            target_crs = self.config.coordinate_system.get("target_crs", "EPSG:5243")
            new_df = new_df.to_crs(target_crs)
            
            # Ensure existing data is in the same CRS
            if not heat_sources_gdf.empty and heat_sources_gdf.crs != target_crs:
                heat_sources_gdf = heat_sources_gdf.to_crs(target_crs)
            
            # Append to existing data
            if heat_sources_gdf.empty:
                updated_gdf = new_df
            else:
                updated_gdf = pd.concat([heat_sources_gdf, new_df], ignore_index=True)
            
            # Save updated data
            result = self.save_heat_sources(updated_gdf)
            
            if result.get("status") == "success":
                logger.info(f"Added heat source at ({latitude}, {longitude}) with {annual_heat_production} kW/year")
                return {
                    "status": "success",
                    "message": f"Heat source added successfully",
                    "heat_source_id": heat_source_id,
                    "total_count": len(updated_gdf),
                    "coordinates": [latitude, longitude],
                    "annual_heat_production": annual_heat_production,
                    "heat_source_type": heat_source_type
                }
            else:
                return result
                
        except Exception as e:
            logger.error(f"Error adding heat source: {e}")
            return {
                "status": "error",
                "message": f"Failed to add heat source: {str(e)}"
            }
    
    def remove_heat_source(self, heat_source_id: str) -> Dict[str, Any]:
        """Remove a heat source by ID."""
        try:
            heat_sources_gdf = self.load_heat_sources()
            
            if heat_sources_gdf.empty:
                return {
                    "status": "error",
                    "message": "No heat sources to remove"
                }
            
            # Remove the specified heat source
            updated_gdf = heat_sources_gdf[heat_sources_gdf['id'] != heat_source_id]
            
            if len(updated_gdf) == len(heat_sources_gdf):
                return {
                    "status": "error",
                    "message": f"Heat source {heat_source_id} not found"
                }
            
            # Save updated data
            result = self.save_heat_sources(updated_gdf)
            
            if result.get("status") == "success":
                logger.info(f"Removed heat source {heat_source_id}")
                return {
                    "status": "success",
                    "message": f"Heat source removed successfully",
                    "total_count": len(updated_gdf)
                }
            else:
                return result
                
        except Exception as e:
            logger.error(f"Error removing heat source: {e}")
            return {
                "status": "error",
                "message": f"Failed to remove heat source: {str(e)}"
            }
    
    def clear_all_heat_sources(self) -> Dict[str, Any]:
        """Clear all heat sources."""
        try:
            # Create empty GeoDataFrame
            empty_gdf = self._create_empty_heat_sources_gdf()
            
            # Save empty data (this will overwrite the file)
            result = self.save_heat_sources(empty_gdf)
            
            if result.get("status") == "success":
                logger.info("Cleared all heat sources")
                return {
                    "status": "success",
                    "message": "All heat sources cleared successfully",
                    "total_count": 0
                }
            else:
                return result
                
        except Exception as e:
            logger.error(f"Error clearing heat sources: {e}")
            return {
                "status": "error",
                "message": f"Failed to clear heat sources: {str(e)}"
            }
    
    def save_heat_sources(self, heat_sources_gdf: gpd.GeoDataFrame) -> Dict[str, Any]:
        """Save heat sources to GeoJSON file."""
        try:
            # Ensure output directory exists
            output_file = Path(self.heat_sources_path)
            output_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Transform to target CRS if needed (EPSG:5243)
            target_crs = self.config.coordinate_system.get("target_crs", "EPSG:5243")
            if heat_sources_gdf.crs != target_crs:
                heat_sources_gdf_transformed = heat_sources_gdf.to_crs(target_crs)
            else:
                heat_sources_gdf_transformed = heat_sources_gdf.copy()
            
            # Save to GeoJSON
            heat_sources_gdf_transformed.to_file(self.heat_sources_path, driver="GeoJSON")
            
            logger.info(f"Heat sources saved to {self.heat_sources_path}")
            
            return {
                "status": "success",
                "message": f"Heat sources saved successfully",
                "file_path": self.heat_sources_path,
                "total_count": len(heat_sources_gdf)
            }
            
        except Exception as e:
            logger.error(f"Error saving heat sources: {e}")
            return {
                "status": "error",
                "message": f"Failed to save heat sources: {str(e)}"
            }
    
    def get_heat_sources_summary(self) -> Dict[str, Any]:
        """Get summary statistics about heat sources."""
        try:
            heat_sources_gdf = self.load_heat_sources()
            
            if heat_sources_gdf.empty:
                return {
                    "status": "success",
                    "total_count": 0,
                    "total_production": 0.0,
                    "average_production": 0.0,
                    "heat_source_types": []
                }
            
            # Calculate statistics
            total_count = len(heat_sources_gdf)
            total_production = heat_sources_gdf['annual_heat_production'].sum()
            average_production = heat_sources_gdf['annual_heat_production'].mean()
            heat_source_types = heat_sources_gdf['heat_source_type'].value_counts().to_dict()
            
            return {
                "status": "success",
                "total_count": total_count,
                "total_production": float(total_production),
                "average_production": float(average_production),
                "heat_source_types": heat_source_types
            }
            
        except Exception as e:
            logger.error(f"Error getting heat sources summary: {e}")
            return {
                "status": "error",
                "message": f"Failed to get summary: {str(e)}"
            }
    
    def load_heat_sources_data(self) -> Optional[str]:
        """Load heat sources data for map visualization."""
        try:
            heat_sources_gdf = self.load_heat_sources()
            
            if heat_sources_gdf.empty:
                logger.info("No heat sources data to load")
                return None
            
            # Ensure CRS is WGS84 for web display - transform from target CRS if needed
            target_crs = self.config.coordinate_system.get("target_crs", "EPSG:5243")
            web_crs = "EPSG:4326"
            
            if heat_sources_gdf.crs and str(heat_sources_gdf.crs) == target_crs:
                # Transform from target CRS to web CRS for display
                heat_sources_gdf = heat_sources_gdf.to_crs(web_crs)
            elif heat_sources_gdf.crs and str(heat_sources_gdf.crs) != web_crs:
                # Transform to web CRS if not already
                heat_sources_gdf = heat_sources_gdf.to_crs(web_crs)
            
            # Convert to GeoJSON string
            geojson_str = heat_sources_gdf.to_json()
            
            logger.info(f"Loaded heat sources data: {len(heat_sources_gdf)} sources")
            return geojson_str
            
        except Exception as e:
            logger.error(f"Error loading heat sources data for visualization: {e}")
            return None
