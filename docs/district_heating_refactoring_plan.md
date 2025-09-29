# District Heating Network Model – Implementation Summary

The single-pipe refactoring plan has been fully implemented. This document explains the actual behaviour of `app/pandapipes_builder.py`, how to configure it, and the steps required to reproduce the two-pipe, closed-loop model inside the project container.

## 1. Scope and Supported Inputs

`PandapipesBuilder` consumes a GraphML created by the network generation pipeline. Each node must include `node_type`, `x`, `y`, and optional attributes such as `heat_demand` or `annual_heat_production`. Supported `node_type` values are `street`, `street_connection`, `building`, and `heat_source`. Edges must provide `edge_type` (defaults: `street_segment`, `building_connection`, or `heat_source_connection`) and optionally `length` in metres. If `length` is missing, Euclidean distance between node coordinates is used.

During import the builder prunes connected components that do not contain a `heat_source`. This avoids floating subnetworks that would otherwise fail during hydraulic analysis. Pruning statistics are included in the build summary under `pruned_nodes` and `pruned_edges`.

## 2. Configuration (`app/config.yml`)

The active configuration for the two-pipe model is stored in the `pandapipes` block. Key fields:

- `supply_temperature_C` / `return_temperature_C`: applied as the default fluid temperatures for supply and return junctions.
- `circ_pump_pressure_bar`: discharge pressure for each circulation pump instance.
- `delta_T_K` and `cp_J_per_kgK`: used to convert aggregated building loads into a circulation mass flow according to \(\dot m = \frac{Q}{c_p \Delta T}\).
- `min_mass_flow_kg_per_s`: lower bound used when heat load is low or zero.
- `min_junction_pressure_bar`: initial nominal pressure for all junctions.
- `default_pipe_diameter_m`, `roughness_m`, and `min_pipe_length_m`: defaults for pipe creation.
- `assume_continuous_operation_h_per_year`: annual operating hours used to translate kWh demand into kW.
- `edge_types_as_pipes`: explicit whitelist of edge types that become pipes.
- `output_paths`: destinations for JSON, CSV, and GeoJSON exports.

No obsolete single-pipe settings remain; the builder ignores any undocumented keys.

## 3. Network Construction (`build_from_graphml`)

The `build_from_graphml` method performs the full translation from GraphML to a pandapipes network and writes the resulting model to JSON. The process is deterministic and side-effect free beyond file exports.

1. **Input resolution**
    - Preference order: `./data/filtered_heating_network.graphml`, fallback `./data/heating_network.graphml`, or a user-supplied path.
    - Raises `FileNotFoundError` if no GraphML is found.

2. **Junction creation**
    - For each node with valid coordinates, the builder creates two junctions: `sup_<node_id>` and `ret_<node_id>`.
    - Supply junctions use the configured supply temperature; return junctions use the return temperature.
    - Geodata (`x`, `y`) and a `circuit` tag (`supply` or `return`) are stored when possible.

3. **Pipe duplication**
    - Each edge is turned into two pipes. The supply pipe connects `sup_u → sup_v`; the return pipe connects `ret_v → ret_u` (opposite direction).
    - Diameters, roughness, and minimum length come from configuration. Lengths under the minimum are clamped and reported as `pipes_clamped_to_min_length`.
    - Circuit labels (`supply`, `return`) are propagated to the pipe table when supported by the pandapipes version in use.

4. **Building loads as heat exchangers**
    - Each `building` node becomes a `pandapipes.heat_exchanger` linking the node’s supply and return junctions.
    - Annual heat demand is converted: \(q_\text{ext,W} = \frac{\text{heat
demand}_{\text{kWh}}}{\text{operating hours}} \times 1000\).
    - Positive `qext_w` values represent heat extracted from the loop (cooling the return branch). Non-finite or zero values are skipped.
    - Created exchangers are tagged with `component_role = building_hex` and reported under `building_heat_exchangers`.

5. **Heat sources and circulation pump**
    - Every `heat_source` node must exist in the GraphML when total building load is non-zero; otherwise the build aborts.
    - The total mass flow is calculated from the aggregated building load using the configured \(\Delta T\) and \(c_p\). If the computed value falls below `min_mass_flow_kg_per_s`, the minimum is used instead. Summary keys `plant_pump_mass_flow_kg_per_s` and `plant_pump_mass_flow_source` describe the final value and whether it originated from the load or the minimum clamp.
    - For each heat source node, the builder creates a `pandapipes.circ_pump_const_mass_flow` between the return and supply junctions (`ret → sup`). The pump enforces the per-source mass flow (`total_mass_flow / number_of_sources`) and applies the configured delivery pressure (`circ_pump_pressure_bar`).
    - No additional plant-side heat exchanger is instantiated; thermal input is implicitly represented by the circulation pump and the positive building loads. `plant_heater_created` is therefore always `False` in the build summary.

6. **Exports and summary**
    - The pandapipes network is written to `./data/pandapipes/network.json` (path configurable).
    - The returned dictionary includes counts for junctions and pipes (split by circuit), the aggregate building load (`total_heat_load_W`), pruning statistics, pump metadata, and the output JSON path. This summary is consumed by the Dash callbacks.

## 4. Hydraulic Simulation (`run_pipeflow`)

`run_pipeflow` loads the stored network (or accepts an in-memory network), executes `pp.pipeflow`, and exports results:

- Pipeflow configuration uses the Swamee–Jain friction model with sequential solving. Legacy `mode="all"` values are normalised to `sequential` for compatibility.
- Convergence tolerances and iteration limits honour the `pandapipes.pipeflow` subsection in `config.yml`.
- Junction, pipe, and heat-exchanger tables are exported to CSV. When available, simulated results are joined onto the static component tables (e.g., velocities, temperatures, pressures).
- Pipe results gain helper columns (`from_junction_name`, `to_junction_name`, `circuit`). Heat exchangers gain building IDs and junction temperature/pressure snapshots.
- If junction geodata exist, pipe results are projected to `EPSG:5243` and written to GeoJSON for map display.
- The returned summary reports convergence status, min/max junction pressures, maximum pipe velocity, iteration counts, export paths, and any pipeflow errors.

## 5. Reproducing the Build Inside the Container

1. Ensure the Docker environment is running with hot reload:

    ```bash
    docker compose up
    ```

2. Provide a `filtered_heating_network.graphml` (or `heating_network.graphml`) under `app/data/`.

3. Trigger the build step via the Dash UI or directly from a Python shell inside the container:

    ```python
    from config import Config
    from pandapipes_builder import PandapipesBuilder

    cfg = Config()
    builder = PandapipesBuilder(cfg)
    summary = builder.build_from_graphml()
    print(summary)
    ```

4. Optionally run the hydraulic calculation immediately afterwards:

    ```python
    run_summary = builder.run_pipeflow(json_path=summary["json_path"])
    print(run_summary)
    ```

5. Inspect outputs in `app/data/pandapipes/` (`network.json`, `pipe_results.csv`, `junction_results.csv`, `heat_exchanger_results.csv`, `pipe_results.geojson`). These files feed the Dash callback layer and the map visualisation.

## 6. Operational Notes and Edge Cases

- **Missing heat sources:** if any building has a positive heat demand but no `heat_source` exists in the GraphML component, the build aborts with an explicit error.
- **Zero load networks:** when total building demand is zero, pumps enforce zero mass flow and the system remains idle; summary fields document this via `plant_pump_mass_flow_source = "zero"`.
- **Geodata absence:** lacking `x`/`y` coordinates causes the corresponding nodes to be skipped entirely, reducing junction counts. GeoJSON export is skipped if no geodata are present.
- **Pandapipes availability:** importing `pandapipes` is mandatory. The builder raises immediately if the library is missing, preventing partial outputs.

This document supersedes the earlier refactoring plan and should be used as the definitive reference for developing and troubleshooting the district heating network model.
