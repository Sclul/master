"""Callbacks for progress bar updates."""
import logging
import threading
from dash_extensions.enrich import Input, Output, State, no_update # type: ignore
from dash import html # type: ignore

from .base_callback import BaseCallback

logger = logging.getLogger(__name__)


class ProgressCallbacks(BaseCallback):
    """Handles callbacks related to progress bar updates."""
    
    def _register_callbacks(self):
        """Register progress-related callbacks."""
        
        @self.app.callback(
            [Output("progress-modal", "className"),
             Output("progress-modal-icon", "className"),
             Output("progress-modal-title", "children"),
             Output("progress-modal-bar", "style"),
             Output("progress-modal-bar", "className"),
             Output("progress-modal-details", "children")],
            [Input("progress-interval", "n_intervals")],
            prevent_initial_call=True
        )
        def update_progress_modal(n_intervals):
            """Update bottom sheet modal for long-running operations."""
            from utils.progress_tracker import progress_tracker
            
            state = progress_tracker.get_state()
            
            # Modal visibility - show when active
            modal_class = "progress-modal visible" if state["active"] else "progress-modal hidden"
            
            # Icon state (spinner, success, error)
            if not state["active"]:
                icon_class = "progress-modal-icon"
            elif state["error"]:
                icon_class = "progress-modal-icon error"
            elif state["value"] >= 100:
                icon_class = "progress-modal-icon success"
            else:
                icon_class = "progress-modal-icon spinning"
            
            # Title
            title = state["message"] if state["active"] else "Ready"
            
            # Progress bar style
            bar_style = {"width": f"{state['value']}%"}
            
            # Progress bar class (red for error)
            bar_class = "progress-modal-bar-fill error" if state["error"] else "progress-modal-bar-fill"
            
            # Details (percentage, items, ETA)
            if not state["active"]:
                details = ""
            else:
                details_parts = [f"{state['value']}% complete"]
                
                if state["total_items"] and state["processed_items"] is not None:
                    details_parts.append(f"{state['processed_items']:,} / {state['total_items']:,} items")
                
                if state["eta"] and state["eta"] > 0:
                    eta_str = f"{int(state['eta'] // 60)}m {int(state['eta'] % 60)}s" if state['eta'] > 60 else f"{int(state['eta'])}s"
                    details_parts.append(f"~{eta_str} remaining")
                
                details = " • ".join(details_parts)
            
            return modal_class, icon_class, title, bar_style, bar_class, details
        
        # Button loading state callbacks
        @self.app.callback(
            [Output("start-measurement-btn", "disabled", allow_duplicate=True),
             Output("start-measurement-btn-spinner", "className")],
            [Input("progress-interval", "n_intervals")],
            prevent_initial_call=True
        )
        def update_measurement_button_state(n_intervals):
            """Update measurement button loading state."""
            from utils.progress_tracker import progress_tracker
            state = progress_tracker.get_state()
            
            # Check if measurement operation is active
            is_measuring = state["active"] and any(keyword in state["message"].lower() 
                                                   for keyword in ["extract", "building", "street", "polygon"])
            
            disabled = is_measuring
            spinner_class = "btn-spinner" if is_measuring else "btn-spinner hidden"
            
            return disabled, spinner_class
        
        @self.app.callback(
            [Output("generate-network-btn", "disabled", allow_duplicate=True),
             Output("generate-network-btn-spinner", "className")],
            [Input("progress-interval", "n_intervals")],
            prevent_initial_call=True
        )
        def update_generate_network_button_state(n_intervals):
            """Update generate network button loading state."""
            from utils.progress_tracker import progress_tracker
            state = progress_tracker.get_state()
            
            # Check if network generation is active
            is_generating = state["active"] and "network" in state["message"].lower() and "optim" not in state["message"].lower()
            
            disabled = is_generating
            spinner_class = "btn-spinner" if is_generating else "btn-spinner hidden"
            
            return disabled, spinner_class
        
        @self.app.callback(
            [Output("optimize-network-btn", "disabled", allow_duplicate=True),
             Output("optimize-network-btn-spinner", "className")],
            [Input("progress-interval", "n_intervals")],
            prevent_initial_call=True
        )
        def update_optimize_network_button_state(n_intervals):
            """Update optimize network button loading state."""
            from utils.progress_tracker import progress_tracker
            state = progress_tracker.get_state()
            
            # Check if optimization is active
            is_optimizing = state["active"] and "optim" in state["message"].lower()
            
            disabled = is_optimizing
            spinner_class = "btn-spinner" if is_optimizing else "btn-spinner hidden"
            
            return disabled, spinner_class
        
        @self.app.callback(
            [Output("apply-filters-btn", "disabled", allow_duplicate=True),
             Output("apply-filters-btn-spinner", "className")],
            [Input("progress-interval", "n_intervals")],
            prevent_initial_call=True
        )
        def update_filter_button_state(n_intervals):
            """Update filter button loading state."""
            from utils.progress_tracker import progress_tracker
            state = progress_tracker.get_state()
            
            # Check if filtering is active
            is_filtering = state["active"] and "filter" in state["message"].lower()
            
            disabled = is_filtering
            spinner_class = "btn-spinner" if is_filtering else "btn-spinner hidden"
            
            return disabled, spinner_class
        
        @self.app.callback(
            [Output("sim-init-btn", "disabled", allow_duplicate=True),
             Output("sim-init-btn-spinner", "className")],
            [Input("progress-interval", "n_intervals")],
            prevent_initial_call=True
        )
        def update_sim_init_button_state(n_intervals):
            """Update simulation init button loading state."""
            from utils.progress_tracker import progress_tracker
            state = progress_tracker.get_state()
            
            # Check if initialization is active
            is_initializing = state["active"] and "initializ" in state["message"].lower()
            
            disabled = is_initializing
            spinner_class = "btn-spinner" if is_initializing else "btn-spinner hidden"
            
            return disabled, spinner_class
        
        @self.app.callback(
            [Output("sim-run-btn", "disabled", allow_duplicate=True),
             Output("sim-run-btn-spinner", "className")],
            [Input("progress-interval", "n_intervals")],
            prevent_initial_call=True
        )
        def update_sim_run_button_state(n_intervals):
            """Update simulation run button loading state."""
            from utils.progress_tracker import progress_tracker
            state = progress_tracker.get_state()
            
            # Check if pipeflow is active
            is_running = state["active"] and "pipeflow" in state["message"].lower()
            
            disabled = is_running
            spinner_class = "btn-spinner" if is_running else "btn-spinner hidden"
            
            return disabled, spinner_class
