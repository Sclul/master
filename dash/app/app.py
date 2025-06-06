"""Main application entry point for the Dash OSM Street Processor."""
import logging
from dash_extensions.enrich import DashProxy # type: ignore

from config import Config
from layout import create_layout
from callbacks import CallbackManager


def create_app():
    """Create and configure the Dash application."""
    # Initialize configuration
    config = Config()
    
    logger = logging.getLogger(__name__)
    logger.info("Starting Dash OSM Street Processor")
    
    # Create Dash app
    app = DashProxy()
    logger.info("DashProxy app created")
    
    # Set layout
    app.layout = create_layout()
    logger.info("App layout set")
    
    # Register callbacks
    CallbackManager(app, config)
    logger.info("Callbacks registered")
    
    return app, config

if __name__ == '__main__':
    app, config = create_app()
    
    logger = logging.getLogger(__name__)
    logger.info("Running app")
    
    app.run(
        debug=config.server_settings["debug"], 
        host=config.server_settings["host"], 
        port=config.server_settings["port"]
    )