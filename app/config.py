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
            "data_dir": "./data",
            "polygon_path": "./data/polygon.geojson",
            "streets_path": "./data/streets.geojson",
            "buildings_path": "./data/buildings.geojson",
            "filtered_buildings_path": "./data/filtered_buildings.geojson",
            "network_path": "./data/heating_network.geojson",
            "network_graphml_path": "./data/heating_network.graphml",
            "filtered_network_graphml_path": "./data/filtered_heating_network.graphml",
            "filtered_network_path": "./data/filtered_heating_network.geojson",
            "heat_sources_path": "./data/heat_sources.geojson",
        },
        "heat_demand": {
            "gdb_path": "/gdb/GDB.gdb",
            "gdb_layer": "Raumwaermebedarf_ist",
            "heat_demand_column": "RW",
        },
        "map_settings": {
            "default_center": [50.9413, 6.9572],  # Cologne
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
        },
        "coordinate_system": {
            "target_crs": "EPSG:5243",
            "input_crs": "EPSG:4326"
        },
        "building_filters": {
            "exclude_zero_heat_demand": True,
            "min_heat_demand": "",
            "max_heat_demand": "",
            "postcodes": [""],
            "cities": [""],
            "building_uses": [""]
        },
        "building_clustering": {
            "auto_apply": True
        },
        "graph_filters": {
            "max_building_connection_distance": 20.0,
            "default_pruning_algorithm": "minimum_spanning_tree",
            "pruning_algorithms": {
                "minimum_spanning_tree": {},
                "all_building_connections": {},
                "steiner_tree": {}
            }
        },
        "pandapipes": {
            "enabled": True,
            "hydraulics": "2-pipe",
            "source_model": "ext_grid",
            "fluid": "water",
            "supply_temperature_C": 130.0,
            "return_temperature_C": 50.0,
            "delta_T_K": 30.0,
            "cp_J_per_kgK": 4180.0,
            "rho_kg_per_m3": 985.0,
            "min_junction_pressure_bar": 1.5,
            "source_pressure_bar": 20.0,
            "ext_grid_temperature_C": 130.0,
            "use_per_source_pressures": True,
            "use_per_source_temperatures": True,
            "target_velocity_m_per_s": 1.5,
            "max_velocity_m_per_s": 2.5,
            "roughness_m": 1.0e-4,
            "pipe_diameters_by_type_m": {
                "building_connection": 0.2,
                "street_segment": 0.8
            },
            "available_diameters_m": [0.032, 0.040, 0.050, 0.065, 0.080, 0.100, 0.125, 0.150, 0.200, 0.250],
            "building_heat_demand_unit": "kWh_per_year",
            "heat_source_capacity_unit": "kWh_per_year",
            "demand_scaling_factor": 1.0,
            "assume_continuous_operation_h_per_year": 2000,
            "multi_source_split": "by_capacity",
            "edge_types_as_pipes": ["street_segment", "building_connection", "heat_source_connection"],
            "run_after_build": False,
            "pipeflow": {
                "enabled": True,
                "friction_model": "swamee_jain",
                "mode": "all",
                "tol": 1e-6,
                "max_iter": 100
            },
            "output_paths": {
                "pandapipes_net_json_path": "./data/pandapipes/network.json",
                "pandapipes_dump_dir": "./data/pandapipes/",
                "pipe_results_geojson": "./data/pandapipes/pipe_results.geojson",
                "junction_results_csv": "./data/pandapipes/junction_results.csv",
                "pipe_results_csv": "./data/pandapipes/pipe_results.csv"
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
        # Use 'data_dir' from YAML config, which matches the YAML structure
        self.data_dir = self.config["data_paths"]["data_dir"]
        
        # Build paths using the direct path values from YAML
        self.polygon_path = self.config["data_paths"]["polygon_path"]
        self.streets_path = self.config["data_paths"]["streets_path"]
        self.buildings_path = self.config["data_paths"]["buildings_path"]
        self.filtered_buildings_path = self.config["data_paths"]["filtered_buildings_path"]
        self.network_path = self.config["data_paths"]["network_path"]
        self.network_graphml_path = self.config["data_paths"]["network_graphml_path"]
        self.filtered_network_graphml_path = self.config["data_paths"].get("filtered_network_graphml_path", "./data/filtered_heating_network.graphml")
        self.filtered_network_path = self.config["data_paths"].get("filtered_network_path", "./data/filtered_heating_network.geojson")
        self.heat_sources_path = self.config["data_paths"].get("heat_sources_path", "./data/heat_sources.geojson")
        
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
            "buildings_path": self.buildings_path,
            "filtered_buildings_path": self.filtered_buildings_path,
            "network_path": self.network_path,
            "network_graphml_path": self.network_graphml_path,
            "filtered_network_graphml_path": self.filtered_network_graphml_path,
            "filtered_network_path": self.filtered_network_path,
            "heat_sources_path": self.heat_sources_path
        }
    
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
        return self.config.get("building_filters", {
            "exclude_zero_heat_demand": True,
            "postcodes": [""],
            "cities": [""],
            "building_uses": [""]
        })
    
    @property
    def graph_filters(self) -> Dict[str, Any]:
        """Get graph filters from config."""
        return self.config.get("graph_filters", {
            "max_building_connection_distance": 20.0,
            "default_pruning_algorithm": "minimum_spanning_tree",
            "pruning_algorithms": {
                "minimum_spanning_tree": {"preserve_critical_nodes": True},
                "all_building_connections": {}
            }
        })

    @property
    def pandapipes(self) -> Dict[str, Any]:
        """Get pandapipes conversion defaults."""
        return self.config.get("pandapipes", self.DEFAULT_CONFIG.get("pandapipes", {}))
