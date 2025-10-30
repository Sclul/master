"""Callbacks for managing pipeline workflow state and UI locking."""

import logging
from pathlib import Path
from dash import Output, Input, State, html
from dash.exceptions import PreventUpdate
from callbacks.base_callback import BaseCallback

logger = logging.getLogger(__name__)


class PipelineStateCallbacks(BaseCallback):
    """Manages pipeline progression, step completion, and UI lock states."""
    
    def __init__(self, app, config):
        super().__init__(app, config)
        self.data_paths = config.data_paths
    
    def _register_callbacks(self):
        """Register all pipeline state management callbacks."""
        
        # Main state updater - checks file system for completion
        @self.app.callback(
            Output('pipeline-state-store', 'data'),
            [
                Input('data-summary', 'children'),  # Triggers after building extraction
                Input('heat-source-summary', 'children'),  # Triggers after heat source ops
                Input('heat-sources-data', 'data'),  # Triggers when heat sources change
                Input('filter-status', 'children'),  # Triggers after filtering
                Input('network-status', 'children'),  # Triggers after network gen
                Input('network-optimization-status', 'children'),  # Triggers after optimization
                Input('sim-status', 'children'),  # Triggers after simulation (right panel)
                Input('init-state-check', 'n_intervals')  # Triggers on page load
            ],
            State('pipeline-state-store', 'data')
        )
        def update_pipeline_state(
            data_summary, heat_summary, heat_sources, filter_status, network_status,
            optimization_status, sim_status, n_intervals, current_state
        ):
            """Check file system and stores to determine step completion."""
            if not current_state:
                current_state = {
                    'area_selection': False,
                    'heat_sources': False,
                    'building_filters': False,
                    'network_generation': False,
                    'graph_optimization': False,
                    'simulation': False
                }
            
            # STEP 1: Area Selection - check if buildings.geojson exists
            buildings_path = Path(self.data_paths.get("buildings_geojson_path", "./data/buildings.geojson"))
            if buildings_path.exists():
                try:
                    # Check if file has content
                    if buildings_path.stat().st_size > 100:  # More than just empty structure
                        current_state['area_selection'] = True
                except Exception as e:
                    logger.debug(f"Error checking buildings file: {e}")
            
            # STEP 2: Heat Sources - check if any sources in store
            if heat_sources and isinstance(heat_sources, list) and len(heat_sources) > 0:
                current_state['heat_sources'] = True
            
            # STEP 3: Building Filters - mark complete after first filter application
            # Check if filter_status has content (indicates filters were applied)
            if filter_status and not (filter_status == "" or filter_status is None):
                current_state['building_filters'] = True
            
            # STEP 4: Network Generation - check if graphml exists
            network_path = Path(self.data_paths.get("network_graphml_path", "./data/heating_network.graphml"))
            if network_path.exists():
                try:
                    if network_path.stat().st_size > 100:
                        current_state['network_generation'] = True
                except Exception as e:
                    logger.debug(f"Error checking network file: {e}")
            
            # STEP 5: Graph Optimization - check if filtered graphml exists
            filtered_path = Path(self.data_paths.get("filtered_network_graphml_path", "./data/filtered_heating_network.graphml"))
            if filtered_path.exists():
                try:
                    if filtered_path.stat().st_size > 100:
                        current_state['graph_optimization'] = True
                except Exception as e:
                    logger.debug(f"Error checking filtered network file: {e}")
            
            # STEP 6: Simulation - check if pandapipes results exist
            results_path = Path(self.data_paths.get("pandapipes_results_path", "./data/pandapipes"))
            if results_path.exists() and results_path.is_dir():
                # Check for any CSV files in the results directory
                csv_files = list(results_path.glob("*.csv"))
                if csv_files:
                    current_state['simulation'] = True
            
            logger.debug(f"Updated pipeline state: {current_state}")
            return current_state
        
        # NEW: Manage section collapse/expand states
        @self.app.callback(
            [
                Output('section-area-selection-header', 'className'),
                Output('section-area-selection-body', 'className'),
                Output('section-heat-sources-header', 'className'),
                Output('section-heat-sources-body', 'className'),
                Output('section-building-filters-header', 'className'),
                Output('section-building-filters-body', 'className'),
                Output('section-network-generation-header', 'className'),
                Output('section-network-generation-body', 'className'),
                Output('section-graph-optimization-header', 'className'),
                Output('section-graph-optimization-body', 'className'),
                Output('workflow-expansion-store', 'data')
            ],
            [
                Input('pipeline-state-store', 'data'),
                Input('section-area-selection-header', 'n_clicks'),
                Input('section-heat-sources-header', 'n_clicks'),
                Input('section-building-filters-header', 'n_clicks'),
                Input('section-network-generation-header', 'n_clicks'),
                Input('section-graph-optimization-header', 'n_clicks')
            ],
            State('workflow-expansion-store', 'data'),
            prevent_initial_call=False
        )
        def manage_section_expansion(
            state, click1, click2, click3, click4, click5, expansion_store
        ):
            """Manage which section is expanded based on workflow state and clicks."""
            from dash import callback_context
            
            if not state:
                # Initial state: only step 1 expanded
                return (
                    'section-header', 'section-body',  # Step 1 expanded
                    'section-header collapsed', 'section-body collapsed',  # Step 2 collapsed
                    'section-header collapsed', 'section-body collapsed',  # Step 3 collapsed
                    'section-header collapsed', 'section-body collapsed',  # Step 4 collapsed
                    'section-header collapsed', 'section-body collapsed',  # Step 5 collapsed
                    {'expanded_section': 'section-area-selection'}
                )
            
            if not expansion_store:
                expansion_store = {'expanded_section': 'section-area-selection'}
            
            # Determine which sections are unlocked
            sections_unlocked = {
                'section-area-selection': True,  # Always unlocked
                'section-heat-sources': state.get('area_selection', False),
                'section-building-filters': state.get('heat_sources', False),
                'section-network-generation': state.get('heat_sources', False),
                'section-graph-optimization': state.get('network_generation', False)
            }
            
            # Check if this was triggered by a header click
            triggered = callback_context.triggered
            if triggered and len(triggered) > 0:
                trigger_id = triggered[0]['prop_id'].split('.')[0]
                
                # If a section header was clicked
                if trigger_id.endswith('-header'):
                    section_id = trigger_id.replace('-header', '')
                    
                    # Only respond to clicks on unlocked sections
                    if sections_unlocked.get(section_id, False):
                        # Toggle: if already expanded, collapse it; otherwise expand it
                        if expansion_store.get('expanded_section') == section_id:
                            expansion_store['expanded_section'] = None
                        else:
                            expansion_store['expanded_section'] = section_id
            
            # Auto-expand next section when step completes
            elif 'pipeline-state-store' in str(triggered[0]['prop_id']):
                # Determine which section should be expanded based on what's NOT yet complete
                # This auto-collapses completed sections and opens the next one
                if not state.get('area_selection', False):
                    # Step 1 not done yet - keep it expanded
                    expansion_store['expanded_section'] = 'section-area-selection'
                elif not state.get('heat_sources', False):
                    # Step 1 done, Step 2 not done - expand Step 2
                    expansion_store['expanded_section'] = 'section-heat-sources'
                elif not state.get('network_generation', False):
                    # Step 2 done, Step 4 not done - skip optional Step 3, expand Step 4
                    expansion_store['expanded_section'] = 'section-network-generation'
                elif not state.get('graph_optimization', False):
                    # Step 4 done, Step 5 not done - expand optional Step 5
                    expansion_store['expanded_section'] = 'section-graph-optimization'
                else:
                    # All steps complete - collapse everything for clean view
                    expansion_store['expanded_section'] = None
            
            # Build class names based on expansion state
            expanded_section = expansion_store.get('expanded_section')
            
            def get_classes(section_id, is_unlocked):
                """Get header and body classes for a section."""
                is_locked = not is_unlocked
                is_expanded = expanded_section == section_id
                
                header_classes = ['section-header']
                body_classes = ['section-body']
                
                if is_locked:
                    header_classes.append('locked')
                
                if not is_expanded:
                    header_classes.append('collapsed')
                    body_classes.append('collapsed')
                
                return ' '.join(header_classes), ' '.join(body_classes)
            
            # Generate classes for all sections
            step1_h, step1_b = get_classes('section-area-selection', sections_unlocked['section-area-selection'])
            step2_h, step2_b = get_classes('section-heat-sources', sections_unlocked['section-heat-sources'])
            step3_h, step3_b = get_classes('section-building-filters', sections_unlocked['section-building-filters'])
            step4_h, step4_b = get_classes('section-network-generation', sections_unlocked['section-network-generation'])
            step5_h, step5_b = get_classes('section-graph-optimization', sections_unlocked['section-graph-optimization'])
            
            return (
                step1_h, step1_b,
                step2_h, step2_b,
                step3_h, step3_b,
                step4_h, step4_b,
                step5_h, step5_b,
                expansion_store
            )
        
        # Update UI lock states for all sections
        @self.app.callback(
            [
                Output('section-heat-sources', 'className'),
                Output('add-heat-source-btn', 'disabled'),
                Output('clear-heat-sources-btn', 'disabled'),
                Output('section-building-filters', 'className'),
                Output('apply-filters-btn', 'disabled'),
                Output('section-network-generation', 'className'),
                Output('generate-network-btn', 'disabled'),
                Output('section-graph-optimization', 'className'),
                Output('optimize-network-btn', 'disabled'),
                Output('section-simulation', 'className'),
                Output('sim-init-btn', 'disabled'),
                Output('sim-run-btn', 'disabled')
            ],
            Input('pipeline-state-store', 'data')
        )
        def update_section_locks(state):
            """Enable/disable sections based on pipeline state."""
            if not state:
                # All locked by default
                return (
                    'control-section locked', True, True,  # Heat Sources
                    'control-section locked', True,        # Filters
                    'control-section locked', True,        # Network
                    'control-section locked', True,        # Optimization
                    'status-panel locked', True, True      # Simulation
                )
            
            # Step 2: Heat Sources (requires Step 1)
            heat_sources_unlocked = state.get('area_selection', False)
            heat_sources_class = 'control-section' if heat_sources_unlocked else 'control-section locked'
            
            # Step 3: Filters (requires Step 2)
            filters_unlocked = state.get('heat_sources', False)
            filters_class = 'control-section' if filters_unlocked else 'control-section locked'
            
            # Step 4: Network Generation (requires Step 2, filters optional)
            # Network can be generated after heat sources, filters not required
            network_unlocked = state.get('heat_sources', False)
            network_class = 'control-section' if network_unlocked else 'control-section locked'
            
            # Step 5: Graph Optimization (requires Step 4)
            optimization_unlocked = state.get('network_generation', False)
            optimization_class = 'control-section' if optimization_unlocked else 'control-section locked'
            
            # Step 6: Simulation (requires Step 4, optimization optional)
            simulation_unlocked = state.get('network_generation', False)
            simulation_class = 'status-panel' if simulation_unlocked else 'status-panel locked'
            
            return (
                heat_sources_class, not heat_sources_unlocked, not heat_sources_unlocked,
                filters_class, not filters_unlocked,
                network_class, not network_unlocked,
                optimization_class, not optimization_unlocked,
                simulation_class, not simulation_unlocked, not simulation_unlocked
            )
        
        # Update step number badges with completion checkmarks
        @self.app.callback(
            [
                Output('step-1-badge', 'children'),
                Output('step-1-badge', 'className'),
                Output('step-2-badge', 'children'),
                Output('step-2-badge', 'className'),
                Output('step-3-badge', 'children'),
                Output('step-3-badge', 'className'),
                Output('step-4-badge', 'children'),
                Output('step-4-badge', 'className'),
                Output('step-5-badge', 'children'),
                Output('step-5-badge', 'className'),
                Output('step-6-badge', 'children'),
                Output('step-6-badge', 'className')
            ],
            Input('pipeline-state-store', 'data')
        )
        def update_step_badges(state):
            """Update step number badges to show checkmarks when complete."""
            if not state:
                return (
                    "1", "step-number",
                    "2", "step-number",
                    "3", "step-number",
                    "4", "step-number",
                    "5", "step-number",
                    "6", "step-number"
                )
            
            # Step 1: Area Selection
            step1_content = "✓" if state.get('area_selection', False) else "1"
            step1_class = "step-number completed" if state.get('area_selection', False) else "step-number"
            
            # Step 2: Heat Sources
            step2_complete = state.get('heat_sources', False)
            step2_content = "✓" if step2_complete else "2"
            step2_class = "step-number completed" if step2_complete else "step-number"
            
            # Step 3: Filters (optional)
            step3_complete = state.get('building_filters', False)
            step3_content = "✓" if step3_complete else "3"
            step3_class = "step-number completed" if step3_complete else "step-number"
            
            # Step 4: Network Generation
            step4_complete = state.get('network_generation', False)
            step4_content = "✓" if step4_complete else "4"
            step4_class = "step-number completed" if step4_complete else "step-number"
            
            # Step 5: Optimization (optional)
            step5_complete = state.get('graph_optimization', False)
            step5_content = "✓" if step5_complete else "5"
            step5_class = "step-number completed" if step5_complete else "step-number"
            
            # Step 6: Simulation
            step6_complete = state.get('simulation', False)
            step6_content = "✓" if step6_complete else "6"
            step6_class = "step-number completed" if step6_complete else "step-number"
            
            return (
                step1_content, step1_class,
                step2_content, step2_class,
                step3_content, step3_class,
                step4_content, step4_class,
                step5_content, step5_class,
                step6_content, step6_class
            )
        
        # RESET ALL - "Draw Analysis Area" button clears pipeline state
        @self.app.callback(
            Output('pipeline-state-store', 'data', allow_duplicate=True),
            Input('start-measurement-btn', 'n_clicks'),
            prevent_initial_call=True
        )
        def reset_pipeline_on_new_area(n_clicks):
            """Reset entire pipeline state when drawing new analysis area."""
            if n_clicks and n_clicks > 0:
                logger.info("Resetting pipeline state - new area selection started")
                return {
                    'area_selection': False,
                    'heat_sources': False,
                    'building_filters': False,
                    'network_generation': False,
                    'graph_optimization': False,
                    'simulation': False
                }
            raise PreventUpdate
