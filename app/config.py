"""Configuration management for the Dash OSM application."""
import logging
import os
import yaml
from typing import Dict, Any


logger = logging.getLogger(__name__)


class Config:
    """Configuration management class."""
    
    def __init__(self, config_path: str = None):
        """Initialize configuration."""
        if config_path is None:
            config_path = os.path.join(os.path.dirname(__file__), "config.yml")
        
        self.config_path = config_path
        self.config = self._load_config()
        self._setup_logging()
    
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from YAML file."""
        try:
            with open(self.config_path, "r") as f:
                config = yaml.safe_load(f)
            logger.info(f"Configuration loaded from {self.config_path}")
            return config
        except FileNotFoundError:
            logger.error(f"Configuration file not found at {self.config_path}")
            raise
        except yaml.YAMLError as e:
            logger.error(f"Error parsing YAML configuration: {e}")
            raise
    
    def _setup_logging(self):
        """Configure logging based on settings."""
        logging.basicConfig(
            level=logging.DEBUG if self.config["server_settings"]["debug"] else logging.INFO,
            format="%(asctime)s [%(levelname)s] %(message)s"
        )
    
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
        # Ensure data directory exists
        data_dir = self.config["data_paths"].get("data_dir", "./data")
        os.makedirs(data_dir, exist_ok=True)
        return self.config["data_paths"]
    
    @property
    def map_settings(self) -> Dict[str, Any]:
        """Get map display settings."""
        return self.config["map_settings"]
    
    @property
    def heat_demand(self) -> Dict[str, Any]:
        """Get heat demand settings."""
        return self.config.get("heat_demand", {})
    
    @property
    def coordinate_system(self) -> Dict[str, str]:
        """Get coordinate system settings."""
        return self.config.get("coordinate_system", {
            "target_crs": "EPSG:5243",
            "input_crs": "EPSG:4326"
        })
    
    @property
    def building_filters(self) -> Dict[str, Any]:
        """Get building filters from config."""
        return self.config.get("building_filters", {})
    
    @property
    def graph_filters(self) -> Dict[str, Any]:
        """Get graph filters from config."""
        return self.config.get("graph_filters", {})

    @property
    def pandapipes(self) -> Dict[str, Any]:
        """Get pandapipes configuration."""
        return self.config.get("pandapipes", {})
