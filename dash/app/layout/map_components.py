"""Map-related UI components - simplified to essential features."""
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


def create_map_component(config=None):
    """Create the main map component with essential features only."""
    # Use default values if no config provided
    if config is None:
        center = [50.9413, 6.9572]
        zoom = 15
        tile_url = "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        attribution = "© OpenStreetMap contributors"
        measure_settings = {
            "position": "topleft",
            "primary_length_unit": "meters",
            "primary_area_unit": "sqmeters",
            "active_color": "blue",
            "completed_color": "rgba(0, 0, 255, 0.6)"
        }
    else:
        center = config.map_settings["default_center"]
        zoom = config.map_settings["default_zoom"]
        tile_url = config.map_settings["tile_url"]
        attribution = config.map_settings["attribution"]
        measure_settings = config.map_settings["measure_settings"]
    
    event_handlers = get_event_handlers()
    
    return html.Div([
        # Layer controls - simplified to only what you use
        html.Div([
            html.H4("Map Layers"),
            dcc.Checklist(
                id="layer-toggles",
                options=[
                    {"label": "Streets", "value": "streets"},
                    {"label": "Buildings", "value": "buildings"},
                    {"label": "Filtered Buildings", "value": "filtered"},
                ],
                value=[],
                className="layer-toggles"
            )
        ], className="layer-controls"),
        
        # Map
        dl.Map(
            [
                dl.TileLayer(url=tile_url, attribution=attribution),
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
            className="map",
            id="map",
        ),
        
        # Map info
        html.Div([
            html.Div(id="map-coordinates"),
            html.Div(id="map-zoom-info")
        ], className="map-info")
    ], className="map-container")