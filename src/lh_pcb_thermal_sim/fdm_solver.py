"""2D Steady-state Finite-Difference Method (FDM) thermal solver for multi-layer PCBs."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Tuple

from .stackup_math import (
    PCBStackup,
    calculate_anisotropic_conductivities,
    calculate_thermal_via_resistance,
)


@dataclass
class ThermalComponent:
    """Represents a heat-dissipating component mounted on the PCB."""

    name: str
    x_mm: float  # Center X position [mm]
    y_mm: float  # Center Y position [mm]
    width_mm: float  # X dimension [mm]
    length_mm: float  # Y dimension [mm]
    power_w: float  # Dissipated power [Watts]
    r_theta_jb: float = 6.0  # Junction-to-board thermal resistance [°C/W]
    num_thermal_vias: int = 0
    via_drill_diameter_mm: float = 0.3
    via_plating_um: float = 25.0


@dataclass
class PCBBoardDefinition:
    """Defines the geometry, stackup, and boundary conditions of a PCB board."""

    name: str
    length_x_mm: float  # Board X dimension [mm]
    length_y_mm: float  # Board Y dimension [mm]
    stackup: PCBStackup
    components: List[ThermalComponent] = field(default_factory=list)
    ambient_c: float = 25.0  # Ambient air temperature [°C]
    h_conv: float = 12.5  # Natural convection heat transfer coefficient [W/(m^2·K)]


@dataclass
class FDMSolverConfig:
    """Configuration options for the 2D FDM SOR solver."""

    grid_pitch_mm: float = 2.0  # Target grid spacing [mm]
    relaxation_omega: float = 1.30  # Successive Over-Relaxation factor (1.0 to 1.90)
    convergence_tol_c: float = 1e-4  # Maximum temperature change between iterations [°C]
    max_iterations: int = 5000


@dataclass
class ComponentThermalResult:
    """Computed thermal metrics for an individual component."""

    name: str
    power_w: float
    board_temp_c: float
    junction_temp_c: float
    r_theta_eff: float


@dataclass
class SimulationResult:
    """Aggregated thermal simulation results."""

    board_name: str
    grid_nx: int
    grid_ny: int
    dx_mm: float
    dy_mm: float
    iterations: int
    converged: bool
    ambient_c: float
    min_temp_c: float
    max_temp_c: float
    avg_temp_c: float
    max_gradient_c_per_mm: float
    total_input_power_w: float
    total_convective_heat_w: float
    energy_balance_error_pct: float
    temperature_grid: List[List[float]]  # 2D grid [ny][nx]
    component_results: Dict[str, ComponentThermalResult]


def solve_2d_steady_state(
    board: PCBBoardDefinition,
    config: FDMSolverConfig | None = None,
) -> SimulationResult:
    """Solve the 2D steady-state conduction-convection heat equation using FDM SOR."""
    if config is None:
        config = FDMSolverConfig()

    lx_m = board.length_x_mm * 1e-3
    ly_m = board.length_y_mm * 1e-3

    # Compute grid dimensions
    nx = max(4, int(round(board.length_x_mm / config.grid_pitch_mm)))
    ny = max(4, int(round(board.length_y_mm / config.grid_pitch_mm)))
    dx_m = lx_m / nx
    dy_m = ly_m / ny
    dx_mm = board.length_x_mm / nx
    dy_mm = board.length_y_mm / ny

    # Compute homogenized stackup conductivities
    cond = calculate_anisotropic_conductivities(board.stackup)
    k_xy = cond.k_eff_xy
    tz = cond.total_thickness_m

    # Cell-to-cell thermal conductances:
    # Gx = k_xy * (tz * dy) / dx
    # Gy = k_xy * (tz * dx) / dy
    # Convective conductance: top + bottom surface = 2 * h * (dx * dy)
    gx = k_xy * tz * dy_m / dx_m
    gy = k_xy * tz * dx_m / dy_m
    g_conv = 2.0 * board.h_conv * dx_m * dy_m

    # Initialize heat source distribution array P[j][i]
    p_grid = [[0.0 for _ in range(nx)] for _ in range(ny)]
    total_input_power = sum(c.power_w for c in board.components)

    # Distribute component power onto grid cells
    for c in board.components:
        if c.power_w <= 0:
            continue
        # Bounding box of component in mm
        x_min = c.x_mm - c.width_mm / 2.0
        x_max = c.x_mm + c.width_mm / 2.0
        y_min = c.y_mm - c.length_mm / 2.0
        y_max = c.y_mm + c.length_mm / 2.0

        # Find overlapping cell indices
        overlapping_cells: List[Tuple[int, int]] = []
        for j in range(ny):
            cy = (j + 0.5) * dy_mm
            for i in range(nx):
                cx = (i + 0.5) * dx_mm
                if x_min <= cx <= x_max and y_min <= cy <= y_max:
                    overlapping_cells.append((i, j))

        if not overlapping_cells:
            # Fallback to nearest cell
            ci = min(nx - 1, max(0, int(c.x_mm / dx_mm)))
            cj = min(ny - 1, max(0, int(c.y_mm / dy_mm)))
            overlapping_cells.append((ci, cj))

        power_per_cell = c.power_w / len(overlapping_cells)
        for ci, cj in overlapping_cells:
            p_grid[cj][ci] += power_per_cell

    # Initialize temperature field to ambient
    t_grid = [[board.ambient_c for _ in range(nx)] for _ in range(ny)]
    omega = config.relaxation_omega
    converged = False
    iterations = 0

    # Successive Over-Relaxation (SOR) iterative solver
    for it in range(1, config.max_iterations + 1):
        max_delta = 0.0
        for j in range(ny):
            for i in range(nx):
                sum_g_neighbors = 0.0
                sum_g_t_neighbors = 0.0

                # Left neighbor (i - 1)
                if i > 0:
                    sum_g_neighbors += gx
                    sum_g_t_neighbors += gx * t_grid[j][i - 1]
                # Right neighbor (i + 1)
                if i < nx - 1:
                    sum_g_neighbors += gx
                    sum_g_t_neighbors += gx * t_grid[j][i + 1]
                # Bottom neighbor (j - 1)
                if j > 0:
                    sum_g_neighbors += gy
                    sum_g_t_neighbors += gy * t_grid[j - 1][i]
                # Top neighbor (j + 1)
                if j < ny - 1:
                    sum_g_neighbors += gy
                    sum_g_t_neighbors += gy * t_grid[j + 1][i]

                # Gauss-Seidel target
                denom = sum_g_neighbors + g_conv
                t_gs = (sum_g_t_neighbors + g_conv * board.ambient_c + p_grid[j][i]) / denom

                # Apply SOR
                t_new = (1.0 - omega) * t_grid[j][i] + omega * t_gs
                delta = abs(t_new - t_grid[j][i])
                if delta > max_delta:
                    max_delta = delta
                t_grid[j][i] = t_new

        iterations = it
        if max_delta < config.convergence_tol_c:
            converged = True
            break

    # Temperature statistics
    all_temps = [temp for row in t_grid for temp in row]
    min_temp = min(all_temps)
    max_temp = max(all_temps)
    avg_temp = sum(all_temps) / len(all_temps)

    # Energy conservation verification:
    # Q_conv = sum(g_conv * (T[j][i] - T_amb))
    total_convective_heat = sum(g_conv * (temp - board.ambient_c) for temp in all_temps)
    if total_input_power > 0:
        energy_error_pct = abs(total_input_power - total_convective_heat) / total_input_power * 100.0
    else:
        energy_error_pct = 0.0

    # Max spatial gradient calculation [°C/mm]
    max_gradient = 0.0
    for j in range(ny):
        for i in range(nx):
            grad_x = (t_grid[j][i + 1] - t_grid[j][i]) / dx_mm if i < nx - 1 else 0.0
            grad_y = (t_grid[j + 1][i] - t_grid[j][i]) / dy_mm if j < ny - 1 else 0.0
            grad_mag = math.sqrt(grad_x**2 + grad_y**2)
            if grad_mag > max_gradient:
                max_gradient = grad_mag

    # Component junction temperature calculation
    comp_results: Dict[str, ComponentThermalResult] = {}
    for c in board.components:
        ci = min(nx - 1, max(0, int(c.x_mm / dx_mm)))
        cj = min(ny - 1, max(0, int(c.y_mm / dy_mm)))
        t_board_local = t_grid[cj][ci]

        # Effective thermal resistance including thermal vias if present
        r_eff = c.r_theta_jb
        if c.num_thermal_vias > 0:
            r_via = calculate_thermal_via_resistance(
                num_vias=c.num_thermal_vias,
                drill_diameter_mm=c.via_drill_diameter_mm,
                plating_thickness_um=c.via_plating_um,
                board_thickness_m=tz,
            )
            # Parallel resistance path
            if r_via > 0 and not math.isinf(r_via):
                r_eff = (c.r_theta_jb * r_via) / (c.r_theta_jb + r_via)

        t_junction = t_board_local + c.power_w * r_eff
        comp_results[c.name] = ComponentThermalResult(
            name=c.name,
            power_w=c.power_w,
            board_temp_c=t_board_local,
            junction_temp_c=t_junction,
            r_theta_eff=r_eff,
        )

    return SimulationResult(
        board_name=board.name,
        grid_nx=nx,
        grid_ny=ny,
        dx_mm=dx_mm,
        dy_mm=dy_mm,
        iterations=iterations,
        converged=converged,
        ambient_c=board.ambient_c,
        min_temp_c=min_temp,
        max_temp_c=max_temp,
        avg_temp_c=avg_temp,
        max_gradient_c_per_mm=max_gradient,
        total_input_power_w=total_input_power,
        total_convective_heat_w=total_convective_heat,
        energy_balance_error_pct=energy_error_pct,
        temperature_grid=t_grid,
        component_results=comp_results,
    )


def render_ascii_thermal_map(
    result: SimulationResult,
    chars: str = " .:*#@",
) -> str:
    """Render a 2D ASCII thermal map of the PCB temperature field."""
    t_min = result.min_temp_c
    t_max = result.max_temp_c
    span = t_max - t_min if t_max > t_min else 1.0
    num_chars = len(chars)

    lines: List[str] = []
    lines.append(f"--- 2D Thermal Field Map [{result.board_name}] ({result.grid_nx}x{result.grid_ny}) ---")
    lines.append(f"Legend: '{chars[0]}' <= {t_min:.1f}°C  ...  '{chars[-1]}' >= {t_max:.1f}°C")
    lines.append("+" + "-" * result.grid_nx + "+")

    # Render top-down (ny-1 down to 0)
    for j in range(result.grid_ny - 1, -1, -1):
        row_str = ""
        for i in range(result.grid_nx):
            temp = result.temperature_grid[j][i]
            ratio = (temp - t_min) / span
            idx = min(num_chars - 1, max(0, int(ratio * (num_chars - 1))))
            row_str += chars[idx]
        lines.append(f"|{row_str}|")

    lines.append("+" + "-" * result.grid_nx + "+")
    return "\n".join(lines)
