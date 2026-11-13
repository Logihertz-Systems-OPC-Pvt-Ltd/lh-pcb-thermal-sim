"""Logihertz PCB Thermal Simulator (lh-pcb-thermal-sim).

Multi-Layer PCB 2D Finite-Difference Thermal Simulator, Anisotropic Stackup Conductivity
Calculator, IPC-2152 Trace Heating Engine, and 10-Rule Hardware Thermal Posture Auditor.
"""

__version__ = "0.1.0"
__author__ = "Sameer Tawade"
__license__ = "Apache-2.0"

from .stackup_math import (
    CopperLayer,
    DielectricLayer,
    PCBStackup,
    calculate_anisotropic_conductivities,
    calculate_thermal_via_resistance,
    calculate_ipc2152_trace_heating,
)
from .fdm_solver import (
    ThermalComponent,
    PCBBoardDefinition,
    FDMSolverConfig,
    SimulationResult,
    solve_2d_steady_state,
    render_ascii_thermal_map,
)
from .auditor import (
    PCBThermalPolicy,
    PostureFinding,
    PostureReport,
    audit_pcb_thermal_policy,
)

__all__ = [
    "__version__",
    "CopperLayer",
    "DielectricLayer",
    "PCBStackup",
    "calculate_anisotropic_conductivities",
    "calculate_thermal_via_resistance",
    "calculate_ipc2152_trace_heating",
    "ThermalComponent",
    "PCBBoardDefinition",
    "FDMSolverConfig",
    "SimulationResult",
    "solve_2d_steady_state",
    "render_ascii_thermal_map",
    "PCBThermalPolicy",
    "PostureFinding",
    "PostureReport",
    "audit_pcb_thermal_policy",
]
