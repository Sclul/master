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
            [Output("progress-container", "style"),
             Output("progress-container", "className"),
             Output("progress-bar", "style"),
             Output("progress-bar", "className"),
             Output("progress-title", "children"),
             Output("progress-details", "children"),
             Output("progress-interval", "disabled")],
            [Input("progress-interval", "n_intervals")],
            prevent_initial_call=True
        )
        def update_progress(n_intervals):
            """Update progress bar display with enhanced visual feedback."""
            from utils.progress_tracker import progress_tracker
            
            state = progress_tracker.get_state()
            
            # Container styling and classes
            container_style = {"display": "block"}
            container_class = "progress-widget active" if state["active"] else "progress-widget"
            
            # Progress bar color based on state
            bar_color = "#dc3545" if state["error"] else "#007bff"  # Red for error, blue for normal
            
            # Progress bar style with current width and enhanced styling
            progress_bar_style = {
                "width": f"{state['value']}%" if state["active"] else "0%",
                "background": f"linear-gradient(90deg, {bar_color}, {bar_color}dd)" if state["error"] else None
            }
            
            # Add shimmer effect for active operations
            progress_bar_class = "progress-bar-fill active" if state["active"] and not state["error"] else "progress-bar-fill"
            
            # Title and details based on state
            if not state["active"]:
                title = "Ready"
                details = "No operation in progress"
            elif state["error"]:
                title = "❌ Error"
                details = state["message"]
            else:
                # Format ETA with icon
                title = f"⚡ {state['message']}"
                
                # Build details with item counts and ETA
                details_parts = [f"{state['value']}% complete"]
                
                if state["total_items"] and state["processed_items"] is not None:
                    details_parts.append(f"{state['processed_items']:,}/{state['total_items']:,} items")
                
                if state["eta"] and state["eta"] > 0:
                    eta_str = f"{int(state['eta'] // 60)}m {int(state['eta'] % 60)}s" if state['eta'] > 60 else f"{int(state['eta'])}s"
                    details_parts.append(f"~{eta_str} remaining")
                
                details = " • ".join(details_parts)
            
            # Auto-reset after completion - but only if no new operation has started
            if state["value"] >= 100 and not state["error"] and state["active"]:
                def reset_progress():
                    import time
                    time.sleep(3)  # Wait 3 seconds before resetting
                    # Only reset if still at 100% (no new operation started)
                    current_state = progress_tracker.get_state()
                    if current_state["value"] >= 100 and current_state["active"]:
                        progress_tracker.reset()
                
                # Store timer reference so it can be cancelled if needed
                timer = threading.Timer(3.0, reset_progress)
                progress_tracker._reset_timer = timer
                timer.start()
            
            return (
                container_style,
                container_class,
                progress_bar_style,
                progress_bar_class,
                title,
                details,
                False  # Keep interval always active
            )
        
        @self.app.callback(
            Output("progress-interval", "disabled", allow_duplicate=True),
            [Input("generate-network-btn", "n_clicks"), 
             Input("optimize-network-btn", "n_clicks")],
            prevent_initial_call=True
        )
        def enable_progress_interval(network_clicks, optimize_clicks):
            """Enable progress interval when any long-running operation starts."""
            # Enable the interval to start tracking progress
            return False
