"""Base class for callback modules."""
import logging
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class BaseCallback(ABC):
    """Base class for all callback modules."""
    
    def __init__(self, app, config):
        """Initialize with Dash app and configuration."""
        self.app = app
        self.config = config
        self.data_paths = config.data_paths
        
        # Register callbacks for this module
        self._register_callbacks()
        logger.info(f"{self.__class__.__name__} callbacks registered")
    
    @abstractmethod
    def _register_callbacks(self):
        """Register callbacks specific to this module."""
        pass