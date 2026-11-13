# Security Policy: lh-pcb-thermal-sim

Logihertz Systems (OPC) Private Limited maintains high assurance security and reliability standards for aerospace, robotics, and high-power embedded PCB hardware engineering.

## Supported Versions

| Version | Supported          | Security Maintenance Status |
|---------|--------------------|-----------------------------|
| 0.1.x   | :white_check_mark: | Active Current Release      |
| < 0.1.0 | :x:                | Unsupported                 |

## Threat Model & Scope

The `lh-pcb-thermal-sim` (`bin/lh-pcb-thermal`) simulates thermal dissipation and audits hardware thermal safety margins. Key security and physical safety considerations include:
- **Thermal Runaway & Over-Temperature Protection (OTP)**: Verifying hardware thermal shutdown thresholds ($T_{\text{cutoff}} \le 115^\circ\text{C}$) to prevent catastrophic battery ignition or silicon destruction.
- **FR-4 Glass Transition ($T_g$) Bounds**: Ensuring PCB laminate core temperatures do not approach delamination thresholds ($T \le T_g - 20^\circ\text{C}$).
- **IPC-2152 High-Current Joule Heating**: Guarding against trace necking, copper delamination, and excessive temperature rises in power delivery networks (PDN).
- **Thermo-Mechanical Stress**: Auditing maximum spatial thermal gradients ($|\nabla T|_{\max} \le 3.5^\circ\text{C/mm}$) to prevent BGA solder-joint shear fatigue and ceramic capacitor cracking.
- **Input Validation**: Hardening JSON board manifests and thermal policy parsers against unbounded grid dimensions, negative conductivities, and malformed layers.

## Reporting a Vulnerability

If you discover an issue or vulnerability in `lh-pcb-thermal-sim`, please contact the Logihertz security team:

- **Email**: `security@logihertz.com` (cc: `ops@logihertz.com`)
- **PGP Encryption**: Available upon request for confidential reports.
- **Information Required**:
  - Detailed description of the issue
  - Affected components (`stackup_math`, `fdm_solver`, `auditor`, etc.)
  - Reproduction manifest or steps
  - Estimated impact on hardware thermal safety

## Response Timeline

- **Initial Acknowledgement**: Within 24 business hours.
- **Triage & Assessment**: Within 72 business hours.
- **Remediation & Advisory**: Coordinated disclosure within 30 calendar days.
