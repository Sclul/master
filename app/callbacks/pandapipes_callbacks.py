"""Callbacks for Pandapipes simulation UI.

Wires the "Initialize Net" button to build the pandapipes network from the
current GraphML and reports a concise summary.
"""
import logging
from dash_extensions.enrich import Input, Output # type: ignore
from dash import html # type: ignore

from .base_callback import BaseCallback

logger = logging.getLogger(__name__)


class PandapipesCallbacks(BaseCallback):
    """Handles minimal UI interactions for Pandapipes simulation."""

    def __init__(self, app, config):
        super().__init__(app, config)

    def _register_callbacks(self):
        """Register minimal simulation-related callbacks."""

        @self.app.callback(
            [
                Output("sim-status", "children"),
                Output("sim-summary", "children")
            ],
            Input("sim-init-btn", "n_clicks"),
            prevent_initial_call=True
        )
        def on_sim_init(n_clicks):
            """Handle Initialize Net button: build pandapipes net from GraphML and summarize."""
            try:
                if not n_clicks:
                    return "", ""

                # Lazy import to avoid any circulars and speed idle init
                from pandapipes_builder import PandapipesBuilder  # type: ignore
                from utils.progress_tracker import progress_tracker  # type: ignore

                progress_tracker.start("Initializing pandapipes net...")

                builder = PandapipesBuilder(self.config)
                result = builder.build_from_graphml()

                progress_tracker.complete("Pandapipes net created")

                status = html.Div("Pandapipes net initialized", className="success-message")
                
                # Display two-pipe network statistics
                summary = html.Div([
                    html.H4("Two-Pipe Network Summary", style={"marginBottom": "10px"}),
                    html.P(f"Junctions (Supply): {result.get('junctions_supply', 0)}"),
                    html.P(f"Junctions (Return): {result.get('junctions_return', 0)}"),
                    html.P(f"Total Junctions: {result.get('junctions_total', 0)}"),
                    html.Hr(style={"margin": "10px 0"}),
                    html.P(f"Pipes (Supply): {result.get('pipes_supply', 0)}"),
                    html.P(f"Pipes (Return): {result.get('pipes_return', 0)}"),
                    html.P(f"Total Pipes: {result.get('pipes_total', 0)}"),
                    html.P(f"Pipes clamped to min length: {result.get('pipes_clamped_to_min_length', 0)}"),
                    html.Hr(style={"margin": "10px 0"}),
                    html.P(f"Building Heat Exchangers: {result.get('building_heat_exchangers', 0)}"),
                    html.P(f"Total Heat Load: {result.get('total_heat_load_W', 0.0)/1000:.1f} kW"),
                    html.Hr(style={"margin": "10px 0"}),
                    html.P(f"Circulation Pumps: {result.get('circulation_pumps', 0)}"),
                    html.P(f"Plant Pump Mass Flow: {result.get('plant_pump_mass_flow_kg_per_s', 0.0):.4f} kg/s ({result.get('plant_pump_mass_flow_source', 'unknown')})"),
                    html.Hr(style={"margin": "10px 0"}),
                    html.P(f"Pruned Nodes: {result.get('pruned_nodes', 0)}"),
                    html.P(f"Pruned Edges: {result.get('pruned_edges', 0)}"),
                    html.Hr(style={"margin": "10px 0"}),
                    html.P(f"Output: {result.get('json_path', '')}", style={"fontSize": "0.9em", "color": "#666"})
                ], className="summary-display")

                logger.info(f"Pandapipes net build summary: {result}")
                return status, summary
            except Exception as e:
                logger.exception("Error in sim init callback")
                # Provide a concise error to UI
                return html.Div(f"Initialization failed: {e}", className="error-message"), ""

        @self.app.callback(
            [
                Output("sim-status", "children"),
                Output("sim-summary", "children")
            ],
            Input("sim-run-btn", "n_clicks"),
            prevent_initial_call=True
        )
        def on_sim_run(n_clicks):
            """Run pandapipes pipeflow on last-built network and summarize."""
            try:
                if not n_clicks:
                    return "", ""

                from pandapipes_builder import PandapipesBuilder  # type: ignore
                from utils.progress_tracker import progress_tracker  # type: ignore

                progress_tracker.start("Running pipeflow...")

                # Use configuration defaults (max_iter fixed in PandapipesBuilder)
                builder = PandapipesBuilder(self.config)
                result = builder.run_pipeflow()
                progress_tracker.complete("Pipeflow complete")

                status = (
                    html.Div("Pipeflow completed", className="success-message")
                    if result.get("converged", True)
                    else html.Div([
                        html.P("Pipeflow failed to converge", style={"fontWeight": "bold", "marginBottom": "5px"}),
                        html.P(f"Mode: {result.get('mode', 'unknown')}", style={"fontSize": "0.9em"}),
                        html.P(f"Errors: {', '.join(result.get('errors', []))}", style={"fontSize": "0.9em", "color": "#c00"})
                    ], className="error-message")
                )
                # Display a compact summary
                def fmt(val, unit=""):
                    try:
                        return f"{float(val):.3f}{unit}"
                    except Exception:
                        return str(val)

                summary = html.Div([
                    html.P(f"Mode: {result.get('mode', 'unknown')}"),
                    html.P(f"Converged: {'Yes' if result.get('converged') else 'No'}"),
                    html.Hr(style={"margin": "8px 0"}),
                    html.P(f"Pressure min: {fmt(result.get('p_min_bar'), ' bar')}"),
                    html.P(f"Pressure max: {fmt(result.get('p_max_bar'), ' bar')}"),
                    html.P(f"Velocity max: {fmt(result.get('v_max_m_per_s'), ' m/s')}"),
                    html.Hr(style={"margin": "8px 0"}),
                    html.P(f"Friction model: {result.get('friction_model_used', 'N/A')}"),
                    html.P(f"Max hydraulic iterations: {result.get('max_iter_hyd', 'N/A')}"),
                    html.P(f"Max thermal iterations: {result.get('max_iter_therm', 'N/A')}"),
                    html.Hr(style={"margin": "8px 0"}),
                    html.P(f"Pipe results: {result.get('pipe_results_geojson', '')}", style={"fontSize": "0.9em"}),
                    (html.Div([
                        html.P("Errors:", style={"fontWeight": "bold", "color": "#c00", "marginBottom": "3px"}),
                        html.Ul([html.Li(err) for err in result.get('errors', [])])
                    ]) if result.get('errors') else None)
                ], className="summary-display")

                logger.info(f"Pipeflow run summary: {result}")
                return status, summary
            except Exception as e:
                logger.exception("Error in pipeflow run callback")
                return html.Div(f"Pipeflow failed: {e}", className="error-message"), ""
