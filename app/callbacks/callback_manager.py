"""Main callback manager that coordinates all callback modules - simplified."""
import logging
from .geospatial_callbacks import GeospatialCallbacks
from .ui_callbacks import UICallbacks
from .map_callbacks import MapCallbacks

logger = logging.getLogger(__name__)


class CallbackManager:
    """Manages essential Dash callbacks for the application."""
    
    def __init__(self, app, config):
        """Initialize with Dash app and configuration."""
        self.app = app
        self.config = config
        
        # Initialize only essential callback modules
        self.geospatial = GeospatialCallbacks(app, config)
        self.ui = UICallbacks(app, config)
        self.map = MapCallbacks(app, config)
        
        logger.info("Essential callback modules initialized")