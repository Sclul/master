"""Callbacks for Pandapipes simulation UI.

Wires the "Initialize Net" button to build the pandapipes network from the
current GraphML and reports a concise summary.
"""
import logging
from dash_extensions.enrich import Input, Output # type: ignore
from dash import html # type: ignore

from .base_callback import BaseCallback
from utils.status_messages import status_message

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
            [
                Input("sim-init-btn", "n_clicks"),
                Input("operating-hours-store", "data"),
                Input("mass-flow-mode-store", "data")
            ],
            prevent_initial_call=True
        )
        def on_sim_init(n_clicks, operating_hours, mass_flow_mode):
            """Handle Initialize Net button: build pandapipes net from GraphML and summarize."""
            try:
                if not n_clicks:
                    return "", ""

                # Lazy import to avoid any circulars and speed idle init
                from pandapipes_builder import PandapipesBuilder  # type: ignore
                from utils.progress_tracker import progress_tracker  # type: ignore

                progress_tracker.start("Initializing pandapipes net...")

                builder = PandapipesBuilder(self.config)
                
                # Use demand mode as default if not specified
                mode = mass_flow_mode if mass_flow_mode else "demand"
                result = builder.build_from_graphml(operating_hours=operating_hours, mass_flow_mode=mode)

                progress_tracker.complete("Pandapipes net created")

                # Import metric card components
                from layout.ui_components import create_metric_card, create_metric_group
                
                # Create metric cards organized by category
                
                # Junctions group
                junction_metrics = [
                    create_metric_card(
                        label="Supply Junctions",
                        value=result.get('junctions_supply', 0),
                        unit="junctions"
                    ),
                    create_metric_card(
                        label="Return Junctions",
                        value=result.get('junctions_return', 0),
                        unit="junctions"
                    ),
                    create_metric_card(
                        label="Total Junctions",
                        value=result.get('junctions_total', 0),
                        unit="junctions"
                    )
                ]
                
                # Pipes group
                pipe_metrics = [
                    create_metric_card(
                        label="Supply Pipes",
                        value=result.get('pipes_supply', 0),
                        unit="pipes"
                    ),
                    create_metric_card(
                        label="Return Pipes",
                        value=result.get('pipes_return', 0),
                        unit="pipes"
                    ),
                    create_metric_card(
                        label="Total Pipes",
                        value=result.get('pipes_total', 0),
                        unit="pipes"
                    ),
                    create_metric_card(
                        label="Clamped to Min Length",
                        value=result.get('pipes_clamped_to_min_length', 0),
                        unit="pipes"
                    )
                ]
                
                # Components group
                component_metrics = [
                    create_metric_card(
                        label="Building Heat Exchangers",
                        value=result.get('building_heat_exchangers', 0),
                        unit="exchangers"
                    ),
                    create_metric_card(
                        label="Total Heat Load",
                        value=result.get('total_heat_load_W', 0.0) / 1000,
                        unit="kW"
                    ),
                    create_metric_card(
                        label="Circulation Pumps",
                        value=result.get('circulation_pumps', 0),
                        unit="pumps"
                    ),
                    create_metric_card(
                        label=f"Pump Mass Flow ({result.get('plant_pump_mass_flow_source', 'unknown')})",
                        value=result.get('plant_pump_mass_flow_kg_per_s', 0.0),
                        unit="kg/s"
                    )
                ]
                
                # Pruning statistics
                pruning_metrics = []
                if result.get('pruned_nodes', 0) > 0 or result.get('pruned_edges', 0) > 0:
                    pruning_metrics = [
                        create_metric_card(
                            label="Pruned Nodes",
                            value=result.get('pruned_nodes', 0),
                            unit="nodes"
                        ),
                        create_metric_card(
                            label="Pruned Edges",
                            value=result.get('pruned_edges', 0),
                            unit="edges"
                        )
                    ]
                
                # Combine all groups
                summary_groups = [
                    create_metric_group("Junctions", junction_metrics),
                    create_metric_group("Pipes", pipe_metrics),
                    create_metric_group("Components", component_metrics)
                ]
                
                if pruning_metrics:
                    summary_groups.append(create_metric_group("Pruning Statistics", pruning_metrics))
                
                summary = html.Div(summary_groups)

                logger.info(f"Pandapipes net build summary: {result}")
                return status_message.success("Pandapipes net initialized"), summary
            except Exception as e:
                logger.exception("Error in sim init callback")
                # Provide a concise error to UI
                return status_message.error("Initialization failed", details=str(e)), ""

        @self.app.callback(
            [
                Output("sim-status", "children"),
                Output("sim-summary", "children"),
                Output("sim-run-state-store", "data")
            ],
            Input("sim-run-btn", "n_clicks"),
            prevent_initial_call=True
        )
        def on_sim_run(n_clicks):
            """Run pandapipes pipeflow on last-built network and summarize."""
            try:
                if not n_clicks:
                    return "", "", None

                from pandapipes_builder import PandapipesBuilder  # type: ignore
                from utils.progress_tracker import progress_tracker  # type: ignore

                progress_tracker.start("Running pipeflow...")

                # Use configuration defaults (max_iter fixed in PandapipesBuilder)
                builder = PandapipesBuilder(self.config)
                result = builder.run_pipeflow()
                progress_tracker.complete("Pipeflow complete")

                # Status message based on convergence
                if result.get("converged", True):
                    status_msg = status_message.success("Pipeflow completed")
                else:
                    error_details = [
                        f"Mode: {result.get('mode', 'unknown')}"
                    ]
                    if result.get('errors'):
                        error_details.append(f"Errors: {', '.join(result.get('errors', []))}")
                    status_msg = status_message.error("Pipeflow failed to converge", details=error_details)
                
                # Import metric card components
                from layout.ui_components import (
                    create_metric_card, 
                    create_range_metric, 
                    create_status_metric,
                    create_metric_group
                )
                
                # Convergence status
                convergence_metrics = [
                    create_status_metric(
                        label="Convergence Status",
                        status=result.get('converged', False),
                        success_text="Converged",
                        failure_text="Failed"
                    ),
                    create_metric_card(
                        label="Simulation Mode",
                        value=result.get('mode', 'unknown')
                    )
                ]
                
                # Hydraulic results
                hydraulic_metrics = [
                    create_range_metric(
                        label="Pressure Range",
                        min_val=result.get('p_min_bar', 0),
                        max_val=result.get('p_max_bar', 0),
                        unit="bar"
                    ),
                    create_metric_card(
                        label="Maximum Velocity",
                        value=result.get('v_max_m_per_s', 0),
                        unit="m/s"
                    )
                ]
                
                # Combine groups
                summary_groups = [
                    create_metric_group("Convergence", convergence_metrics),
                    create_metric_group("Hydraulic Results", hydraulic_metrics)
                ]
                
                # Add errors if present
                if result.get('errors'):
                    error_display = html.Div([
                        html.H4("Errors", className="metric-group-title", style={"color": "var(--error-600)"}),
                        html.Ul([html.Li(err, style={"color": "var(--error-600)"}) for err in result.get('errors', [])])
                    ], className="metric-group")
                    summary_groups.append(error_display)
                
                summary = html.Div(summary_groups)

                logger.info(f"Pipeflow run summary: {result}")
                
                # Store pipeflow completion state
                pipeflow_state = {
                    "completed": True,
                    "converged": result.get("converged", True),
                    "timestamp": n_clicks
                }
                
                return status_msg, summary, pipeflow_state
            except Exception as e:
                logger.exception("Error in pipeflow run callback")
                return status_message.error("Pipeflow failed", details=str(e)), "", None
