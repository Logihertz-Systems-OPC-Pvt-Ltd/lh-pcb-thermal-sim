# lh-pcb-thermal-sim

[![CI](https://github.com/Logihertz-Systems-OPC-Pvt-Ltd/lh-pcb-thermal-sim/actions/workflows/ci.yml/badge.svg)](https://github.com/Logihertz-Systems-OPC-Pvt-Ltd/lh-pcb-thermal-sim/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![Python Version](https://img.shields.io/badge/Python-3.11%20%7C%203.12%20%7C%203.13-blue.svg)](https://www.python.org/)
[![Standard](https://img.shields.io/badge/Standard-IPC--2152-orange.svg)](https://www.ipc.org/)
[![Dependencies](https://img.shields.io/badge/Dependencies-Zero%20(std%20only)-brightgreen.svg)](#dependencies)

**Production-grade, zero-dependency Python 3.11+ Multi-Layer PCB 2D Finite-Difference Thermal Simulator, Anisotropic Copper/FR-4 Stackup Conductivity Calculator, IPC-2152 Trace Heating Engine, and 10-Rule Hardware Thermal Reliability Posture Auditor.**

`lh-pcb-thermal-sim` (`bin/lh-pcb-thermal`) is an enterprise-grade electronic design automation (EDA) thermal simulator and hardware safety auditor engineered for high-power embedded computing (NVIDIA Jetson, NXP i.MX, AMD FPGA carrier boards), robotics swarms, motor drivers, and mission-critical aerospace PCB layouts. Built strictly with the Python standard library, it delivers cycle-accurate 2D finite-difference heat diffusion modeling, anisotropic copper/FR-4 conductivity homogenization, thermal via barrel resistance calculation, IPC-2152 high-current trace temperature analysis, and automated 10-rule hardware reliability posture auditing.

---

## Key Capabilities

- **2D Steady-State Finite-Difference SOR Heat Solver**: Discretizes the 2D steady-state heat conduction-convection partial differential equation over an $N_x \times N_y$ board mesh, applying Successive Over-Relaxation (SOR) with configurable relaxation factor $\omega \in [1.0, 1.90]$ and strict convergence tolerances ($\epsilon \le 10^{-4}\ ^\circ\text{C}$).
- **Global Energy Balance Verification**: Proves physical conservation of energy by strictly comparing total component input power $P_{\text{total}} = \sum P_c$ against total integrated surface convective heat dissipation $Q_{\text{out}} = \sum 2 h_{\text{conv}} \Delta x \Delta y (T_{i,j} - T_{\text{amb}})$, guaranteeing relative error $< 0.5\%$.
- **Anisotropic Stackup Homogenization ($k_{\text{eff}, xy}$ vs $k_{\text{eff}, z}$)**: Models multi-layer copper planes (with fractional coverage $\phi_l$) and FR-4 dielectric layers ($k_{\text{FR4}} = 0.30\text{ W/(m}\cdot\text{K)}$) to compute parallel in-plane ($k_{xy} \approx 25\text{--}50\text{ W/(m}\cdot\text{K)}$) and series through-plane ($k_z \approx 0.35\text{ W/(m}\cdot\text{K)}$) effective conductivities, capturing thermal anisotropy ratios exceeding $100\times$.
- **PTH Thermal Via Array Resistance ($R_{\theta, \text{vias}}$)**: Computes cylindrical copper barrel cross-sectional areas and parallel thermal resistances for plated through-hole via arrays under high-power QFN/BGA thermal pads.
- **IPC-2152 High-Current Trace Heating**: Evaluates high-current power distribution traces using official IPC-2152 empirical formulas, temperature-compensated copper resistivity ($\alpha_{\text{Cu}} = 0.00393\ \text{K}^{-1}$), and internal vs. external layer convective derating.
- **Silicon Junction Temperature ($T_J$) & Spatial Gradient ($|\nabla T|_{\max}$)**: Computes peak silicon junction temperatures with junction-to-board ($R_{\theta JB}$) and thermal via modeling, and maps maximum spatial thermal gradients in $^\circ\text{C/mm}$ to defend against solder-joint shear fatigue.
- **2D ASCII/ANSI Thermal Field Heatmaps**: Renders full-resolution terminal heatmaps (`[ . : * # @ ]`) displaying temperature contours, hotspot plumes, and component locations.
- **10-Rule Hardware Thermal Reliability Posture Auditor**: Audits hardware design rules (`LH-PCB-001` through `LH-PCB-010`), computing a standardized score out of 100 with ANSI Box Table, Canonical JSON, and OASIS SARIF v2.1.0 exports.
- **100% Zero External Dependencies**: Pure Python 3.11+ Standard Library (`math`, `json`, `argparse`, `pathlib`, `dataclasses`, `typing`). Zero external runtime libraries.

---

## Architectural Block Diagram

```
+----------------------------------------------------------------------------------------------------+
|                                    lh-pcb-thermal Simulator                                        |
+----------------------------------------------------------------------------------------------------+
                                                  |
  +-----------------------------------------------+-----------------------------------------------+
  |                               |                               |                               |
  v                               v                               v                               v
[Stackup Conductivity]    [2D FDM SOR Solver]           [IPC-2152 Trace Engine]         [Thermal Posture Auditor]
  * In-Plane k_eff,xy       * 2D Conduction-Convection    * Cross-Sectional Area (mils2)  * 10 Reliability Rules
  * Through-Plane k_eff,z   * Energy Balance (<0.5%)      * Delta T Rise (C)              * Junction Temp & Tg Safety
  * Anisotropy Ratio        * Component Junction Tj       * Temp-Compensated R_DC         * Thermal Via Density
  * Thermal Via R_theta     * Spatial Gradient |grad T|   * Joule Loss (I^2 * R)          * Table/JSON/SARIF Export
```

---

## Mathematical Formulations

### 1. 2D Steady-State Heat Conduction-Convection PDE Discretization

The steady-state temperature field $T(x, y)$ of a thin PCB with thickness $t_z$, in-plane thermal conductivity $k_{\text{eff}, xy}$, top/bottom surface natural convection $h_{\text{conv}}$, ambient temperature $T_{\text{amb}}$, and areal heat generation $q''(x, y)$ satisfies:

$$k_{\text{eff}, xy} t_z \left(\frac{\partial^2 T}{\partial x^2} + \frac{\partial^2 T}{\partial y^2}\right) - 2 h_{\text{conv}} \left(T - T_{\text{amb}}\right) + q''(x, y) = 0$$

Discretizing on a uniform mesh with cell size $\Delta x \times \Delta y$:

- In-plane conductances: $G_x = \frac{k_{\text{eff}, xy} t_z \Delta y}{\Delta x}$, $G_y = \frac{k_{\text{eff}, xy} t_z \Delta x}{\Delta y}$
- Surface convection conductance: $G_{\text{conv}} = 2 h_{\text{conv}} \Delta x \Delta y$
- Cell $(i, j)$ heat generation: $P_{i,j} = q''_{i,j} \Delta x \Delta y$

The discrete Gauss-Seidel update with adiabatic board edges is:

$$T_{i,j}^{\text{GS}} = \frac{\sum_{m \in \text{neighbors}} G_m T_m + G_{\text{conv}} T_{\text{amb}} + P_{i,j}}{\sum_{m \in \text{neighbors}} G_m + G_{\text{conv}}}$$

Successive Over-Relaxation (SOR) accelerates convergence:

$$T_{i,j}^{(k+1)} = (1 - \omega) T_{i,j}^{(k)} + \omega T_{i,j}^{\text{GS}}, \quad \omega \in [1.0, 1.90]$$

Iterating until $\max_{i,j} \left|T_{i,j}^{(k+1)} - T_{i,j}^{(k)}\right| < \epsilon_{\text{tol}}$.

### 2. Anisotropic Multi-Layer Effective Thermal Conductivities

For copper thermal conductivity $k_{\text{Cu}} = 385.0\text{ W/(m}\cdot\text{K)}$ and FR-4 dielectric conductivity $k_{\text{FR4}} = 0.30\text{ W/(m}\cdot\text{K)}$, copper layer thicknesses $t_{\text{Cu}, l}$ with coverage ratios $\phi_l$, dielectric thicknesses $t_{\text{diel}, m}$, and total board thickness $t_{\text{total}} = \sum t_{\text{Cu}, l} + \sum t_{\text{diel}, m}$:

- **In-Plane (Parallel) Effective Thermal Conductivity**:
  $$k_{\text{eff}, xy} = \frac{1}{t_{\text{total}}} \left(\sum_l t_{\text{Cu}, l} \left(\phi_l k_{\text{Cu}} + (1 - \phi_l) k_{\text{FR4}}\right) + \sum_m t_{\text{diel}, m} k_{\text{FR4}}\right)$$
- **Through-Plane (Series) Effective Thermal Conductivity**:
  $$k_{\text{eff}, z} = \frac{t_{\text{total}}}{\sum_l \frac{t_{\text{Cu}, l}}{\phi_l k_{\text{Cu}} + (1 - \phi_l) k_{\text{FR4}}} + \sum_m \frac{t_{\text{diel}, m}}{k_{\text{FR4}}}}$$

### 3. Plated Through-Hole (PTH) Thermal Via Array Resistance

For $N_{\text{vias}}$ cylindrical thermal vias with drill radius $r_{\text{drill}}$ and plating thickness $t_{\text{plate}}$:

$$A_{\text{barrel}} = \pi \left(r_{\text{drill}}^2 - (r_{\text{drill}} - t_{\text{plate}})^2\right), \qquad R_{\theta, \text{vias}} = \frac{t_{\text{total}}}{N_{\text{vias}} \cdot k_{\text{Cu}} \cdot A_{\text{barrel}}} \quad (\text{K/W})$$

### 4. IPC-2152 High-Current Trace Temperature Rise & Joule Heating

Given trace width $W_{\text{mm}}$, copper weight $W_{\text{oz}}$, length $L_{\text{mm}}$, current $I_{\text{amps}}$, and area in square mils $A_{\text{mils}^2}$:

$$\Delta T_{\text{trace}} = \left(\frac{I_{\text{amps}}}{k \cdot A_{\text{mils}^2}^{0.725}}\right)^{\frac{1}{0.44}} \quad (^\circ\text{C})$$

where $k = 0.048$ for external layers and $k = 0.024$ for internal layers. Temperature-compensated DC resistance:

$$R_{\text{DC}}(T) = \frac{\rho_{\text{Cu}, 20} \cdot L}{A_{\text{m}^2}} \left(1 + \alpha_{\text{Cu}} (T - 20.0)\right), \qquad P_{\text{Joule}} = I_{\text{amps}}^2 \cdot R_{\text{DC}}(T)$$

---

## 10-Rule Hardware Thermal Reliability Posture Audit Matrix

| Rule ID | Severity | Weight | CWE | Title | Condition Triggered | Remediation |
|:---|:---:|:---:|:---:|:---|:---|:---|
| `LH-PCB-001` | CRITICAL | 25 | CWE-682 | Component Junction Temperature Reliability & Derating Margin | `max_junction_temp_c > 105.0` or `tj_derating_margin_c < 15.0` | Reduce component power dissipation, enlarge thermal copper pours, or add active cooling to maintain $T_J \le 105^\circ\text{C}$ and derating margin $\ge 15^\circ\text{C}$. |
| `LH-PCB-002` | CRITICAL | 25 | CWE-400 | PCB FR-4 Glass Transition (Tg) Safety Boundary & Delamination Guard | `max_board_temp_c > (fr4_tg_temp_c - 20.0)` or `fr4_tg_temp_c < 150.0` | Select High-Tg laminate ($T_g \ge 170^\circ\text{C}$) and keep peak laminate temperature at least $20^\circ\text{C}$ below $T_g$. |
| `LH-PCB-003` | CRITICAL | 25 | CWE-754 | Hardware Over-Temperature Protection (OTP) Thermal Cutoff Safeguard | `otp_hardware_cutoff_enabled == false` or `otp_cutoff_temp_c > 115.0` | Implement hardware NTC/PMIC thermal shutdown circuit with cutoff trip point $\le 115^\circ\text{C}$. |
| `LH-PCB-004` | HIGH | 10 | CWE-682 | Thermal Via Array Density & Plating Barrel Thickness Under Power Pads | `thermal_via_count_per_watt < 4` or `via_plating_thickness_um < 20.0` | Stitch at least 4 thermal vias per Watt under exposed thermal pads with plating thickness $\ge 20\ \mu\text{m}$. |
| `LH-PCB-005` | HIGH | 10 | CWE-682 | IPC-2152 High-Current Power Trace Temperature Rise & Copper Weight | `max_trace_temp_rise_c > 20.0` or `power_layer_copper_oz < 1.0` | Widen high-current power traces or increase copper weight to $\ge 2\text{ oz}$ to maintain IPC-2152 temperature rise $\le 20^\circ\text{C}$. |
| `LH-PCB-006` | HIGH | 10 | CWE-662 | In-Plane Spatial Thermal Gradient & Thermo-Mechanical Fatigue Defense | `max_thermal_gradient_c_per_mm > 3.5` | Distribute heat spreaders and increase internal plane copper coverage to limit thermal gradient $\le 3.5^\circ\text{C/mm}$. |
| `LH-PCB-007` | HIGH | 10 | CWE-20 | High-Power Component Placement Keepout & Sensitive Analog Thermal Isolation | `min_power_ic_spacing_mm < 5.0` or `precision_analog_thermal_isolation == false` | Maintain $\ge 5\text{ mm}$ separation between high-power ICs and thermally isolate precision analog/TCXO circuitry. |
| `LH-PCB-008` | MEDIUM | 4 | CWE-682 | 2D FDM Thermal Solver Convergence Tolerance & Grid Resolution | `fdm_convergence_tol_c > 0.01` or `grid_pitch_mm > 2.5` | Set FDM convergence tolerance $\le 0.01^\circ\text{C}$ and spatial grid pitch $\le 2.5\text{ mm}$. |
| `LH-PCB-009` | MEDIUM | 4 | CWE-693 | Thermal Interface Material (TIM) Thermal Resistance & Ambient Validation | `tim_thermal_resistance_c_per_w > 0.5` or `worst_case_ambient_verified == false` | Use high-performance TIM with resistance $\le 0.5^\circ\text{C/W}$ and verify operation against worst-case maximum ambient. |
| `LH-PCB-010` | LOW | 1 | CWE-778 | Empirical Infrared (IR) Thermography Baseline & Runtime PMIC Telemetry | `ir_thermography_verified == false` or `pmic_temp_telemetry_logged == false` | Validate thermal model with empirical IR thermography and log runtime PMIC/SoC temperature telemetry. |

The posture score is computed monotonically:

$$S_{\text{posture}} = \max\left(0, 100 - \sum_{\text{findings}} W_i\right)$$

- $S_{\text{posture}} \ge 90$: **HARDENED** (Aerospace & Industrial High-Reliability Thermal Margins).
- $70 \le S_{\text{posture}} < 90$: **ADEQUATE** (Minor Thermal Derating or Keepout Risks Present).
- $50 \le S_{\text{posture}} < 70$: **VULNERABLE** (Elevated Hotspot or Thermal Gradient Failure Risk).
- $S_{\text{posture}} < 50$: **CRITICAL** (Severe Thermal Runaway or Delamination Vulnerability).

---

## Installation & Quick Start

### Prerequisites

- Python 3.11, 3.12, or 3.13.
- Linux, macOS, or Windows.

### Build from Source

```bash
# Clone the repository
git clone https://github.com/Logihertz-Systems-OPC-Pvt-Ltd/lh-pcb-thermal-sim.git
cd lh-pcb-thermal-sim

# Verify test suite
PYTHONPATH=src python3 -m unittest discover -s tests -v

# Run executable directly
./bin/lh-pcb-thermal --version
```

---

## CLI Command Reference

### 1. Hardware Thermal Posture Audit (`scan`)

Audits a PCB thermal reliability design policy manifest:

```bash
# ANSI Terminal Box Table format (default)
./bin/lh-pcb-thermal scan fixtures/hardened_pcb_policy.json --format table

# Machine-readable Canonical JSON format
./bin/lh-pcb-thermal scan fixtures/hardened_pcb_policy.json --format json

# OASIS SARIF v2.1.0 format for CI/CD security integration
./bin/lh-pcb-thermal scan fixtures/vulnerable_pcb_policy.json --format sarif --output audit.sarif
```

### 2. 2D Steady-State Thermal Simulation (`simulate`)

Simulates board temperature field and prints component junction temperatures:

```bash
# Basic simulation report:
./bin/lh-pcb-thermal simulate fixtures/sample_jetson_carrier_board.json

# Simulation with 2D ASCII heatmap rendering:
./bin/lh-pcb-thermal simulate fixtures/sample_jetson_carrier_board.json --heatmap
```

### 3. Anisotropic Stackup Thermal Conductivity (`calc-stackup`)

Calculates homogenized in-plane ($k_{xy}$) and through-plane ($k_z$) conductivity:

```bash
./bin/lh-pcb-thermal calc-stackup fixtures/sample_jetson_carrier_board.json
```

### 4. IPC-2152 High-Current Trace Joule Heating (`ipc2152`)

Computes temperature rise and power loss for high-current power distribution traces:

```bash
# External 4mm trace carrying 12A on 2 oz copper:
./bin/lh-pcb-thermal ipc2152 --current-amps 12.0 --width-mm 4.0 --copper-oz 2.0

# Internal power plane neck trace:
./bin/lh-pcb-thermal ipc2152 --current-amps 8.0 --width-mm 2.5 --copper-oz 1.0 --internal
```

---

## Policy Configuration Format

Receiver policies are written in standard JSON:

```json
{
  "policy_id": "HARDENED-AERO-THERMAL-01",
  "board_name": "Jetson-Robotics-Carrier-V3",
  "max_junction_temp_c": 82.5,
  "tj_derating_margin_c": 22.5,
  "max_board_temp_c": 74.0,
  "fr4_tg_temp_c": 170.0,
  "otp_hardware_cutoff_enabled": true,
  "otp_cutoff_temp_c": 105.0,
  "thermal_via_count_per_watt": 6.5,
  "via_plating_thickness_um": 25.0,
  "max_trace_temp_rise_c": 11.5,
  "power_layer_copper_oz": 2.0,
  "max_thermal_gradient_c_per_mm": 2.2,
  "min_power_ic_spacing_mm": 8.0,
  "precision_analog_thermal_isolation": true,
  "fdm_convergence_tol_c": 0.001,
  "grid_pitch_mm": 2.0,
  "tim_thermal_resistance_c_per_w": 0.35,
  "worst_case_ambient_verified": true,
  "ir_thermography_verified": true,
  "pmic_temp_telemetry_logged": true
}
```

---

## Security Disclosure

For security vulnerabilities, refer to [SECURITY.md](SECURITY.md). Please report issues to `security@logihertz.com`.

---

## Contributing

Review [CONTRIBUTING.md](CONTRIBUTING.md) and [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) for coding standards, pull request procedures, and community guidelines.

---

## License & Attribution

Copyright (c) 2026 Logihertz Systems (OPC) Private Limited & Sameer Tawade.

Licensed under the Apache License, Version 2.0 (the "License"); you may not use this file except in compliance with the License. You may obtain a copy of the License at [http://www.apache.org/licenses/LICENSE-2.0](http://www.apache.org/licenses/LICENSE-2.0).
