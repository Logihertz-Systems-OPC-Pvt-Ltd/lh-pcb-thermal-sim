# Contributing to lh-pcb-thermal-sim

Thank you for your interest in contributing to `lh-pcb-thermal-sim` (`bin/lh-pcb-thermal`), the zero-dependency Python multi-layer PCB 2D thermal simulator and hardware reliability auditor.

## Core Governance Mandates

1. **Zero External Runtime Dependencies**:
   The simulator and auditor must execute with pure Python 3.11+ standard library modules (`json`, `math`, `hashlib`, `argparse`, `pathlib`, `dataclasses`, `typing`). No external runtime packages (NumPy, SciPy, etc.) are allowed.
2. **Deterministic Physics & Numerics**:
   All 2D FDM SOR iterations, energy balance calculations, anisotropic thermal conductivity homogenizations, and IPC-2152 equations must be numerically deterministic and rigorously tested.
3. **Quality Gates**:
   All contributions must pass:
   ```bash
   python3 -m py_compile src/lh_pcb_thermal_sim/*.py tests/test_pcb_thermal_sim.py
   PYTHONPATH=src python3 -m unittest discover -s tests -v
   ```

## Development Workflow

1. Fork or clone the repository:
   ```bash
   git clone https://github.com/Logihertz-Systems-OPC-Pvt-Ltd/lh-pcb-thermal-sim.git
   cd lh-pcb-thermal-sim
   ```

2. Make changes in `src/lh_pcb_thermal_sim/`.

3. Add comprehensive tests in `tests/test_pcb_thermal_sim.py`.

4. Run the test suite:
   ```bash
   PYTHONPATH=src python3 -m unittest discover -s tests -v
   ```

5. Submit pull requests with clear conventional commit messages (`feat:`, `fix:`, `docs:`, `test:`).
