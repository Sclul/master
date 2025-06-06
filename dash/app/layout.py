"""Dash layout components and UI elements."""
import dash_leaflet as dl # type: ignore
from dash import dcc
from dash_extensions.enrich import html # type: ignore
from dash_extensions.javascript import assign # type: ignore


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


def create_map_component(event_handlers, center=[52.5200, 13.4050], zoom=15):
    """Create the main map component with controls."""
    return dl.Map(
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
