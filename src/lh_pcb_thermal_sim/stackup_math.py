"""Multi-layer PCB stackup thermal physics and IPC-2152 trace heating math."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List

# Thermal & Physical Constants
K_CU: float = 385.0  # Pure copper thermal conductivity [W/(m·K)]
K_FR4: float = 0.30  # Standard FR-4 dielectric thermal conductivity [W/(m·K)]
CU_1OZ_METERS: float = 3.5e-5  # 1 oz/ft^2 copper thickness = 35 um = 3.5e-5 m
MILS_PER_OZ: float = 1.378  # 1 oz copper thickness in mils (~35 um)
MM_PER_INCH: float = 25.4
RHO_CU_20: float = 1.72e-8  # Copper electrical resistivity at 20°C [Ohm·m]
ALPHA_CU: float = 0.00393  # Copper temperature coefficient of resistance [1/K]


@dataclass
class CopperLayer:
    """Represents a conductive copper plane or signal layer in the PCB stackup."""

    name: str
    thickness_m: float
    coverage_ratio: float = 1.0  # 0.0 (no copper) to 1.0 (solid plane)

    @classmethod
    def from_oz(cls, name: str, thickness_oz: float, coverage_ratio: float = 1.0) -> CopperLayer:
        return cls(name=name, thickness_m=thickness_oz * CU_1OZ_METERS, coverage_ratio=coverage_ratio)


@dataclass
class DielectricLayer:
    """Represents an insulating prepreg or core dielectric layer."""

    name: str
    thickness_m: float
    k_dielectric: float = K_FR4


@dataclass
class PCBStackup:
    """Represents an entire multi-layer PCB stackup."""

    name: str
    copper_layers: List[CopperLayer]
    dielectric_layers: List[DielectricLayer]

    @property
    def total_thickness_m(self) -> float:
        t_cu = sum(c.thickness_m for c in self.copper_layers)
        t_diel = sum(d.thickness_m for d in self.dielectric_layers)
        return t_cu + t_diel


@dataclass
class AnisotropicConductivity:
    """Effective anisotropic thermal conductivities of a homogenized PCB stackup."""

    k_eff_xy: float  # In-plane thermal conductivity [W/(m·K)]
    k_eff_z: float  # Through-plane thermal conductivity [W/(m·K)]
    anisotropy_ratio: float  # k_eff_xy / k_eff_z
    total_thickness_m: float


def calculate_anisotropic_conductivities(stackup: PCBStackup) -> AnisotropicConductivity:
    """Calculate homogenized in-plane (k_xy) and through-plane (k_z) conductivities."""
    t_total = stackup.total_thickness_m
    if t_total <= 0:
        raise ValueError("Total stackup thickness must be positive.")

    # 1. In-Plane (Parallel) Effective Thermal Conductivity:
    # Weighted arithmetic mean of all layer conductivities
    in_plane_sum = 0.0
    for cl in stackup.copper_layers:
        k_cl = cl.coverage_ratio * K_CU + (1.0 - cl.coverage_ratio) * K_FR4
        in_plane_sum += cl.thickness_m * k_cl
    for dl in stackup.dielectric_layers:
        in_plane_sum += dl.thickness_m * dl.k_dielectric

    k_eff_xy = in_plane_sum / t_total

    # 2. Through-Plane (Series) Effective Thermal Conductivity:
    # Harmonic mean of layer thermal resistances
    through_plane_resistance_sum = 0.0
    for cl in stackup.copper_layers:
        k_cl = cl.coverage_ratio * K_CU + (1.0 - cl.coverage_ratio) * K_FR4
        if k_cl <= 0:
            k_cl = K_FR4
        through_plane_resistance_sum += cl.thickness_m / k_cl
    for dl in stackup.dielectric_layers:
        k_dl = dl.k_dielectric if dl.k_dielectric > 0 else K_FR4
        through_plane_resistance_sum += dl.thickness_m / k_dl

    k_eff_z = t_total / through_plane_resistance_sum
    anisotropy_ratio = k_eff_xy / k_eff_z

    return AnisotropicConductivity(
        k_eff_xy=k_eff_xy,
        k_eff_z=k_eff_z,
        anisotropy_ratio=anisotropy_ratio,
        total_thickness_m=t_total,
    )


def calculate_thermal_via_resistance(
    num_vias: int,
    drill_diameter_mm: float,
    plating_thickness_um: float,
    board_thickness_m: float,
) -> float:
    """Calculate equivalent thermal resistance (K/W) of a parallel plated through-hole via array."""
    if num_vias <= 0:
        return float("inf")

    r_drill = (drill_diameter_mm * 1e-3) / 2.0
    t_plate = plating_thickness_um * 1e-6
    if t_plate >= r_drill:
        # Solid copper via
        a_barrel = math.pi * (r_drill**2)
    else:
        r_inner = r_drill - t_plate
        a_barrel = math.pi * (r_drill**2 - r_inner**2)

    if a_barrel <= 0:
        return float("inf")

    # Thermal resistance of N parallel thermal via cylinders:
    # R_theta = L / (N * k_Cu * A_barrel)
    r_theta = board_thickness_m / (num_vias * K_CU * a_barrel)
    return r_theta


@dataclass
class TraceHeatingResult:
    """Results of IPC-2152 trace temperature rise and Joule heating calculation."""

    current_amps: float
    width_mm: float
    copper_oz: float
    length_mm: float
    is_internal: bool
    area_mils2: float
    temp_rise_c: float
    trace_temp_c: float
    dc_resistance_ohms: float
    joule_power_w: float


def calculate_ipc2152_trace_heating(
    current_amps: float,
    width_mm: float,
    copper_oz: float = 1.0,
    length_mm: float = 50.0,
    is_internal: bool = False,
    ambient_c: float = 25.0,
) -> TraceHeatingResult:
    """Calculate IPC-2152 temperature rise, resistance, and Joule heating for a PCB trace."""
    if current_amps < 0:
        raise ValueError("Current cannot be negative.")
    if width_mm <= 0:
        raise ValueError("Trace width must be positive.")
    if copper_oz <= 0:
        raise ValueError("Copper weight must be positive.")

    # Convert dimensions to mils
    width_mils = width_mm / 0.0254
    thick_mils = copper_oz * MILS_PER_OZ
    area_mils2 = width_mils * thick_mils

    # IPC-2152 empirical formula:
    # I = k * (Delta_T)^0.44 * (A)^0.725
    # Delta_T = (I / (k * A^0.725))^(1 / 0.44)
    # k = 0.048 for external layers, k = 0.024 for internal layers
    k = 0.024 if is_internal else 0.048

    if current_amps == 0:
        temp_rise_c = 0.0
    else:
        temp_rise_c = (current_amps / (k * (area_mils2**0.725))) ** (1.0 / 0.44)

    trace_temp_c = ambient_c + temp_rise_c

    # DC resistance calculation: R(T) = rho_20 * (L / A) * (1 + alpha * (T - 20))
    # Area in m^2
    width_m = width_mm * 1e-3
    thick_m = copper_oz * CU_1OZ_METERS
    area_m2 = width_m * thick_m
    length_m = length_mm * 1e-3

    temp_factor = 1.0 + ALPHA_CU * (trace_temp_c - 20.0)
    r_dc = (RHO_CU_20 * length_m / area_m2) * temp_factor
    joule_power_w = (current_amps**2) * r_dc

    return TraceHeatingResult(
        current_amps=current_amps,
        width_mm=width_mm,
        copper_oz=copper_oz,
        length_mm=length_mm,
        is_internal=is_internal,
        area_mils2=area_mils2,
        temp_rise_c=temp_rise_c,
        trace_temp_c=trace_temp_c,
        dc_resistance_ohms=r_dc,
        joule_power_w=joule_power_w,
    )
