"""Dash layout components and UI elements."""
import dash_leaflet as dl # type: ignore
from dash import dcc
from dash_extensions.enrich import html # type: ignore
from dash_extensions.javascript import assign # type: ignore

from config import Config


config = Config()

def get_event_handlers():
    """Get JavaScript event handlers for the map."""
    return dict(
        measurefinish=assign(
            """
            function(e, ctx) {
                ctx.setProps({coords: getAreaCoords(e)});
            }
            """
        ),
    )


def create_map_component(event_handlers, center=None, zoom=None):
    """Create the main map component with controls."""
    # Use config values or fallback to parameters
    center = center or config.map_settings["default_center"]
    zoom = zoom or config.map_settings["default_zoom"]
    measure_settings = config.map_settings["measure_settings"]
    
    return dl.Map(
        [
            dl.TileLayer(
                url=config.map_settings["tile_url"],
                attribution=config.map_settings["attribution"]
            ),
            dl.MeasureControl(
                position=measure_settings["position"],
                primaryLengthUnit=measure_settings["primary_length_unit"],
                primaryAreaUnit=measure_settings["primary_area_unit"],
                activeColor=measure_settings["active_color"],
                completedColor=measure_settings["completed_color"] 
            ),
        ],
        eventHandlers=event_handlers,
        center=center,
        zoom=zoom,
        style={"height": "50vh"},
        id="map",
    )


def create_layout():
    """Create the main application layout."""
    event_handlers = get_event_handlers()
    
    return html.Div(
        [
            create_map_component(event_handlers),
            dcc.Store(id="geojson-saved"),  # Hidden store to trigger log callback
            html.Div(id="log"),
        ]
    )
