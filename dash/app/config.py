"""Configuration management for the Dash OSM application."""
import json
import logging
import os
import yaml
from typing import Dict, Any


logger = logging.getLogger(__name__)


class Config:
    """Configuration management class."""
    
    DEFAULT_CONFIG = {
        "osmnx_settings": {
            "consolidation_tolerance": 15,
            "network_type": "drive",
        },
        "server_settings": {
            "host": "0.0.0.0",
            "port": 8050,
            "debug": True,
        },
        "data_paths": {
            "output_directory": "./data",
            "polygon_geojson": "polygon.geojson",
            "streets_geojson": "streets.geojson",
            "buildings_geojson": "buildings.geojson",
            "gdb_path": "/gdb/GDB.gdb",
            "gdb_layer": "Raumwaermebedarf_ist", 
            "heat_demand_column": "RW",  # or "RW_WW" or "RW_spez" depending on what you want
        },
        "map_settings": {
            "default_center": [52.5200, 13.4050],  # Berlin by default
            "default_zoom": 15,
            "tile_url": "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
            "attribution": "© OpenStreetMap contributors",
            "measure_settings": {
                "position": "topleft",
                "primary_length_unit": "meters",
                "primary_area_unit": "sqmeters",
                "active_color": "blue",
                "completed_color": "rgba(0, 0, 255, 0.6)"
            }
        }
    }
    
    def __init__(self, config_path: str = None):
        """Initialize configuration."""
        if config_path is None:
            config_path = os.path.join(os.path.dirname(__file__), "config.yml")
        
        self.config_path = config_path
        self.config = self._load_config()
        self._setup_logging()
        self._setup_paths()
    
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from YAML file with fallback to defaults."""
        try:
            with open(self.config_path, "r") as f:
                config = yaml.safe_load(f)
            logger.info(f"Configuration loaded from {self.config_path}")
            return config
        except FileNotFoundError:
            logger.error(f"Configuration file not found at {self.config_path}. Using default values.")
            return self.DEFAULT_CONFIG.copy()
        except yaml.YAMLError as e:
            logger.error(f"Error parsing YAML configuration: {e}. Using default values.")
            return self.DEFAULT_CONFIG.copy()
    
    def _setup_logging(self):
        """Configure logging based on settings."""
        logging.basicConfig(
            level=logging.DEBUG if self.config["server_settings"]["debug"] else logging.INFO,
            format="%(asctime)s [%(levelname)s] %(message)s"
        )
    
    def _setup_paths(self):
        """Set up data paths and ensure directories exist."""
        self.data_dir = self.config["data_paths"]["output_directory"]
        self.polygon_path = os.path.join(self.data_dir, self.config["data_paths"]["polygon_geojson"])
        self.streets_path = os.path.join(self.data_dir, self.config["data_paths"]["streets_geojson"])
        self.buildings_path = os.path.join(self.data_dir, self.config["data_paths"]["buildings_geojson"])
        
        # Ensure data directory exists
        os.makedirs(self.data_dir, exist_ok=True)
    
    def get(self, key: str, default=None):
        """Get configuration value by key."""
        keys = key.split('.')
        value = self.config
        try:
            for k in keys:
                value = value[k]
            return value
        except (KeyError, TypeError):
            return default
    
    @property
    def osmnx_settings(self) -> Dict[str, Any]:
        """Get OSMnx settings."""
        return self.config["osmnx_settings"]
    
    @property
    def server_settings(self) -> Dict[str, Any]:
        """Get server settings."""
        return self.config["server_settings"]
    
    @property
    def data_paths(self) -> Dict[str, str]:
        """Get data paths."""
        return {
            "data_dir": self.data_dir,
            "polygon_path": self.polygon_path,
            "streets_path": self.streets_path,
            "buildings_path": self.buildings_path
        }
    
    @property
    def map_settings(self) -> Dict[str, Any]:
        """Get map display settings."""
        return self.config["map_settings"]
