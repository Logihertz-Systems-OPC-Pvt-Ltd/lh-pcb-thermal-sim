# Changelog

All notable changes to `lh-pcb-thermal-sim` will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-11-13

### Added
- Pure Python 2D steady-state heat conduction-convection PDE solver using Finite-Difference Method (FDM) with Successive Over-Relaxation (SOR).
- Global energy conservation verification verifying total component heat input against surface convective dissipation (< 1% relative error).
- Anisotropic multi-layer copper/FR-4 effective thermal conductivity calculator ($k_{\text{eff}, xy}$ in-plane and $k_{\text{eff}, z}$ through-plane).
- Plated through-hole (PTH) thermal via barrel resistance modeling ($R_{\theta, \text{vias}}$).
- IPC-2152 trace Joule heating and temperature-compensated DC resistance engine for internal and external layers.
- Component silicon junction temperature ($T_J$) estimation and spatial thermal gradient ($|\nabla T|_{\max}$) mapping in $^\circ\text{C/mm}$.
- 2D ASCII/ANSI thermal heatmap rendering (`[ . : + * # @ ]`).
- 10-rule deterministic PCB thermal reliability posture auditor (`LH-PCB-001` through `LH-PCB-010`) scoring out of 100.
- Multi-format exporters: ANSI Box Tables, Canonical JSON, and OASIS SARIF v2.1.0.
- Command-line interface (`bin/lh-pcb-thermal`) with subcommands `scan`, `simulate`, `calc-stackup`, `ipc2152`, `--version`, and `--help`.
- Comprehensive unit test suite in `tests/test_pcb_thermal_sim.py` with 85+ deterministic assertions.
