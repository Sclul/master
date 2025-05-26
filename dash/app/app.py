import json
import logging
import os
import yaml

import osmnx as ox # type: ignore
from shapely.geometry import shape # type: ignore
import dash_leaflet as dl # type: ignore
from dash import dcc
from dash_extensions.enrich import DashProxy, Input, Output, html, no_update # type: ignore
from dash_extensions.javascript import assign # type: ignore


logger = logging.getLogger(__name__)

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.yml")
try:
    with open(CONFIG_PATH, "r") as f:
        config = yaml.safe_load(f)
    logger.info(f"Configuration loaded from {CONFIG_PATH}")
except FileNotFoundError:
    logger.error(f"Configuration file not found at {CONFIG_PATH}. Using default values.")
    # Provide default values or handle the error as appropriate
    config = {
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
        }
    }
except yaml.YAMLError as e:
    logger.error(f"Error parsing YAML configuration: {e}. Using default values.")
    # Provide default values or handle the error as appropriate
    config = {
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
        }
    }


# Set up logging
logging.basicConfig(
    level=logging.DEBUG if config["server_settings"]["debug"] else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)



logger.info("Starting app.py")


# Construct full paths for data files
DATA_DIR = config["data_paths"]["output_directory"]
POLYGON_PATH = os.path.join(DATA_DIR, config["data_paths"]["polygon_geojson"])
STREETS_PATH = os.path.join(DATA_DIR, config["data_paths"]["streets_geojson"])

# Ensure data directory exists
os.makedirs(DATA_DIR, exist_ok=True)

# Send data back to Dash.
event_handlers = dict(
    measurefinish=assign(
        """
        function(e, ctx) {
            ctx.setProps({coords: getAreaCoords(e)});
        }
        """
    ),

)



logger.debug(f"Event handlers set: {event_handlers}")

# Create small example app.
app = DashProxy()
logger.info("DashProxy app created")


app.layout = html.Div(
    [
        dl.Map(
            [
                dl.TileLayer(),
                dl.MeasureControl(
                    position="topleft",
                    primaryLengthUnit="meters",
                    primaryAreaUnit="sqmeters",
                    activeColor="blue",
                    completedColor="rgba(0, 0, 255, 0.6)" 
                ),
            ],
            eventHandlers=event_handlers,
            center=[52.5200, 13.4050],
            zoom=15,
            style={"height": "50vh"},
            id="map",
        ),
        dcc.Store(id="geojson-saved"),  # Hidden store to trigger log callback
        html.Div(id="log"),
    ]
)
logger.info("App layout set")

@app.callback(Output("geojson-saved", "data"), Input("map", "coords"))
def save_geojson(message):
    if isinstance(message, dict) and "coordinates" in message:
        coordinates = message["coordinates"]
        logger.debug(f"Polygon coordinates: {coordinates}")
        geojson = {
            "type": "Feature",
            "geometry": {
                "type": "Polygon",
                "coordinates": [coordinates],
            },
            "properties": {},
        }
        with open(POLYGON_PATH, "w") as f:
            json.dump(geojson, f, indent=2)
        try:
            polygon = shape(geojson["geometry"])
            G = ox.graph_from_polygon(
                polygon, 
                network_type=config["osmnx_settings"]["network_type"], 
                truncate_by_edge=True
            ) 
            if len(G.edges) == 0:
                logger.error("No streets found in the selected area.")
                return {"status": "no_streets"}

            # Project the graph to a suitable CRS for distance calculations
            G_proj = ox.project_graph(G)

            # Consolidate intersections
            G_consolidated = ox.simplification.consolidate_intersections(
                G_proj, 
                tolerance=config["osmnx_settings"]["consolidation_tolerance"], 
                rebuild_graph=True, 
                dead_ends=True
            )
            
            G_undirected = ox.convert.to_undirected(G_consolidated)

            # Convert the simplified graph back to GeoDataFrames
            gdf_edges = ox.graph_to_gdfs(G_undirected, nodes=False, edges=True) 
            gdf_edges.to_file(STREETS_PATH, driver="GeoJSON")
            logger.info(f"Streets saved to {STREETS_PATH}")
        except Exception as e:
            logger.error(f"Error saving streets.geojson: {e}")
            return {"status": "error", "message": str(e)}
        return {"status": "saved"}
    return no_update

@app.callback(Output("log", "children"), Input("geojson-saved", "data"))
def log(status):
    if status is not None and isinstance(status, dict):
        if status.get("status") == "no_streets":
            return "No streets found in the selected area."
        if status.get("status") == "error":
            return f"Error: {status.get('message')}"
    try:
        with open(STREETS_PATH, "r") as f:
            data = json.load(f)
        return json.dumps(data, indent=2)
    except FileNotFoundError:
        return "No streets saved yet."
    except Exception as e:
        return f"Error reading {STREETS_PATH}: {e}"

if __name__ == '__main__':
    logger.info("Running app")
    app.run(
        debug=config["server_settings"]["debug"], 
        host=config["server_settings"]["host"], 
        port=config["server_settings"]["port"]
    )