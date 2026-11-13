"""Unit and integration test suite for lh-pcb-thermal-sim (85+ assertions)."""

from __future__ import annotations

import json
import math
import os
import subprocess
import sys
import unittest
from pathlib import Path

# Add src to path
SRC_DIR = Path(__file__).resolve().parent.parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from lh_pcb_thermal_sim.auditor import (
    PCBThermalPolicy,
    audit_pcb_thermal_policy,
)
from lh_pcb_thermal_sim.exporters import (
    render_json,
    render_sarif,
    render_table,
)
from lh_pcb_thermal_sim.fdm_solver import (
    FDMSolverConfig,
    PCBBoardDefinition,
    ThermalComponent,
    render_ascii_thermal_map,
    solve_2d_steady_state,
)
from lh_pcb_thermal_sim.stackup_math import (
    CopperLayer,
    DielectricLayer,
    PCBStackup,
    calculate_anisotropic_conductivities,
    calculate_ipc2152_trace_heating,
    calculate_thermal_via_resistance,
)


class TestStackupMath(unittest.TestCase):
    """Test anisotropic thermal conductivity, thermal vias, and IPC-2152 formulas."""

    def setUp(self) -> None:
        self.cu_layers = [
            CopperLayer(name="L1", thickness_m=3.5e-5, coverage_ratio=0.5),
            CopperLayer(name="L2_GND", thickness_m=3.5e-5, coverage_ratio=1.0),
            CopperLayer(name="L3_PWR", thickness_m=7.0e-5, coverage_ratio=0.8),  # 2 oz
            CopperLayer(name="L4", thickness_m=3.5e-5, coverage_ratio=0.5),
        ]
        self.diel_layers = [
            DielectricLayer(name="D1", thickness_m=0.0003, k_dielectric=0.30),
            DielectricLayer(name="D2", thickness_m=0.0008, k_dielectric=0.30),
            DielectricLayer(name="D3", thickness_m=0.0003, k_dielectric=0.30),
        ]
        self.stackup = PCBStackup(
            name="4-Layer-Test",
            copper_layers=self.cu_layers,
            dielectric_layers=self.diel_layers,
        )

    def test_anisotropic_conductivity(self) -> None:
        cond = calculate_anisotropic_conductivities(self.stackup)
        # In-plane conductivity must be much higher than through-plane
        self.assertGreater(cond.k_eff_xy, 15.0)
        self.assertLess(cond.k_eff_xy, 100.0)
        self.assertGreater(cond.k_eff_z, 0.25)
        self.assertLess(cond.k_eff_z, 0.50)
        self.assertGreater(cond.anisotropy_ratio, 30.0)
        self.assertAlmostEqual(cond.total_thickness_m, 0.001575, delta=1e-5)

    def test_copper_weight_monotonic_increase(self) -> None:
        # 1 oz planes vs 2 oz planes
        stackup_1oz = PCBStackup(
            name="1oz",
            copper_layers=[CopperLayer.from_oz("L1", 1.0, 1.0), CopperLayer.from_oz("L2", 1.0, 1.0)],
            dielectric_layers=[DielectricLayer("D1", 0.0015, 0.30)],
        )
        stackup_2oz = PCBStackup(
            name="2oz",
            copper_layers=[CopperLayer.from_oz("L1", 2.0, 1.0), CopperLayer.from_oz("L2", 2.0, 1.0)],
            dielectric_layers=[DielectricLayer("D1", 0.0015, 0.30)],
        )
        cond_1oz = calculate_anisotropic_conductivities(stackup_1oz)
        cond_2oz = calculate_anisotropic_conductivities(stackup_2oz)
        self.assertGreater(cond_2oz.k_eff_xy, cond_1oz.k_eff_xy)

    def test_stackup_zero_thickness_error(self) -> None:
        empty_stackup = PCBStackup(name="Empty", copper_layers=[], dielectric_layers=[])
        with self.assertRaises(ValueError):
            calculate_anisotropic_conductivities(empty_stackup)

    def test_thermal_via_resistance(self) -> None:
        # N=16 vias, 0.3mm drill, 25 um plating, 1.6mm board thickness
        r_16 = calculate_thermal_via_resistance(16, 0.3, 25.0, 0.0016)
        r_32 = calculate_thermal_via_resistance(32, 0.3, 25.0, 0.0016)

        self.assertGreater(r_16, 0.0)
        self.assertGreater(r_32, 0.0)
        # Doubling via count cuts thermal resistance roughly in half
        self.assertAlmostEqual(r_16 / r_32, 2.0, delta=0.01)

        # Zero or negative vias
        self.assertEqual(calculate_thermal_via_resistance(0, 0.3, 25.0, 0.0016), float("inf"))
        self.assertEqual(calculate_thermal_via_resistance(-5, 0.3, 25.0, 0.0016), float("inf"))

        # Thick plating (solid via)
        r_solid = calculate_thermal_via_resistance(16, 0.3, 200.0, 0.0016)
        self.assertGreater(r_solid, 0.0)
        self.assertLess(r_solid, r_16)

    def test_ipc2152_trace_heating(self) -> None:
        # 10A current on 3mm trace, 1 oz copper, external layer
        res = calculate_ipc2152_trace_heating(current_amps=10.0, width_mm=3.0, copper_oz=1.0, length_mm=50.0, is_internal=False)
        self.assertGreater(res.temp_rise_c, 5.0)
        self.assertLess(res.temp_rise_c, 50.0)
        self.assertGreater(res.dc_resistance_ohms, 0.0)
        self.assertGreater(res.joule_power_w, 0.0)

        # Doubling trace width decreases temperature rise
        res_wide = calculate_ipc2152_trace_heating(current_amps=10.0, width_mm=6.0, copper_oz=1.0, length_mm=50.0, is_internal=False)
        self.assertLess(res_wide.temp_rise_c, res.temp_rise_c)

        # Internal layer runs hotter due to lower thermal dissipation
        res_internal = calculate_ipc2152_trace_heating(current_amps=10.0, width_mm=3.0, copper_oz=1.0, length_mm=50.0, is_internal=True)
        self.assertGreater(res_internal.temp_rise_c, res.temp_rise_c)

        # Zero current produces zero rise
        res_zero = calculate_ipc2152_trace_heating(current_amps=0.0, width_mm=3.0)
        self.assertEqual(res_zero.temp_rise_c, 0.0)
        self.assertEqual(res_zero.joule_power_w, 0.0)

        # Invalid arguments raise ValueError
        with self.assertRaises(ValueError):
            calculate_ipc2152_trace_heating(current_amps=-1.0, width_mm=3.0)
        with self.assertRaises(ValueError):
            calculate_ipc2152_trace_heating(current_amps=5.0, width_mm=0.0)
        with self.assertRaises(ValueError):
            calculate_ipc2152_trace_heating(current_amps=5.0, width_mm=2.0, copper_oz=0.0)


class TestFDMSolver(unittest.TestCase):
    """Test 2D steady-state FDM SOR heat equation solver."""

    def setUp(self) -> None:
        self.stackup = PCBStackup(
            name="2L-Basic",
            copper_layers=[CopperLayer.from_oz("Top", 1.0, 0.5), CopperLayer.from_oz("Bottom", 1.0, 0.5)],
            dielectric_layers=[DielectricLayer("Core", 0.0016, 0.30)],
        )

    def test_zero_power_board_convergence(self) -> None:
        # A board with 0W dissipation must remain at ambient everywhere
        board = PCBBoardDefinition(
            name="Cold-Board",
            length_x_mm=50.0,
            length_y_mm=50.0,
            stackup=self.stackup,
            components=[],
            ambient_c=25.0,
            h_conv=12.5,
        )
        config = FDMSolverConfig(grid_pitch_mm=5.0, convergence_tol_c=1e-5)
        res = solve_2d_steady_state(board, config)

        self.assertTrue(res.converged)
        self.assertAlmostEqual(res.min_temp_c, 25.0, places=4)
        self.assertAlmostEqual(res.max_temp_c, 25.0, places=4)
        self.assertAlmostEqual(res.avg_temp_c, 25.0, places=4)
        self.assertEqual(res.total_input_power_w, 0.0)

    def test_energy_conservation(self) -> None:
        # Heat in must equal convective heat out (< 0.5% error)
        comp = ThermalComponent(
            name="Heater",
            x_mm=25.0,
            y_mm=25.0,
            width_mm=10.0,
            length_mm=10.0,
            power_w=5.0,
            r_theta_jb=5.0,
        )
        board = PCBBoardDefinition(
            name="Heated-Board",
            length_x_mm=50.0,
            length_y_mm=50.0,
            stackup=self.stackup,
            components=[comp],
            ambient_c=25.0,
            h_conv=15.0,
        )
        config = FDMSolverConfig(grid_pitch_mm=2.5, convergence_tol_c=1e-4)
        res = solve_2d_steady_state(board, config)

        self.assertTrue(res.converged)
        self.assertGreater(res.max_temp_c, 25.0)
        self.assertLess(res.energy_balance_error_pct, 0.5)  # < 0.5% error
        self.assertAlmostEqual(res.total_input_power_w, res.total_convective_heat_w, delta=0.05)

    def test_spatial_symmetry(self) -> None:
        # Symmetric square board with central heat source should produce identical corner temps
        comp = ThermalComponent(
            name="Center-IC",
            x_mm=30.0,
            y_mm=30.0,
            width_mm=10.0,
            length_mm=10.0,
            power_w=4.0,
        )
        board = PCBBoardDefinition(
            name="Symmetric-Board",
            length_x_mm=60.0,
            length_y_mm=60.0,
            stackup=self.stackup,
            components=[comp],
            ambient_c=25.0,
        )
        config = FDMSolverConfig(grid_pitch_mm=5.0, convergence_tol_c=1e-5)
        res = solve_2d_steady_state(board, config)

        t_00 = res.temperature_grid[0][0]
        t_0n = res.temperature_grid[0][res.grid_nx - 1]
        t_n0 = res.temperature_grid[res.grid_ny - 1][0]
        t_nn = res.temperature_grid[res.grid_ny - 1][res.grid_nx - 1]

        self.assertAlmostEqual(t_00, t_0n, delta=1e-4)
        self.assertAlmostEqual(t_00, t_n0, delta=1e-4)
        self.assertAlmostEqual(t_00, t_nn, delta=1e-4)

    def test_junction_temperature_and_vias(self) -> None:
        comp_no_via = ThermalComponent("NoVia", x_mm=20.0, y_mm=25.0, width_mm=6.0, length_mm=6.0, power_w=2.0, r_theta_jb=10.0)
        comp_with_via = ThermalComponent(
            "WithVia",
            x_mm=40.0,
            y_mm=25.0,
            width_mm=6.0,
            length_mm=6.0,
            power_w=2.0,
            r_theta_jb=10.0,
            num_thermal_vias=16,
            via_drill_diameter_mm=0.3,
            via_plating_um=25.0,
        )
        board = PCBBoardDefinition(
            name="Via-Test",
            length_x_mm=60.0,
            length_y_mm=50.0,
            stackup=self.stackup,
            components=[comp_no_via, comp_with_via],
            ambient_c=25.0,
        )
        res = solve_2d_steady_state(board)

        tj_no_via = res.component_results["NoVia"].junction_temp_c
        tj_with_via = res.component_results["WithVia"].junction_temp_c

        # Thermal vias reduce effective R_theta, leading to a cooler junction
        self.assertLess(tj_with_via, tj_no_via)
        self.assertGreater(tj_no_via, res.component_results["NoVia"].board_temp_c)

    def test_ascii_thermal_heatmap(self) -> None:
        comp = ThermalComponent("IC", 25.0, 25.0, 10.0, 10.0, power_w=3.0)
        board = PCBBoardDefinition("MapBoard", 50.0, 50.0, self.stackup, [comp], 25.0)
        res = solve_2d_steady_state(board, FDMSolverConfig(grid_pitch_mm=5.0))
        ascii_map = render_ascii_thermal_map(res)

        self.assertIn("--- 2D Thermal Field Map [MapBoard]", ascii_map)
        self.assertIn("Legend:", ascii_map)
        self.assertIn("@", ascii_map)  # Hotspot character


class TestAuditorAndPosture(unittest.TestCase):
    """Test 10-rule PCB thermal reliability auditor and score math."""

    def get_base_hardened_policy(self) -> PCBThermalPolicy:
        return PCBThermalPolicy(
            policy_id="HARDENED-TEST-01",
            board_name="Test-Board",
            max_junction_temp_c=85.0,
            tj_derating_margin_c=25.0,
            max_board_temp_c=75.0,
            fr4_tg_temp_c=170.0,
            otp_hardware_cutoff_enabled=True,
            otp_cutoff_temp_c=105.0,
            thermal_via_count_per_watt=6.0,
            via_plating_thickness_um=25.0,
            max_trace_temp_rise_c=12.0,
            power_layer_copper_oz=2.0,
            max_thermal_gradient_c_per_mm=2.1,
            min_power_ic_spacing_mm=8.0,
            precision_analog_thermal_isolation=True,
            fdm_convergence_tol_c=0.001,
            grid_pitch_mm=2.0,
            tim_thermal_resistance_c_per_w=0.35,
            worst_case_ambient_verified=True,
            ir_thermography_verified=True,
            pmic_temp_telemetry_logged=True,
        )

    def test_audit_hardened_score_100(self) -> None:
        policy = self.get_base_hardened_policy()
        report = audit_pcb_thermal_policy(policy)
        self.assertEqual(report.score, 100)
        self.assertEqual(report.passed_count, 10)
        self.assertEqual(report.failed_count, 0)
        self.assertEqual(report.total_deductions, 0)
        self.assertIn("HARDENED", report.verdict)

    def test_audit_vulnerable_score_0(self) -> None:
        vulnerable = PCBThermalPolicy(
            policy_id="VULNERABLE-TEST-01",
            board_name="Test-Board",
            max_junction_temp_c=115.0,  # Rule 1: -25
            tj_derating_margin_c=5.0,
            max_board_temp_c=130.0,  # Rule 2: -25
            fr4_tg_temp_c=140.0,
            otp_hardware_cutoff_enabled=False,  # Rule 3: -25
            otp_cutoff_temp_c=125.0,
            thermal_via_count_per_watt=2.0,  # Rule 4: -10
            via_plating_thickness_um=15.0,
            max_trace_temp_rise_c=28.0,  # Rule 5: -10
            power_layer_copper_oz=0.5,
            max_thermal_gradient_c_per_mm=4.5,  # Rule 6: -10
            min_power_ic_spacing_mm=3.0,  # Rule 7: -10
            precision_analog_thermal_isolation=False,
            fdm_convergence_tol_c=0.05,  # Rule 8: -4
            grid_pitch_mm=3.0,
            tim_thermal_resistance_c_per_w=0.8,  # Rule 9: -4
            worst_case_ambient_verified=False,
            ir_thermography_verified=False,  # Rule 10: -1
            pmic_temp_telemetry_logged=False,
        )
        report = audit_pcb_thermal_policy(vulnerable)
        self.assertEqual(report.score, 0)
        self.assertEqual(report.passed_count, 0)
        self.assertEqual(report.failed_count, 10)
        # 25*3 + 10*4 + 4*2 + 1 = 75 + 40 + 8 + 1 = 124
        self.assertEqual(report.total_deductions, 124)
        self.assertIn("CRITICAL", report.verdict)

    def test_audit_individual_rules(self) -> None:
        # Rule 1: -25
        p1 = self.get_base_hardened_policy()
        p1.max_junction_temp_c = 110.0
        r1 = audit_pcb_thermal_policy(p1)
        self.assertEqual(r1.score, 75)
        self.assertEqual(r1.findings[0].deduction, 25)
        self.assertFalse(r1.findings[0].passed)

        # Rule 2: -25
        p2 = self.get_base_hardened_policy()
        p2.max_board_temp_c = 160.0
        r2 = audit_pcb_thermal_policy(p2)
        self.assertEqual(r2.score, 75)
        self.assertFalse(r2.findings[1].passed)

        # Rule 3: -25
        p3 = self.get_base_hardened_policy()
        p3.otp_hardware_cutoff_enabled = False
        r3 = audit_pcb_thermal_policy(p3)
        self.assertEqual(r3.score, 75)
        self.assertFalse(r3.findings[2].passed)

        # Rule 4: -10
        p4 = self.get_base_hardened_policy()
        p4.thermal_via_count_per_watt = 2.0
        r4 = audit_pcb_thermal_policy(p4)
        self.assertEqual(r4.score, 90)
        self.assertFalse(r4.findings[3].passed)

        # Rule 5: -10
        p5 = self.get_base_hardened_policy()
        p5.max_trace_temp_rise_c = 25.0
        r5 = audit_pcb_thermal_policy(p5)
        self.assertEqual(r5.score, 90)
        self.assertFalse(r5.findings[4].passed)

        # Rule 6: -10
        p6 = self.get_base_hardened_policy()
        p6.max_thermal_gradient_c_per_mm = 4.0
        r6 = audit_pcb_thermal_policy(p6)
        self.assertEqual(r6.score, 90)
        self.assertFalse(r6.findings[5].passed)

        # Rule 7: -10
        p7 = self.get_base_hardened_policy()
        p7.precision_analog_thermal_isolation = False
        r7 = audit_pcb_thermal_policy(p7)
        self.assertEqual(r7.score, 90)
        self.assertFalse(r7.findings[6].passed)

        # Rule 8: -4
        p8 = self.get_base_hardened_policy()
        p8.grid_pitch_mm = 3.0
        r8 = audit_pcb_thermal_policy(p8)
        self.assertEqual(r8.score, 96)
        self.assertFalse(r8.findings[7].passed)

        # Rule 9: -4
        p9 = self.get_base_hardened_policy()
        p9.tim_thermal_resistance_c_per_w = 0.8
        r9 = audit_pcb_thermal_policy(p9)
        self.assertEqual(r9.score, 96)
        self.assertFalse(r9.findings[8].passed)

        # Rule 10: -1
        p10 = self.get_base_hardened_policy()
        p10.ir_thermography_verified = False
        r10 = audit_pcb_thermal_policy(p10)
        self.assertEqual(r10.score, 99)
        self.assertFalse(r10.findings[9].passed)

        # Partial combined score check: Rule 1 (25) + Rule 4 (10) = 100 - 35 = 65 (VULNERABLE)
        p_combo = self.get_base_hardened_policy()
        p_combo.max_junction_temp_c = 110.0
        p_combo.thermal_via_count_per_watt = 2.0
        r_combo = audit_pcb_thermal_policy(p_combo)
        self.assertEqual(r_combo.score, 65)
        self.assertIn("VULNERABLE", r_combo.verdict)


class TestExportersAndFixtures(unittest.TestCase):
    """Test table, JSON, and SARIF exporters and fixture files."""

    def setUp(self) -> None:
        self.fixtures_dir = Path(__file__).resolve().parent.parent / "fixtures"

    def test_exporters_output(self) -> None:
        policy = PCBThermalPolicy("TEST-POL", "Board-A")
        report = audit_pcb_thermal_policy(policy)

        # Table
        tbl = render_table(report)
        self.assertIn("LOGIHERTZ PCB THERMAL", tbl)
        self.assertIn("LH-PCB-001", tbl)

        # JSON
        js = render_json(report)
        data = json.loads(js)
        self.assertEqual(data["score"], 100)
        self.assertEqual(data["policy_id"], "TEST-POL")

        # SARIF
        sarif_str = render_sarif(report)
        sarif_doc = json.loads(sarif_str)
        self.assertEqual(sarif_doc["version"], "2.1.0")
        self.assertEqual(sarif_doc["runs"][0]["tool"]["driver"]["name"], "lh-pcb-thermal")

    def test_fixtures_end_to_end(self) -> None:
        # 1. Hardened fixture
        hardened_path = self.fixtures_dir / "hardened_pcb_policy.json"
        hard_pol = PCBThermalPolicy.from_file(hardened_path)
        hard_rep = audit_pcb_thermal_policy(hard_pol)
        self.assertEqual(hard_rep.score, 100)
        self.assertEqual(hard_rep.failed_count, 0)

        # 2. Vulnerable fixture
        vuln_path = self.fixtures_dir / "vulnerable_pcb_policy.json"
        vuln_pol = PCBThermalPolicy.from_file(vuln_path)
        vuln_rep = audit_pcb_thermal_policy(vuln_pol)
        self.assertEqual(vuln_rep.score, 0)
        self.assertEqual(vuln_rep.failed_count, 10)

        # 3. Sample Jetson board fixture
        board_path = self.fixtures_dir / "sample_jetson_carrier_board.json"
        with open(board_path, "r", encoding="utf-8") as f:
            b_data = json.load(f)
        self.assertEqual(b_data["name"], "Jetson-Orin-Robotics-Carrier-8L")
        self.assertEqual(len(b_data["components"]), 5)
        self.assertEqual(len(b_data["stackup"]["copper_layers"]), 8)


class TestCLISubprocess(unittest.TestCase):
    """Test CLI commands via subprocess."""

    def setUp(self) -> None:
        self.root_dir = Path(__file__).resolve().parent.parent
        self.cli_bin = self.root_dir / "bin" / "lh-pcb-thermal"
        self.fixtures_dir = self.root_dir / "fixtures"

    def run_cmd(self, *args: str) -> subprocess.CompletedProcess[str]:
        cmd = [sys.executable, str(self.cli_bin), *args]
        return subprocess.run(cmd, capture_output=True, text=True)

    def test_version_and_help(self) -> None:
        res_v = self.run_cmd("--version")
        self.assertEqual(res_v.returncode, 0)
        self.assertIn("lh-pcb-thermal 0.1.0", res_v.stdout)

        res_h = self.run_cmd("--help")
        self.assertEqual(res_h.returncode, 0)
        self.assertIn("usage: lh-pcb-thermal", res_h.stdout)

    def test_scan_hardened(self) -> None:
        path = str(self.fixtures_dir / "hardened_pcb_policy.json")
        res = self.run_cmd("scan", path, "--format", "table")
        self.assertEqual(res.returncode, 0)
        self.assertIn("HARDENED", res.stdout)

        res_json = self.run_cmd("scan", path, "--format", "json")
        self.assertEqual(res_json.returncode, 0)
        self.assertIn('"score": 100', res_json.stdout)

        res_sarif = self.run_cmd("scan", path, "--format", "sarif")
        self.assertEqual(res_sarif.returncode, 0)
        self.assertIn('"version": "2.1.0"', res_sarif.stdout)

    def test_scan_vulnerable(self) -> None:
        path = str(self.fixtures_dir / "vulnerable_pcb_policy.json")
        res = self.run_cmd("scan", path)
        self.assertEqual(res.returncode, 1)  # Vulnerability detected
        self.assertIn("CRITICAL", res.stdout)

    def test_simulate_board(self) -> None:
        path = str(self.fixtures_dir / "sample_jetson_carrier_board.json")
        res = self.run_cmd("simulate", path, "--heatmap")
        self.assertEqual(res.returncode, 0)
        self.assertIn("SoC-Orin-NX", res.stdout)
        self.assertIn("Energy Balance Error:", res.stdout)
        self.assertIn("--- 2D Thermal Field Map", res.stdout)

    def test_calc_stackup(self) -> None:
        path = str(self.fixtures_dir / "sample_jetson_carrier_board.json")
        res = self.run_cmd("calc-stackup", path)
        self.assertEqual(res.returncode, 0)
        self.assertIn("In-Plane Conductivity", res.stdout)
        self.assertIn("Thermal Anisotropy Ratio", res.stdout)

    def test_ipc2152_trace_heating_cli(self) -> None:
        # Safe 5A trace
        res = self.run_cmd("ipc2152", "--current-amps", "5.0", "--width-mm", "2.0")
        self.assertEqual(res.returncode, 0)
        self.assertIn("Computed Temperature Rise:", res.stdout)

        # Overheated 25A on tiny 0.5mm trace
        res_hot = self.run_cmd("ipc2152", "--current-amps", "25.0", "--width-mm", "0.5")
        self.assertEqual(res_hot.returncode, 1)
        self.assertIn("Warning: Trace temperature rise", res_hot.stderr)

    def test_invalid_cli_usage(self) -> None:
        res = self.run_cmd("invalid-command")
        self.assertEqual(res.returncode, 2)


if __name__ == "__main__":
    unittest.main()
