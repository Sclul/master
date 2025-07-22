"""Map-related UI components."""
import dash_leaflet as dl # type: ignore
from dash import dcc # type: ignore
from dash_extensions.enrich import html # type: ignore
from dash_extensions.javascript import assign # type: ignore


def get_event_handlers():
    """Get JavaScript event handlers for the map."""
    return dict(
        measurefinish=assign(
            """
            function(e, ctx) {
                ctx.setProps({coords: autoDeleteMeasurement(e)});
            }
            """
        ),
        click=assign(
            """
            function(e, ctx) {
                ctx.setProps({click_lat_lng: [e.latlng.lat, e.latlng.lng]});
            }
            """
        ),
    )


def create_map_component(config=None):
    """Create a clean, minimal map component for desktop use."""
    # Default configuration
    defaults = {
        "center": [50.9413, 6.9572],
        "zoom": 15,
        "tile_url": "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
        "attribution": "© OpenStreetMap contributors",
        "measure_settings": {
            "position": "topleft",
            "primary_length_unit": "meters",
            "primary_area_unit": "sqmeters",
            "active_color": "blue",
            "completed_color": "rgba(0, 0, 255, 0.6)"
        }
    }
    
    # Use config values or defaults
    if config:
        center = config.map_settings["default_center"]
        zoom = config.map_settings["default_zoom"]
        tile_url = config.map_settings["tile_url"]
        attribution = config.map_settings["attribution"]
        measure_settings = config.map_settings["measure_settings"]
    else:
        center = defaults["center"]
        zoom = defaults["zoom"]
        tile_url = defaults["tile_url"]
        attribution = defaults["attribution"]
        measure_settings = defaults["measure_settings"]
    
    event_handlers = get_event_handlers()
    
    return html.Div([
        # Layer controls bar above map
        html.Div([
            dcc.Checklist(
                id="layer-toggles",
                options=[
                    {"label": "Streets", "value": "streets"},
                    {"label": "Buildings", "value": "buildings"},
                    {"label": "Filtered", "value": "filtered"},
                    {"label": "Network", "value": "network"},
                    {"label": "Filtered Network", "value": "filtered_network"},
                    {"label": "Heat Sources", "value": "heat_sources"},
                ],
                value=[],
                className="map-layer-controls"
            )
        ], className="map-controls-bar"),
        
        # Clean map component
        dl.Map([
            dl.TileLayer(url=tile_url, attribution=attribution),
            dl.MeasureControl(
                position=measure_settings["position"],
                primaryLengthUnit=measure_settings["primary_length_unit"],
                primaryAreaUnit=measure_settings["primary_area_unit"],
                activeColor=measure_settings["active_color"],
                completedColor=measure_settings["completed_color"] 
            ),
            dl.LayerGroup(id="data-layers", children=[])
        ],
        eventHandlers=event_handlers,
        center=center,
        zoom=zoom,
        className="map",
        id="map")
    ], className="map-container")