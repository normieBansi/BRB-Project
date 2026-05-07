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

## Technology Stack

The stack is selected for observability, deterministic control behavior, and reproducible lab validation rather than production throughput optimization.

| Layer | Technologies | Responsibility in this framework |
| --- | --- | --- |
| Hypervisor and Lab Runtime | Virtualized lab environment, segmented virtual networks | Hosts isolated security zones and reproducible test topology |
| Firewall and Policy Engine | OPNsense, pf, alias tables, rule ordering | Enforces pass and block logic, state tracking, and default deny behavior |
| Detection Engine | Suricata in IDS-oriented mode | Deep packet and signature inspection for threat visibility |
| Firewall Management API | OPNsense REST endpoints (alias, reconfigure, diagnostics) | Allows programmatic policy updates and operational introspection |
| Control Service | FastAPI application in control-api/app.py | Exposes control endpoints, orchestrates alias updates, serves telemetry summaries |
| Reliability Layer | Alias inventory retry logic, UUID overrides, UUID and alias caches, persisted state file | Reduces intermittent API fragility and preserves deterministic updates |
| Telemetry Transport | OPNsense log forwarding plus rsyslog on Ubuntu | Collects pf filterlog and Suricata telemetry streams |
| Data Engineering | Python parsers and feature pipeline in ml/ | Normalizes logs into feature schema for downstream analytics |
| ML Analytics | scikit-learn Isolation Forest workflow plus model artifacts | Produces anomaly-only scoring for validation analysis |
| Attack Simulation | Kali Linux scenario scripts in kali-scenarios/ (Podman-driven workloads) | Generates controlled adversarial traffic with known intent |
| Visualization and Operations UI | dashboard single-page interface plus API-backed status views | Presents policy state, telemetry, and validation outcomes |
| Artifacts and Evidence | diagnostics/, report/, generated CSV and model files | Captures proof, repeatability evidence, and interpretation context |

## Architecture

The system is intentionally separated into four planes.

| Plane | Main Components | Purpose |
| --- | --- | --- |
| Control and Data Plane | OPNsense, pf | Stateful packet filtering, rule ordering, alias resolution, default-deny enforcement |
| Detection Plane | Suricata (IDS mode) | Signature-based application-layer inspection and alert generation |
| Telemetry and Analytics Plane | Ubuntu, rsyslog, Python ML pipeline | Dual-stream ingestion, normalization, feature extraction, anomaly scoring |
| Adversarial Plane | Kali scenarios in Podman | Controlled attack generation and ground-truth traffic injection |

### Detailed Lab Topology (Logical)

- Kali on OPT1 network: 192.168.60.x
- Ubuntu target on LAN: 192.168.50.10
- OPNsense interfaces: em2 (OPT1), em1 (LAN), em0 (WAN)

```text
                                    Management and Operator Plane
                          +-----------------------------------------------+
                          | Browser Dashboard and API Clients             |
                          | - View telemetry and control state            |
                          | - Trigger control actions                     |
                          +------------------------+----------------------+
                                                   |
                                                   | HTTP(S)
                                                   v
                          +-----------------------------------------------+
                          | Ubuntu Control and Analytics Host             |
                          | - FastAPI control-api                         |
                          | - Alias reliability logic and state           |
                          | - rsyslog telemetry collector                 |
                          | - ML parse/train/infer pipeline               |
                          +------------------------+----------------------+
                                                   |
                                                   | HTTPS REST (OPNsense API)
                                                   v
+-----------------------------+    em2/OPT1    +-----------------------------+    em1/LAN    +--------------------------+
| Kali Adversarial Node(s)    |  ----------->  | OPNsense Firewall            |  -----------> | Ubuntu Target Workload   |
| - Scenario scripts           |                | - pf rule engine             |               | - Service endpoint(s)    |
| - Controlled malicious flows |                | - Alias table resolution     |               | - Validation target      |
| - Source: 192.168.60.x       |  <-----------  | - Suricata IDS inspection    |  <----------- | - Host: 192.168.50.10    |
+-----------------------------+   stateful rtn +-----------------------------+   stateful rtn +--------------------------+
                                                   |
                                                   | em0/WAN
                                                   v
                                          Upstream network edge
```

### Architecture of Control Operations

The control path is intentionally strict about alias type, UUID identity, and apply behavior.

```text
Client
  |
  | POST /kali/network or ban/unban endpoint
  v
FastAPI control layer (control-api/app.py)
  |
  +--> Validate request and business constraints
  |
  +--> Resolve alias UUID using deterministic fallback chain
  |      1) OPNSENSE_*_ALIAS_UUID override (if present)
  |      2) Live alias inventory call (retry up to 3 times)
  |      3) In-memory alias_entry_cache and alias_uuid_cache
  |      4) Persisted UUID seed from state file (for Kali alias continuity)
  |
  +--> Update Host(s) alias content with set/setItem-compatible path
  |
  +--> Trigger OPNsense alias reconfigure/apply
  |
  +--> Persist resulting network and UUID metadata for continuity
  |
  +--> Return response with diagnostic context (uuid source, alias path, status)
```

### Telemetry and Analytics Pipeline Architecture

```text
                +------------------+                +------------------+
                | pf filterlog     |                | Suricata alerts  |
                | (network control)|                | (detection layer)|
                +---------+--------+                +---------+--------+
                          |                                   |
                          +---------------+-------------------+
                                          |
                                          v
                               +---------------------+
                               | rsyslog ingestion   |
                               | on Ubuntu host      |
                               +----------+----------+
                                          |
                                          v
                               +---------------------+
                               | Parser and schema   |
                               | timestamp           |
                               | event_source        |
                               | src_ip, dst_ip      |
                               | src_port, dst_port  |
                               | proto, action       |
                               | direction, label    |
                               +----------+----------+
                                          |
                         +----------------+----------------+
                         |                                 |
                         v                                 v
              +-----------------------+         +-----------------------+
              | train.py              |         | infer.py              |
              | Isolation Forest fit  |         | Anomaly scoring       |
              | with preprocessor     |         | against trained model |
              +-----------+-----------+         +-----------+-----------+
                          |                                 |
                          +---------------+-----------------+
                                          |
                                          v
                               +---------------------+
                               | API and dashboard   |
                               | telemetry views     |
                               | validation evidence |
                               +---------------------+
```

### End-to-End Runtime Sequence (Control to Enforcement)

```text
Operator -> Dashboard -> Control API -> OPNsense API -> Alias Update -> Reconfigure
   ^                                                                  |
   |                                                                  v
   +-------------------------- Status/Diagnostics <-------------------+

Traffic Generator (Kali) -> pf Rules/States -> Suricata IDS -> Logs -> Analytics -> Dashboard
```

## Why the Project Shifted from Product Thinking to Validation Thinking

Commercial security tools hide major internals behind proprietary interfaces. That can obscure whether controls are genuinely effective.

This project externalizes those internals so policy, detection, and telemetry behavior can be observed directly. The shift to validation-first engineering is deliberate and academically stronger for several reasons.

1. Ground-truth alignment: each observed alert can be traced to known scenario activity.
2. Dual-source telemetry realism: pf filterlog and Suricata alerts represent different layers and must be reconciled.
3. Policy propagation reality: alias updates, reload timing, and state handling are measured as part of control validity.
4. Evaluation integrity: detection quality is prioritized before aggressive autonomous response loops.

## End-to-End Data and Control Flow

1. Kali scenarios generate controlled adversarial traffic with known intent and timing.
2. pf evaluates ordered rules, alias membership, and connection state.
3. Allowed flows continue and are inspected by Suricata, while denied flows remain visible in filterlog.
4. OPNsense emits control and detection telemetry toward Ubuntu ingestion.
5. rsyslog and parser components normalize events into a stable, analysis-ready schema.
6. The ML workflow performs anomaly-only scoring to characterize unusual behavior patterns.
7. The control API exposes operational controls and telemetry endpoints with diagnostic context.
8. The dashboard consolidates control state, telemetry summaries, and model output for validation decisions.

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
