"""ANSI Terminal Table, Canonical JSON, and OASIS SARIF v2.1.0 report exporters."""

from __future__ import annotations

import json
from typing import Any, Dict

from .auditor import PostureReport


def render_table(report: PostureReport) -> str:
    """Render an ANSI terminal box table representing the audit report."""
    lines = [
        "",
        "========================================================================================",
        "  LOGIHERTZ PCB THERMAL RELIABILITY AUDITOR (lh-pcb-thermal v0.1.0)",
        "========================================================================================",
        f"  Policy ID: {report.policy_id:<20}  Board: {report.board_name}",
        f"  Overall Posture Score:  {report.score} / 100    Verdict: {report.verdict}",
        f"  Rules Passed: {report.passed_count}/10  |  Rules Failed: {report.failed_count}/10  |  Total Deductions: -{report.total_deductions}",
        "",
        "┌──────────────┬──────────┬────────┬───────┬─────────────────────────────────────────────┐",
        "│ Rule ID      │ Severity │ Status │ Deduct│ Rule Title & Description                    │",
        "├──────────────┼──────────┼────────┼───────┼─────────────────────────────────────────────┤",
    ]

    for f in report.findings:
        status_str = " PASS " if f.passed else " FAIL "
        deduct_str = "-0   " if f.passed else f"-{f.deduction:<4}"

        title_trunc = f.title
        if len(title_trunc) > 43:
            title_trunc = title_trunc[:40] + "..."

        lines.append(f"│ {f.rule_id:<12} │ {f.severity:<8} │ {status_str} │ {deduct_str} │ {title_trunc:<43} │")

        if not f.passed:
            remed_trunc = f.remediation
            if len(remed_trunc) > 70:
                remed_trunc = remed_trunc[:67] + "..."
            lines.append(f"│              └─► Remediation: {remed_trunc:<59} │")

    lines.append("└──────────────┴──────────┴────────┴───────┴─────────────────────────────────────────────┘")
    lines.append("")
    return "\n".join(lines)


def render_json(report: PostureReport) -> str:
    """Render the PostureReport as canonical indented JSON."""
    return json.dumps(report.to_dict(), indent=2, sort_keys=True)


def render_sarif(report: PostureReport) -> str:
    """Render the audit findings in OASIS SARIF v2.1.0 format."""
    rules = []
    results = []

    for f in report.findings:
        rules.append(
            {
                "id": f.rule_id,
                "name": f.title,
                "shortDescription": {"text": f.title},
                "help": {"text": f"CWE: {f.cwe}. Remediation: {f.remediation}"},
            }
        )

        if not f.passed:
            level = "warning"
            if f.severity in ("CRITICAL", "HIGH"):
                level = "error"
            elif f.severity == "MEDIUM":
                level = "warning"
            elif f.severity == "LOW":
                level = "note"

            results.append(
                {
                    "ruleId": f.rule_id,
                    "level": level,
                    "message": {"text": f.message},
                }
            )

    sarif_doc: Dict[str, Any] = {
        "$schema": "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/Schemata/sarif-schema-2.1.0.json",
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "lh-pcb-thermal",
                        "version": "0.1.0",
                        "informationUri": "https://github.com/Logihertz-Systems-OPC-Pvt-Ltd/lh-pcb-thermal-sim",
                        "rules": rules,
                    }
                },
                "results": results,
            }
        ],
    }
    return json.dumps(sarif_doc, indent=2)
