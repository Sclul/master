"""Callbacks for Pandapipes simulation UI.

Wires the "Initialize Net" button to build the pandapipes network from the
current GraphML and reports a concise summary.
"""
import logging
from dash_extensions.enrich import Input, Output, State # type: ignore
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
                Output("sim-summary", "children"),
                Output("heat-source-summary", "children", allow_duplicate=True)
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
                from dash_extensions.enrich import no_update  # type: ignore
                if not n_clicks:
                    return "", "", no_update

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
                
                # Update heat source summary with actual production capacity in demand mode
                heat_source_summary_update = no_update
                if mode == "demand":
                    # In demand mode, calculate actual production capacity from total heat load
                    total_heat_load_w = result.get('total_heat_load_W', 0.0)
                    
                    # Convert to GWh/year using the same operating hours
                    if operating_hours and operating_hours > 0:
                        op_hours = operating_hours
                    else:
                        op_hours = float(self.config.pandapipes.get("assume_continuous_operation_h_per_year", 2000))
                    
                    # Convert from W to GWh/year: W → kW → kWh/year → GWh/year
                    # total_heat_load_w is design power (W), multiply by op_hours to get annual energy
                    total_production_kwh_year = (total_heat_load_w / 1000.0) * op_hours
                    
                    # Convert to appropriate unit (same logic as Total Heat Demand display)
                    if total_production_kwh_year >= 1_000_000:
                        production_value = total_production_kwh_year / 1_000_000
                        production_unit = "GWh/year"
                    elif total_production_kwh_year >= 1_000:
                        production_value = total_production_kwh_year / 1_000
                        production_unit = "MWh/year"
                    else:
                        production_value = total_production_kwh_year
                        production_unit = "kWh/year"
                    
                    # Get heat source count
                    from heat_source_handler import HeatSourceHandler
                    handler = HeatSourceHandler(self.config)
                    summary_data = handler.get_heat_sources_summary()
                    heat_source_count = summary_data.get('total_count', 0)
                    
                    # Create updated heat source summary
                    heat_source_metrics = [
                        create_metric_card(
                            label="Total Heat Sources",
                            value=heat_source_count,
                            unit="sources"
                        ),
                        create_metric_card(
                            label="Total Production Capacity",
                            value=production_value,
                            unit=production_unit
                        )
                    ]
                    
                    heat_source_summary_update = create_metric_group(
                        title="Heat Source Summary",
                        metrics=heat_source_metrics
                    )
                
                return status_message.success("Pandapipes net initialized"), summary, heat_source_summary_update
            except Exception as e:
                logger.exception("Error in sim init callback")
                # Provide a concise error to UI
                from dash_extensions.enrich import no_update  # type: ignore
                return status_message.error("Initialization failed", details=str(e)), "", no_update

        @self.app.callback(
            [
                Output("sim-status", "children"),
                Output("sim-summary", "children"),
                Output("sim-run-state-store", "data"),
                Output("validation-alert", "children"),
                Output("validation-alert", "style")
            ],
            Input("sim-run-btn", "n_clicks"),
            prevent_initial_call=True
        )
        def on_sim_run(n_clicks):
            """Run pandapipes pipeflow on last-built network and summarize."""
            try:
                if not n_clicks:
                    return "", "", None, "", {'display': 'none'}

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
                
                # Build validation alert
                validation_alert, alert_style = self._build_validation_alert(
                    result.get("validation", {})
                )
                
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
                
                return status_msg, summary, pipeflow_state, validation_alert, alert_style
            except Exception as e:
                logger.exception("Error in pipeflow run callback")
                return status_message.error("Pipeflow failed", details=str(e)), "", None, "", {'display': 'none'}
        
        # Add callback to toggle validation alert expansion
        @self.app.callback(
            [
                Output("validation-alert-body", "className"),
                Output("validation-alert-toggle-icon", "className")
            ],
            [Input("validation-alert-header", "n_clicks")],
            [State("validation-alert-body", "className")],
            prevent_initial_call=True
        )
        def toggle_validation_details(n_clicks, current_class):
            """Toggle validation alert body expansion."""
            if not n_clicks:
                return current_class or "", "validation-alert-toggle"
            
            is_expanded = "expanded" in (current_class or "")
            
            if is_expanded:
                return "", "validation-alert-toggle"
            else:
                return "validation-alert-body expanded", "validation-alert-toggle expanded"
    
    def _build_validation_alert(self, validation: dict) -> tuple:
        """
        Build validation alert component from validation dict.
        
        Returns:
            (alert_content, alert_style) tuple
        """
        if not validation:
            return "", {'display': 'none'}
        
        critical = validation.get('critical', [])
        warnings = validation.get('warnings', [])
        info = validation.get('info', [])
        
        # If all clear, show success message
        if not critical and not warnings and not info:
            alert_content = html.Div([
                html.Div(
                    "All validation checks passed",
                    className="validation-alert-header",
                    style={'cursor': 'default'}
                )
            ], className="validation-alert severity-success")
            
            return alert_content, {'display': 'block', 'marginBottom': '1rem'}
        
        # Determine severity (highest priority)
        if critical:
            severity = 'critical'
            title = 'Critical Issues'
        elif warnings:
            severity = 'warning'
            title = 'Warnings'
        else:
            severity = 'info'
            title = 'Information'
        
        # Count messages
        critical_count = len(critical)
        warning_count = len(warnings)
        info_count = len(info)
        
        # Build summary text
        summary_parts = []
        if critical_count:
            summary_parts.append(f"{critical_count} critical")
        if warning_count:
            summary_parts.append(f"{warning_count} warning{'s' if warning_count > 1 else ''}")
        if info_count:
            summary_parts.append(f"{info_count} info")
        summary_text = f"{title}: {', '.join(summary_parts)}"
        
        # Build message list
        messages = []
        for msg in critical:
            messages.append(html.Li(msg, className="critical"))
        for msg in warnings:
            messages.append(html.Li(msg, className="warning"))
        for msg in info:
            messages.append(html.Li(msg, className="info"))
        
        # Build collapsible alert
        alert_content = html.Div([
            html.Div(
                [
                    html.Span(summary_text),
                    html.Span("▼", id="validation-alert-toggle-icon", className="validation-alert-toggle")
                ],
                id="validation-alert-header",
                className="validation-alert-header"
            ),
            html.Div(
                html.Ul(messages, className="validation-message-list"),
                id="validation-alert-body",
                className="validation-alert-body"
            )
        ], className=f"validation-alert severity-{severity}")
        
        alert_style = {'display': 'block', 'marginBottom': '1rem'}
        
        return alert_content, alert_style
