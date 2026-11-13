"""Command-line interface entrypoint for lh-pcb-thermal-sim."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

from .auditor import PCBThermalPolicy, audit_pcb_thermal_policy
from .exporters import render_json, render_sarif, render_table
from .fdm_solver import (
    FDMSolverConfig,
    PCBBoardDefinition,
    ThermalComponent,
    render_ascii_thermal_map,
    solve_2d_steady_state,
)
from .stackup_math import (
    CopperLayer,
    DielectricLayer,
    PCBStackup,
    calculate_anisotropic_conductivities,
    calculate_ipc2152_trace_heating,
    calculate_thermal_via_resistance,
)

TOOL_NAME = "lh-pcb-thermal"
TOOL_VERSION = "0.1.0"


def parse_board_json(path: str | Path) -> PCBBoardDefinition:
    """Parse board manifest JSON into PCBBoardDefinition."""
    with open(path, "r", encoding="utf-8") as f:
        data: Dict[str, Any] = json.load(f)

    # Parse stackup
    st_data = data.get("stackup", {})
    cu_layers: List[CopperLayer] = []
    for cl in st_data.get("copper_layers", []):
        if "thickness_m" in cl:
            t_m = float(cl["thickness_m"])
        elif "thickness_oz" in cl:
            t_m = float(cl["thickness_oz"]) * 3.5e-5
        else:
            t_m = 3.5e-5
        cu_layers.append(
            CopperLayer(
                name=cl.get("name", "Cu"),
                thickness_m=t_m,
                coverage_ratio=float(cl.get("coverage_ratio", 1.0)),
            )
        )

    diel_layers: List[DielectricLayer] = []
    for dl in st_data.get("dielectric_layers", []):
        diel_layers.append(
            DielectricLayer(
                name=dl.get("name", "FR4"),
                thickness_m=float(dl.get("thickness_m", 0.0002)),
                k_dielectric=float(dl.get("k_dielectric", 0.30)),
            )
        )

    stackup = PCBStackup(
        name=st_data.get("name", "Custom-Stackup"),
        copper_layers=cu_layers,
        dielectric_layers=diel_layers,
    )

    # Parse components
    comps: List[ThermalComponent] = []
    for c in data.get("components", []):
        comps.append(
            ThermalComponent(
                name=c.get("name", "U1"),
                x_mm=float(c.get("x_mm", 0.0)),
                y_mm=float(c.get("y_mm", 0.0)),
                width_mm=float(c.get("width_mm", 10.0)),
                length_mm=float(c.get("length_mm", 10.0)),
                power_w=float(c.get("power_w", 0.0)),
                r_theta_jb=float(c.get("r_theta_jb", 6.0)),
                num_thermal_vias=int(c.get("num_thermal_vias", 0)),
                via_drill_diameter_mm=float(c.get("via_drill_diameter_mm", 0.3)),
                via_plating_um=float(c.get("via_plating_um", 25.0)),
            )
        )

    return PCBBoardDefinition(
        name=data.get("name", "PCB-Board"),
        length_x_mm=float(data.get("length_x_mm", 100.0)),
        length_y_mm=float(data.get("length_y_mm", 80.0)),
        stackup=stackup,
        components=comps,
        ambient_c=float(data.get("ambient_c", 25.0)),
        h_conv=float(data.get("h_conv", 12.5)),
    )


def cmd_scan(args: argparse.Namespace) -> int:
    """Execute posture audit on a policy manifest."""
    try:
        policy = PCBThermalPolicy.from_file(args.policy_file)
    except Exception as e:
        sys.stderr.write(f"Error loading policy: {e}\n")
        return 2

    report = audit_pcb_thermal_policy(policy)

    fmt = args.format.lower()
    if fmt == "table":
        output = render_table(report)
    elif fmt == "json":
        output = render_json(report)
    elif fmt == "sarif":
        output = render_sarif(report)
    else:
        sys.stderr.write(f"Error: unsupported format {args.format}\n")
        return 2

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output + "\n")
    else:
        print(output)

    if report.failed_count > 0 or report.score < 100:
        return 1
    return 0


def cmd_simulate(args: argparse.Namespace) -> int:
    """Execute 2D steady-state FDM thermal simulation on a board layout."""
    try:
        board = parse_board_json(args.board_file)
    except Exception as e:
        sys.stderr.write(f"Error loading board definition: {e}\n")
        return 2

    config = FDMSolverConfig(
        grid_pitch_mm=args.grid_pitch,
        convergence_tol_c=args.tol,
    )

    result = solve_2d_steady_state(board, config)

    print()
    print("========================================================================================")
    print("  LOGIHERTZ PCB 2D STEADY-STATE THERMAL SIMULATION REPORT")
    print("========================================================================================")
    print(f"  Board:                 {result.board_name} ({board.length_x_mm:.1f} x {board.length_y_mm:.1f} mm)")
    print(f"  Grid Resolution:       {result.grid_nx} x {result.grid_ny} cells (dx={result.dx_mm:.2f}mm, dy={result.dy_mm:.2f}mm)")
    print(f"  Solver Iterations:     {result.iterations} (Converged: {result.converged})")
    print(f"  Ambient Temperature:   {result.ambient_c:.1f}°C")
    print(f"  Board Min / Max / Avg: {result.min_temp_c:.1f}°C / {result.max_temp_c:.1f}°C / {result.avg_temp_c:.1f}°C")
    print(f"  Peak Spatial Gradient: {result.max_gradient_c_per_mm:.2f}°C/mm")
    print(f"  Total Heat Input:      {result.total_input_power_w:.2f} W")
    print(f"  Convective Heat Loss:  {result.total_convective_heat_w:.2f} W")
    print(f"  Energy Balance Error:  {result.energy_balance_error_pct:.3f}%")
    print()

    print("┌────────────────────┬──────────┬─────────────┬─────────────┬──────────────┬───────────┐")
    print("│ Component Name     │ Power(W) │ Board(°C)   │ Junction(°C)│ R_eff(°C/W)  │ Status    │")
    print("├────────────────────┼──────────┼─────────────┼─────────────┼──────────────┼───────────┤")

    hotspot_detected = False
    for name, cr in result.component_results.items():
        status = "NOMINAL"
        if cr.junction_temp_c > 105.0:
            status = "OVERHEAT"
            hotspot_detected = True
        elif cr.junction_temp_c > 90.0:
            status = "WARNING"

        print(
            f"│ {cr.name:<18} │ {cr.power_w:>8.2f} │ {cr.board_temp_c:>11.1f} │ {cr.junction_temp_c:>11.1f} │ {cr.r_theta_eff:>12.2f} │ {status:<9} │"
        )
    print("└────────────────────┴──────────┴─────────────┴─────────────┴──────────────┴───────────┘")
    print()

    if args.heatmap:
        ascii_map = render_ascii_thermal_map(result)
        print(ascii_map)
        print()

    if hotspot_detected or result.max_temp_c > 130.0:
        sys.stderr.write("Warning: Thermal hotspot detected exceeding derated component or board limits.\n")
        return 1

    return 0


def cmd_calc_stackup(args: argparse.Namespace) -> int:
    """Calculate homogenized anisotropic thermal conductivities of the PCB stackup."""
    try:
        board = parse_board_json(args.board_file)
    except Exception as e:
        sys.stderr.write(f"Error loading board definition: {e}\n")
        return 2

    cond = calculate_anisotropic_conductivities(board.stackup)

    print()
    print("========================================================================================")
    print("  LOGIHERTZ PCB ANISOTROPIC STACKUP CONDUCTIVITY REPORT")
    print("========================================================================================")
    print(f"  Stackup Name:                {board.stackup.name}")
    print(f"  Total Thickness:             {cond.total_thickness_m * 1e3:.3f} mm")
    print(f"  In-Plane Conductivity (k_xy): {cond.k_eff_xy:.2f} W/(m·K)")
    print(f"  Through-Plane Cond. (k_z):    {cond.k_eff_z:.3f} W/(m·K)")
    print(f"  Thermal Anisotropy Ratio:    {cond.anisotropy_ratio:.1f}x")
    print()

    # Via analysis for power components
    print("Thermal Via Resistance Estimates:")
    for c in board.components:
        if c.num_thermal_vias > 0:
            r_via = calculate_thermal_via_resistance(
                num_vias=c.num_thermal_vias,
                drill_diameter_mm=c.via_drill_diameter_mm,
                plating_thickness_um=c.via_plating_um,
                board_thickness_m=cond.total_thickness_m,
            )
            print(f"  • {c.name:<18} [{c.num_thermal_vias} vias, {c.via_drill_diameter_mm}mm drill]: R_vias = {r_via:.2f} °C/W")
    print("========================================================================================")
    return 0


def cmd_ipc2152(args: argparse.Namespace) -> int:
    """Calculate IPC-2152 trace temperature rise and Joule heating."""
    try:
        res = calculate_ipc2152_trace_heating(
            current_amps=args.current_amps,
            width_mm=args.width_mm,
            copper_oz=args.copper_oz,
            length_mm=args.length_mm,
            is_internal=args.internal,
            ambient_c=args.ambient_c,
        )
    except Exception as e:
        sys.stderr.write(f"Calculation error: {e}\n")
        return 2

    layer_type = "Internal Layer" if res.is_internal else "External Layer"
    print()
    print("========================================================================================")
    print("  LOGIHERTZ IPC-2152 HIGH-CURRENT TRACE JOULE HEATING REPORT")
    print("========================================================================================")
    print(f"  Current Load:                {res.current_amps:.2f} A")
    print(f"  Trace Width & Weight:        {res.width_mm:.2f} mm ({res.copper_oz:.1f} oz Cu)")
    print(f"  Layer Placement:             {layer_type}")
    print(f"  Cross-Sectional Area:        {res.area_mils2:.1f} sq mils")
    print(f"  Computed Temperature Rise:   {res.temp_rise_c:.2f}°C")
    print(f"  Final Trace Temperature:     {res.trace_temp_c:.2f}°C (at {args.ambient_c:.1f}°C ambient)")
    print(f"  DC Resistance (L={res.length_mm:.0f}mm):     {res.dc_resistance_ohms * 1e3:.3f} mOhm")
    print(f"  Joule Power Loss:            {res.joule_power_w:.3f} W")
    print("========================================================================================")

    if res.temp_rise_c > 20.0:
        sys.stderr.write(f"Warning: Trace temperature rise ({res.temp_rise_c:.1f}°C) exceeds IPC-2152 20°C reliability ceiling.\n")
        return 1

    return 0


def build_parser() -> argparse.ArgumentParser:
    """Build command-line argument parser."""
    parser = argparse.ArgumentParser(
        prog=TOOL_NAME,
        description=f"{TOOL_NAME} {TOOL_VERSION} (Logihertz Multi-Layer PCB 2D Thermal Simulator & Auditor)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("-V", "--version", action="version", version=f"{TOOL_NAME} {TOOL_VERSION}")

    subparsers = parser.add_subparsers(dest="subcommand", help="Subcommand to execute")

    # scan
    p_scan = subparsers.add_parser("scan", help="Audit PCB thermal reliability posture against 10 rules")
    p_scan.add_argument("policy_file", help="Path to policy JSON manifest")
    p_scan.add_argument("--format", choices=["table", "json", "sarif"], default="table", help="Output format")
    p_scan.add_argument("--output", help="Write report to file")

    # simulate
    p_sim = subparsers.add_parser("simulate", help="Solve 2D steady-state PCB temperature field")
    p_sim.add_argument("board_file", help="Path to board definition JSON")
    p_sim.add_argument("--grid-pitch", type=float, default=2.0, help="Grid resolution pitch [mm]")
    p_sim.add_argument("--tol", type=float, default=1e-4, help="Convergence tolerance [°C]")
    p_sim.add_argument("--heatmap", action="store_true", help="Render ASCII thermal heatmap")

    # calc-stackup
    p_st = subparsers.add_parser("calc-stackup", help="Compute anisotropic stackup thermal conductivity")
    p_st.add_argument("board_file", help="Path to board definition JSON")

    # ipc2152
    p_ipc = subparsers.add_parser("ipc2152", help="Compute IPC-2152 trace temperature rise and Joule heating")
    p_ipc.add_argument("--current-amps", type=float, required=True, help="Trace current [A]")
    p_ipc.add_argument("--width-mm", type=float, required=True, help="Trace width [mm]")
    p_ipc.add_argument("--copper-oz", type=float, default=1.0, help="Copper weight [oz]")
    p_ipc.add_argument("--length-mm", type=float, default=50.0, help="Trace length [mm]")
    p_ipc.add_argument("--ambient-c", type=float, default=25.0, help="Ambient temperature [°C]")
    p_ipc.add_argument("--internal", action="store_true", help="Specify if trace is on an internal layer")

    return parser


def main() -> None:
    """Main CLI entrypoint."""
    parser = build_parser()
    if len(sys.argv) < 2:
        parser.print_help()
        sys.exit(2)

    args = parser.parse_args()
    if not args.subcommand:
        parser.print_help()
        sys.exit(2)

    if args.subcommand == "scan":
        code = cmd_scan(args)
    elif args.subcommand == "simulate":
        code = cmd_simulate(args)
    elif args.subcommand == "calc-stackup":
        code = cmd_calc_stackup(args)
    elif args.subcommand == "ipc2152":
        code = cmd_ipc2152(args)
    else:
        parser.print_help()
        code = 2

    sys.exit(code)


if __name__ == "__main__":
    main()
