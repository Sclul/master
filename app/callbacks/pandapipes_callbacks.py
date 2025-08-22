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
                summary = html.Div([
                    html.P(f"Junctions: {result.get('junctions', 0)}"),
                    html.P(f"Pipes: {result.get('pipes', 0)}"),
                    html.P(f"Sinks: {result.get('sinks', 0)}"),
                    html.P(f"Sources: {result.get('sources', 0)}"),
                    html.P(f"Ext grids: {result.get('ext_grids', 0)}"),
                    html.P(f"Total sink mass flow: {result.get('total_sink_mdot_kg_per_s', 0.0):.4f} kg/s"),
                    html.P(f"Output: {result.get('json_path', '')}")
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
                    else html.Div("Pipeflow failed to converge", className="error-message")
                )
                # Display a compact summary
                def fmt(val, unit=""):
                    try:
                        return f"{float(val):.3f}{unit}"
                    except Exception:
                        return str(val)

                summary = html.Div([
                    html.P(f"p_min: {fmt(result.get('p_min_bar'), ' bar')}") ,
                    html.P(f"p_max: {fmt(result.get('p_max_bar'), ' bar')}") ,
                    html.P(f"v_max: {fmt(result.get('v_max_m_per_s'), ' m/s')}") ,
                    html.P(f"Friction model: {result.get('friction_model_used')}") ,
                    html.P(f"Hyd iters: {result.get('max_iter_hyd')}") ,
                    html.P(f"Pipe results: {result.get('pipe_results_geojson', '')}") ,
                    (html.P(f"Errors: {result.get('errors')}") if result.get('errors') else None)
                ], className="summary-display")

                logger.info(f"Pipeflow run summary: {result}")
                return status, summary
            except Exception as e:
                logger.exception("Error in pipeflow run callback")
                return html.Div(f"Pipeflow failed: {e}", className="error-message"), ""
