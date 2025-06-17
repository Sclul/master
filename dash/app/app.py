"""Main Dash application entry point."""
import logging
from dash_extensions.enrich import DashProxy, MultiplexerTransform # type: ignore

from config import Config
from layout.main_layout import create_layout
from callbacks.callback_manager import CallbackManager

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def create_app():
    """Create and configure the Dash application."""
    try:
        # Load configuration
        config = Config()
        logger.info("Configuration loaded successfully")
        
        # Create Dash app
        app = DashProxy(
            __name__,
            transforms=[MultiplexerTransform()],
            suppress_callback_exceptions=True
        )
        
        # Set layout
        app.layout = create_layout(config)
        logger.info("App layout configured")
        
        # Initialize callbacks
        callback_manager = CallbackManager(app, config)
        logger.info("Callbacks initialized")
        
        return app
        
    except Exception as e:
        logger.error(f"Failed to create app: {e}")
        raise


# Create the app instance
app = create_app()

if __name__ == "__main__":
    config = Config()
    server_settings = config.server_settings
    
    app.run(
        host=server_settings["host"],
        port=server_settings["port"],
        debug=server_settings["debug"]
    )