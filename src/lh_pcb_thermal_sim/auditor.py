"""10-Rule deterministic PCB thermal reliability posture auditor."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List


@dataclass
class PCBThermalPolicy:
    """Configuration parameters representing a PCB hardware thermal design policy."""

    policy_id: str
    board_name: str
    max_junction_temp_c: float = 85.0
    tj_derating_margin_c: float = 25.0
    max_board_temp_c: float = 75.0
    fr4_tg_temp_c: float = 170.0
    otp_hardware_cutoff_enabled: bool = True
    otp_cutoff_temp_c: float = 105.0
    thermal_via_count_per_watt: float = 6.0
    via_plating_thickness_um: float = 25.0
    max_trace_temp_rise_c: float = 12.0
    power_layer_copper_oz: float = 2.0
    max_thermal_gradient_c_per_mm: float = 2.1
    min_power_ic_spacing_mm: float = 8.0
    precision_analog_thermal_isolation: bool = True
    fdm_convergence_tol_c: float = 0.001
    grid_pitch_mm: float = 2.0
    tim_thermal_resistance_c_per_w: float = 0.35
    worst_case_ambient_verified: bool = True
    ir_thermography_verified: bool = True
    pmic_temp_telemetry_logged: bool = True

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> PCBThermalPolicy:
        valid_fields = {f for f in cls.__dataclass_fields__}
        filtered = {k: v for k, v in data.items() if k in valid_fields}
        return cls(**filtered)

    @classmethod
    def from_file(cls, path: str | Path) -> PCBThermalPolicy:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls.from_dict(data)


@dataclass
class PostureFinding:
    """Individual rule evaluation finding."""

    rule_id: str
    title: str
    severity: str  # CRITICAL, HIGH, MEDIUM, LOW
    deduction: int
    cwe: str
    passed: bool
    message: str
    remediation: str


@dataclass
class PostureReport:
    """Aggregated posture report across all 10 normative thermal rules."""

    policy_id: str
    board_name: str
    score: int
    verdict: str  # HARDENED, ADEQUATE, VULNERABLE, CRITICAL
    total_deductions: int
    passed_count: int
    failed_count: int
    findings: List[PostureFinding] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "policy_id": self.policy_id,
            "board_name": self.board_name,
            "score": self.score,
            "verdict": self.verdict,
            "total_deductions": self.total_deductions,
            "passed_count": self.passed_count,
            "failed_count": self.failed_count,
            "findings": [asdict(f) for f in self.findings],
        }


def audit_pcb_thermal_policy(policy: PCBThermalPolicy) -> PostureReport:
    """Audit a PCB thermal policy against all 10 normative security and reliability rules."""
    findings: List[PostureFinding] = []
    total_deductions = 0

    # Rule 1: LH-PCB-001 (CRITICAL, 25, CWE-682)
    p1 = (policy.max_junction_temp_c <= 105.0) and (policy.tj_derating_margin_c >= 15.0)
    d1 = 25
    if p1:
        m1 = f"Component junction temperature ({policy.max_junction_temp_c:.1f}°C) within derated ceiling (margin: {policy.tj_derating_margin_c:.1f}°C)."
    else:
        m1 = f"Junction temperature exceeds 105°C ({policy.max_junction_temp_c:.1f}°C) or derating margin < 15°C ({policy.tj_derating_margin_c:.1f}°C); risk of silicon electromigration."
        total_deductions += d1
    findings.append(
        PostureFinding(
            rule_id="LH-PCB-001",
            title="Component Junction Temperature Reliability & Derating Margin",
            severity="CRITICAL",
            deduction=d1,
            cwe="CWE-682",
            passed=p1,
            message=m1,
            remediation="Reduce component power dissipation, enlarge thermal copper pours, or add active cooling to maintain Tj <= 105°C and derating margin >= 15°C.",
        )
    )

    # Rule 2: LH-PCB-002 (CRITICAL, 25, CWE-400)
    p2 = (policy.max_board_temp_c <= (policy.fr4_tg_temp_c - 20.0)) and (policy.fr4_tg_temp_c >= 150.0)
    d2 = 25
    if p2:
        m2 = f"PCB laminate peak temp ({policy.max_board_temp_c:.1f}°C) safely below FR-4 Tg ({policy.fr4_tg_temp_c:.1f}°C) with >= 20°C guardband."
    else:
        m2 = f"PCB laminate peak temp ({policy.max_board_temp_c:.1f}°C) dangerously close to Tg ({policy.fr4_tg_temp_c:.1f}°C) or low-Tg laminate (< 150°C) used; risk of delamination."
        total_deductions += d2
    findings.append(
        PostureFinding(
            rule_id="LH-PCB-002",
            title="PCB FR-4 Glass Transition (Tg) Safety Boundary & Delamination Guard",
            severity="CRITICAL",
            deduction=d2,
            cwe="CWE-400",
            passed=p2,
            message=m2,
            remediation="Select High-Tg laminate (Tg >= 170°C) and keep peak laminate temperature at least 20°C below Tg.",
        )
    )

    # Rule 3: LH-PCB-003 (CRITICAL, 25, CWE-754)
    p3 = policy.otp_hardware_cutoff_enabled and (policy.otp_cutoff_temp_c <= 115.0)
    d3 = 25
    if p3:
        m3 = f"Hardware OTP thermal shutdown active with safe cutoff trip point ({policy.otp_cutoff_temp_c:.1f}°C)."
    else:
        m3 = "Hardware OTP thermal shutdown missing or trip temperature set above 115°C; catastrophic thermal runaway hazard."
        total_deductions += d3
    findings.append(
        PostureFinding(
            rule_id="LH-PCB-003",
            title="Hardware Over-Temperature Protection (OTP) Thermal Cutoff Safeguard",
            severity="CRITICAL",
            deduction=d3,
            cwe="CWE-754",
            passed=p3,
            message=m3,
            remediation="Implement hardware NTC/PMIC thermal shutdown circuit with cutoff trip point <= 115°C.",
        )
    )

    # Rule 4: LH-PCB-004 (HIGH, 10, CWE-682)
    p4 = (policy.thermal_via_count_per_watt >= 4.0) and (policy.via_plating_thickness_um >= 20.0)
    d4 = 10
    if p4:
        m4 = f"Adequate thermal via stitching ({policy.thermal_via_count_per_watt:.1f} vias/W, {policy.via_plating_thickness_um:.1f} um barrel) under power pads."
    else:
        m4 = f"Insufficient thermal via density ({policy.thermal_via_count_per_watt:.1f} vias/W < 4) or thin copper plating (< 20 um); excessive junction-to-board resistance."
        total_deductions += d4
    findings.append(
        PostureFinding(
            rule_id="LH-PCB-004",
            title="Thermal Via Array Density & Plating Barrel Thickness Under Power Pads",
            severity="HIGH",
            deduction=d4,
            cwe="CWE-682",
            passed=p4,
            message=m4,
            remediation="Stitch at least 4 thermal vias per Watt under exposed thermal pads with plating thickness >= 20 um.",
        )
    )

    # Rule 5: LH-PCB-005 (HIGH, 10, CWE-682)
    p5 = (policy.max_trace_temp_rise_c <= 20.0) and (policy.power_layer_copper_oz >= 1.0)
    d5 = 10
    if p5:
        m5 = f"IPC-2152 trace temperature rise ({policy.max_trace_temp_rise_c:.1f}°C) and copper weight ({policy.power_layer_copper_oz:.1f} oz) within reliability limits."
    else:
        m5 = f"Trace temperature rise exceeds 20°C ({policy.max_trace_temp_rise_c:.1f}°C) or undersized power plane copper (< 1 oz); risk of trace necking or delamination."
        total_deductions += d5
    findings.append(
        PostureFinding(
            rule_id="LH-PCB-005",
            title="IPC-2152 High-Current Power Trace Temperature Rise & Copper Weight",
            severity="HIGH",
            deduction=d5,
            cwe="CWE-682",
            passed=p5,
            message=m5,
            remediation="Widen high-current power traces or increase copper weight to >= 2 oz to maintain IPC-2152 temperature rise <= 20°C.",
        )
    )

    # Rule 6: LH-PCB-006 (HIGH, 10, CWE-662)
    p6 = policy.max_thermal_gradient_c_per_mm <= 3.5
    d6 = 10
    if p6:
        m6 = f"In-plane thermal gradient ({policy.max_thermal_gradient_c_per_mm:.2f}°C/mm) safely bounded below 3.5°C/mm."
    else:
        m6 = f"Excessive spatial thermal gradient ({policy.max_thermal_gradient_c_per_mm:.2f}°C/mm > 3.5); causes BGA solder fatigue and MLCC ceramic cracking."
        total_deductions += d6
    findings.append(
        PostureFinding(
            rule_id="LH-PCB-006",
            title="In-Plane Spatial Thermal Gradient & Thermo-Mechanical Fatigue Defense",
            severity="HIGH",
            deduction=d6,
            cwe="CWE-662",
            passed=p6,
            message=m6,
            remediation="Distribute heat spreaders and increase internal plane copper coverage to limit thermal gradient <= 3.5°C/mm.",
        )
    )

    # Rule 7: LH-PCB-007 (HIGH, 10, CWE-20)
    p7 = (policy.min_power_ic_spacing_mm >= 5.0) and policy.precision_analog_thermal_isolation
    d7 = 10
    if p7:
        m7 = f"Safe power IC keepout spacing ({policy.min_power_ic_spacing_mm:.1f} mm) and precision analog/clock thermal isolation active."
    else:
        m7 = "Power ICs clustered with < 5mm spacing or sensitive analog/reference circuitry lacks thermal isolation from heat plumes."
        total_deductions += d7
    findings.append(
        PostureFinding(
            rule_id="LH-PCB-007",
            title="High-Power Component Placement Keepout & Sensitive Analog Thermal Isolation",
            severity="HIGH",
            deduction=d7,
            cwe="CWE-20",
            passed=p7,
            message=m7,
            remediation="Maintain >= 5mm separation between high-power ICs and thermally isolate precision analog/TCXO circuitry.",
        )
    )

    # Rule 8: LH-PCB-008 (MEDIUM, 4, CWE-682)
    p8 = (policy.fdm_convergence_tol_c <= 0.01) and (policy.grid_pitch_mm <= 2.5)
    d8 = 4
    if p8:
        m8 = f"High-resolution FDM thermal solver configured (tol: {policy.fdm_convergence_tol_c}°C, pitch: {policy.grid_pitch_mm:.1f} mm)."
    else:
        m8 = f"Coarse grid pitch ({policy.grid_pitch_mm:.1f} mm > 2.5) or loose solver convergence tolerance (> 0.01°C); risk of uncaptured localized hotspots."
        total_deductions += d8
    findings.append(
        PostureFinding(
            rule_id="LH-PCB-008",
            title="2D FDM Thermal Solver Convergence Tolerance & Grid Resolution",
            severity="MEDIUM",
            deduction=d8,
            cwe="CWE-682",
            passed=p8,
            message=m8,
            remediation="Set FDM convergence tolerance <= 0.01°C and spatial grid pitch <= 2.5mm.",
        )
    )

    # Rule 9: LH-PCB-009 (MEDIUM, 4, CWE-693)
    p9 = (policy.tim_thermal_resistance_c_per_w <= 0.5) and policy.worst_case_ambient_verified
    d9 = 4
    if p9:
        m9 = f"Low thermal interface material resistance ({policy.tim_thermal_resistance_c_per_w:.2f}°C/W) and verified worst-case ambient modeling."
    else:
        m9 = "High TIM contact resistance (> 0.5°C/W) or simulation unverified against worst-case maximum operating ambient temperature."
        total_deductions += d9
    findings.append(
        PostureFinding(
            rule_id="LH-PCB-009",
            title="Thermal Interface Material (TIM) Thermal Resistance & Ambient Validation",
            severity="MEDIUM",
            deduction=d9,
            cwe="CWE-693",
            passed=p9,
            message=m9,
            remediation="Use high-performance TIM with resistance <= 0.5°C/W and verify operation against worst-case maximum ambient.",
        )
    )

    # Rule 10: LH-PCB-010 (LOW, 1, CWE-778)
    p10 = policy.ir_thermography_verified and policy.pmic_temp_telemetry_logged
    d10 = 1
    if p10:
        m10 = "Empirical IR thermography correlation completed and runtime PMIC/SoC temperature telemetry active."
    else:
        m10 = "Simulation unverified by empirical IR thermography or runtime PMIC temperature telemetry unlogged."
        total_deductions += d10
    findings.append(
        PostureFinding(
            rule_id="LH-PCB-010",
            title="Empirical Infrared (IR) Thermography Baseline & Runtime PMIC Telemetry",
            severity="LOW",
            deduction=d10,
            cwe="CWE-778",
            passed=p10,
            message=m10,
            remediation="Validate thermal model with empirical IR thermography and log runtime PMIC/SoC temperature telemetry.",
        )
    )

    score = max(0, 100 - total_deductions)
    passed_count = sum(1 for f in findings if f.passed)
    failed_count = len(findings) - passed_count

    if score >= 90:
        verdict = "HARDENED (Aerospace & Industrial High-Reliability Thermal Margins)"
    elif score >= 70:
        verdict = "ADEQUATE (Minor Thermal Derating or Keepout Risks Present)"
    elif score >= 50:
        verdict = "VULNERABLE (Elevated Hotspot or Thermal Gradient Failure Risk)"
    else:
        verdict = "CRITICAL (Severe Thermal Runaway or Delamination Vulnerability)"

    return PostureReport(
        policy_id=policy.policy_id,
        board_name=policy.board_name,
        score=score,
        verdict=verdict,
        total_deductions=total_deductions,
        passed_count=passed_count,
        failed_count=failed_count,
        findings=findings,
    )
