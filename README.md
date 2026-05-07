# NGFW Security Control Validation Framework

## Executive Summary

This repository is a reproducible, open-source security control validation framework, not a commercial firewall product.

The goal is to validate how network controls behave under adversarial pressure, telemetry load, and infrastructure constraints. Instead of assuming a rule set is effective because it exists, this project treats efficacy as something that must be measured, explained, and repeated.

The platform is intentionally engineered as a measurement system for network defense behavior.

## Project Identity

### What this project is

- A controlled validation harness for firewall policy behavior, IDS alerting, telemetry ingestion, and API-driven policy operations.
- A systems-engineering workflow for proving security control performance with repeatable experiments.
- A constraint-aware lab architecture that prioritizes observability, reproducibility, and defensible conclusions.

### What this project is not

- A turnkey enterprise NGFW appliance.
- A SIEM or SOAR replacement.
- A claim that all malicious traffic can be blocked automatically.

## Core Question

How can we verify that a network security control behaves as expected under realistic attack traffic, telemetry variation, and operational constraints?

## Architecture

The system is intentionally separated into four planes.

| Plane | Main Components | Purpose |
| --- | --- | --- |
| Control and Data Plane | OPNsense, pf | Stateful packet filtering, rule ordering, alias resolution, default-deny enforcement |
| Detection Plane | Suricata (IDS mode) | Signature-based application-layer inspection and alert generation |
| Telemetry and Analytics Plane | Ubuntu, rsyslog, Python ML pipeline | Dual-stream ingestion, normalization, feature extraction, anomaly scoring |
| Adversarial Plane | Kali scenarios in Podman | Controlled attack generation and ground-truth traffic injection |

### Topology

- Kali on OPT1 network: 192.168.60.x
- Ubuntu target on LAN: 192.168.50.10
- OPNsense interfaces: em2 (OPT1), em1 (LAN), em0 (WAN)

Traffic path:

Kali -> OPNsense -> Ubuntu

Return traffic is statefully tracked by pf.

## Why the Project Shifted from Product Thinking to Validation Thinking

Commercial security tools hide major internals behind proprietary interfaces. That can obscure whether controls are genuinely effective.

This project externalizes those internals so policy, detection, and telemetry behavior can be observed directly. The shift to validation-first engineering is deliberate and academically stronger for several reasons.

1. Ground-truth alignment: each observed alert can be traced to known scenario activity.
2. Dual-source telemetry realism: pf filterlog and Suricata alerts represent different layers and must be reconciled.
3. Policy propagation reality: alias updates, reload timing, and state handling are measured as part of control validity.
4. Evaluation integrity: detection quality is prioritized before aggressive autonomous response loops.

## End-to-End Data and Control Flow

1. Kali scenarios generate controlled adversarial traffic.
2. pf evaluates ordered rules and state entries.
3. Suricata inspects allowed traffic and emits IDS alerts.
4. OPNsense forwards telemetry streams.
5. Ubuntu ingests and normalizes logs.
6. The ML pipeline parses and scores events in anomaly-only mode.
7. The control API exposes operations and telemetry views.
8. The dashboard presents control, telemetry, and ML analytics for operator review.

## Engineering Philosophy

- Validation over assumption.
- Reproducibility over one-off demos.
- Deterministic policy behavior over opaque automation.
- Detection and triage before autonomous enforcement.
- Explicit constraints as design inputs, not excuses.

## Constraints and Deliberate Trade-offs

| Constraint | Design Decision | Rationale |
| --- | --- | --- |
| Virtualized lab resources | Serialized workloads and scoped scenarios | Preserve stability and measurement quality |
| FreeBSD em driver environment | Suricata IDS-first operation in lab | Favor inspection visibility and continuity |
| No fully autonomous blocking loop | Human-in-the-loop validation workflow | Avoid false-positive cascades during evaluation |
| Lab-generated data | Ground-truth from documented scenarios | Maintain schema and behavior fidelity |
| API policy updates | Strict alias typing and explicit reload behavior | Keep policy behavior auditable and deterministic |

## Current Implementation Notes

### Firewall and alias model

- KALI_HOST and AUTO_BAN_IPS use Host(s) alias semantics.
- API integration supports alias updates through OPNsense REST paths.
- For restrictive OPNsense API permissions, UUID override support exists through:
  - OPNSENSE_BAN_ALIAS_UUID
  - OPNSENSE_KALI_ALIAS_UUID
- Runtime UUID caching reduces intermittent alias inventory lookup failures.

### Detection and telemetry

- Suricata runs in IDS-oriented validation mode in this framework.
- Telemetry summaries are protocol, source, and action focused.
- Signature visibility is preserved for investigation and correlation.

### ML pipeline

- Anomaly-only pipeline (Isolation Forest plus preprocessor).
- Parser defaults to filterlog-first ingestion for model features.
- Suricata inclusion in ML features is optional by parser flag.

## Evidence-Driven Validation

Diagnostics snapshots in this repository show deterministic allow, block, and alert behavior under controlled test traffic.

Representative evidence patterns include:

- Explicit pass rules from KALI_HOST to UBUNTU_HOST on intended service ports.
- Explicit DNS egress block rules for disallowed flows.
- Default deny behavior for unmatched traffic.
- Suricata alert emission on adversarial web probes.
- Alias counters and rule match data supporting policy-path verification.

Use diagnostics artifacts as experiment evidence, not as static configuration templates.

## Repository Map

- control-api: FastAPI control and telemetry endpoints.
- dashboard: Single-page operations and analytics UI.
- kali-scenarios: Adversarial traffic scripts.
- ml: Parse, train, infer pipeline.
- OPNsense_Click_By_Click_Checklist.md: Firewall build runbook.
- OPNsense_Point_By_Point_Tests.md: Validation test runbook.
- Ubuntu_Checklist.md: Telemetry and API host runbook.
- Kali_Checklist.md: Attacker workflow and scenario execution.
- report: Project writeups.

## Running the Framework

For full setup and execution, follow the runbooks in this order:

1. OPNsense_Click_By_Click_Checklist.md
2. Ubuntu_Checklist.md
3. Kali_Checklist.md
4. OPNsense_Point_By_Point_Tests.md

## Academic and Professional Value

This project demonstrates practical competence in:

- Network policy engineering and stateful filtering.
- IDS telemetry interpretation and correlation.
- Security data pipeline design.
- API-driven policy orchestration.
- Constraint-aware systems engineering.
- Validation methodology for security controls.

Its strongest contribution is methodological: it provides a reproducible way to test and reason about security control behavior under controlled adversarial conditions.

## Known Limits

- This is a lab validation framework, not a production SLA platform.
- Throughput and latency characteristics are bound by virtualization and host resources.
- Results are meaningful for validation and engineering insight, not universal threat coverage guarantees.

## Practical Next Steps

- Add versioned experiment profiles for repeatability across semesters or teams.
- Add automated report generation from telemetry and scenario metadata.
- Add controlled response simulation stages after detection quality baselines are stable.
- Expand reliability diagnostics for OPNsense alias API edge cases.
