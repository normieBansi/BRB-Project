# NGFW Lab Project Reference for LLMs

## 1. Document Goal

This file is the canonical handoff reference for AI coding agents and developers.

It is written to let a new agent:

- understand the architecture quickly,
- make safe changes without breaking lab assumptions,
- know where to edit when adding features,
- validate changes with practical checks.

Use this file as the first read before touching code.

## 2. Project Summary

This repository implements a segmented firewall lab control platform with these major parts:

- FastAPI control API for orchestration and telemetry aggregation,
- static dashboard UI (single HTML file) for control, telemetry, and ML views,
- Kali attack scripts executed inside a Podman container,
- OPNsense REST alias automation for ban/unban and source-host sync,
- optional ML pipeline for anomaly and class predictions.

Primary lab intent:

- Red team can launch controlled attack scenarios.
- Blue team can observe telemetry and apply containment.
- Firewall behavior and alerts are measurable and reproducible.

## 3. Runtime Topology and Network Model

### 3.1 Infrastructure roles

- Windows host runs VirtualBox VMs.
- OPNsense VM is the firewall and IDS/IPS platform.
- Debian VM is the control plane host.
- Kali and Ubuntu containers run inside Debian via Podman.

### 3.2 Addressing conventions

- LAN (blue): `192.168.50.0/24`
- OPT1 (red): `192.168.60.0/24`
- OPNsense LAN: `192.168.50.1`
- OPNsense OPT1: `192.168.60.1`
- Ubuntu target default: `192.168.50.10`
- Kali source default: `192.168.60.10`

### 3.3 Data and control flow

- Dashboard sends authenticated HTTP requests to FastAPI.
- FastAPI launches/stops scripts in `kali-lab` using `sudo podman exec`.
- FastAPI reads OPNsense log file and computes telemetry outputs.
- FastAPI ban/unban calls OPNsense `alias_util` REST endpoints.
- FastAPI can reassign Kali IP and sync `KALI_HOST` alias in OPNsense.
- Dashboard renders live state, telemetry charts, ban windows, and ML outputs.

## 4. Repository Structure (Practical Map)

Core files and folders:

- `control-api/app.py`
- `control-api/requirements.txt`
- `control-api/scripts/debian_smoke_test.sh`
- `dashboard/index.html`
- `kali-scenarios/*.sh`
- `kali-scenarios/trex-profiles/*`
- `ml/parse_logs.py`
- `ml/train.py`
- `ml/infer.py`
- `ml/requirements.txt`
- `NGFW_Theory_to_Action_Guide.md`
- `OPNsense_Click_By_Click_Checklist.md`
- `Ubuntu_Checklist.md`
- `Kali_Checklist.md`
- `OPNsense_Point_By_Point_Tests.md`
- `TRex_3_Level_Setup_Guide.md`
- `diagnostics/*`

Secondary files include reports, notes, and templates.

## 5. Critical Invariants (Do Not Violate)

These constraints are central to project stability.

- Preserve baseline container launch assumptions unless explicitly requested otherwise.
- Keep firewall automation REST-based (do not reintroduce SSH hook path logic).
- Maintain strict separation between mock ban state and live ban state.
- Keep explicit live-mode Apply workflow for API URL/token.
- Keep telemetry timestamp parsing stable and log-derived where possible.
- Keep checklist headings and theory-guide anchors aligned when editing docs.

## 6. Baseline Container Commands (Canonical)

These are treated as baseline operational assumptions in the project docs.

Kali baseline:

```bash
sudo podman run -d --name kali-lab --replace --cap-add=NET_RAW --cap-add=NET_ADMIN --security-opt seccomp=unconfined --network opt1 --ip 192.168.60.10 -v /opt/dev/kali-src:/app kali-lab:custom sleep infinity
```

Ubuntu baseline:

```bash
sudo podman run -d --name ubuntu-lab --replace --cap-add=NET_RAW --cap-add=NET_BIND_SERVICE --network lan1 --ip 192.168.50.10 -v ./10-opnsense.conf:/etc/rsyslog.d/10-opnsense.conf:ro -v ./logs:/var/log -v /opt/dev/ubuntu-src:/app ubuntu-lab:custom rsyslogd -n
```

## 7. Backend Architecture (`control-api/app.py`)

### 7.1 Dependency profile

From `control-api/requirements.txt`:

- `fastapi`
- `uvicorn[standard]`
- `pydantic`

### 7.2 Auth model

- Token header: `X-API-Token`
- Required env var on startup: `API_TOKEN`
- Most routes require auth.
- `/health` is public.

### 7.3 Persistent state files

By default under `state/`:

- `runs.json` for run history and statuses,
- `bans.json` for ban lifecycle records,
- `kali_network.json` for current Kali network metadata,
- `dashboard_actions.log` for JSONL action audit events.

### 7.4 Key environment variables

Required:

- `API_TOKEN`

Execution and lab control:

- `KALI_CONTAINER`
- `KALI_SCENARIOS_DIR`
- `TARGET_DEFAULT`
- `TARGET_PROFILE`
- `SSH_USER`
- `MAX_CONCURRENT_RUNS`
- `KALI_ALLOWED_SUBNET`
- `KALI_INTERFACE`
- `KALI_GATEWAY_IP`
- `KALI_CURRENT_IP`
- `KALI_RESERVED_IPS`

OPNsense REST integration:

- `OPNSENSE_API_BASE_URL`
- `OPNSENSE_API_KEY`
- `OPNSENSE_API_SECRET`
- `OPNSENSE_API_VERIFY_TLS`
- `OPNSENSE_API_TIMEOUT_SECONDS`
- `PODMAN_COMMAND_TIMEOUT_SECONDS`
- `OPNSENSE_BAN_ALIAS_TABLE`
- `OPNSENSE_KALI_ALIAS_TABLE`

Telemetry and CORS:

- `TELEMETRY_LAB_SUBNETS`
- `TELEMETRY_EXCLUDED_IPS`
- `CORS_ALLOWED_ORIGINS`
- `CORS_ALLOW_PRIVATE_NETWORKS`
- `CORS_ALLOW_ORIGIN_REGEX`

ML path variables:

- `ML_RESULTS_PATH`
- `ML_PREDICTIONS_PATH`

### 7.5 Scenario registry

Allowed scenario IDs in backend:

- `tcp_syn_burst`
- `web_scan`
- `ssh_bruteforce_sim`
- `sql_injection_sim`
- `udp_flood`
- `icmp_flood`
- `fin_scan`
- `slow_http`
- `credential_stuffing_http`
- `command_injection_probe`

Each scenario in backend carries metadata used by frontend:

- description,
- category,
- OSI layer,
- severity hint,
- pause support flag.

### 7.6 Run control behavior

- Launch creates UUID `run_id`.
- Process is started with `subprocess.Popen(..., start_new_session=True)`.
- `process_registry` tracks running handles.
- Container-side signals are applied using `pgrep -f run_id` matching.
- Pause/resume supported only for scenarios marked pause-capable.
- Max concurrent run cap enforced by `MAX_CONCURRENT_RUNS`.

### 7.7 Firewall integration behavior

OPNsense alias operations use `alias_util` REST endpoints:

- add address to ban alias for containment,
- delete address from ban alias for release,
- flush and add in Kali alias for source-IP sync.

Integration mode is disabled unless all 3 are set:

- `OPNSENSE_API_BASE_URL`
- `OPNSENSE_API_KEY`
- `OPNSENSE_API_SECRET`

### 7.8 Telemetry parsing and summary

Event parsing extracts:

- timestamp,
- source IP,
- destination IP,
- destination port,
- protocol,
- action,
- signature,
- severity.

Timestamp parsing order:

- RFC3339/RFC5424 datetime token,
- BSD syslog timestamp form,
- fallback to current time only when parse fails.

Severity resolution combines:

- explicit `priority`/`severity` numeric values,
- high-risk and medium-risk keyword sets,
- fallback floor for block/alert actions.

Summary aggregates include:

- total alerts,
- blocked count,
- severity buckets,
- active flows,
- anomalies,
- fixed-size time buckets,
- top source IPs,
- top destination ports.

### 7.9 Backend API routes

Public:

- `GET /health`

Authenticated:

- `GET /config`
- `POST /dashboard/action-log`
- `POST /launch`
- `GET /runs`
- `POST /runs/{run_id}/stop`
- `POST /runs/{run_id}/pause`
- `POST /runs/{run_id}/resume`
- `POST /runs/stop-all`
- `GET /firewall/status`
- `GET /firewall/bans`
- `POST /firewall/hook-test`
- `GET /kali/network`
- `POST /kali/network`
- `POST /firewall/ban`
- `POST /firewall/unban`
- `GET /telemetry/events`
- `GET /telemetry/summary`
- `GET /ml/summary`
- `GET /ml/predictions`

## 8. Frontend Architecture (`dashboard/index.html`)

### 8.1 Stack

- Single HTML document with embedded CSS and JS.
- Chart.js from CDN.
- No build pipeline or module bundler.

### 8.2 UI access and modes

Client-side login overlay credentials:

- username `admin`
- password `rbbd`

Operational modes:

- Mock mode is default and simulates API behavior.
- Live mode requires URL/token + explicit Apply.
- Enter key in URL/token inputs also triggers Apply.

### 8.3 Core UI sections

Control tab:

- Attack catalog with launch/pause/stop controls.
- Run capacity and active runs box.
- Kali IP assignment control.
- Red-team ban watch panel (display only).

Telemetry tab:

- Summary cards.
- Alerts-over-time chart.
- Severity chart.
- Top source and port charts.
- Blue-team containment controls.
- Recent events table.

ML tab:

- Total scored, anomaly rate, top class cards.
- Anomaly trend and class distribution charts.
- Recent predictions table.

### 8.4 Frontend state model

Important JS state objects:

- `runLog`
- `scenarioCatalog`
- `controlConfig`
- `kaliNetworkState`
- `latestBanRows` (live data)
- `mockBanRows` (mock data)
- `releasedBanRows` (fade cache)
- `charts` (Chart.js instances)

### 8.5 Live API contract behavior

- All calls route through `apiFetch()`.
- Headers include token and no-cache directives.
- Action logging posts to `/dashboard/action-log` but never blocks primary actions.
- If live URL/token not applied, control/telemetry/ml render idle status messages.

### 8.6 Ban rendering behavior

- Red panel: visible active bans, no release controls.
- Blue panel: active bans with Release button.
- Released bans fade for ~5 seconds.
- Mock and live ban collections are intentionally separate.

## 9. Scenario Script Catalog (`kali-scenarios`)

- `tcp_syn_burst.sh`: hping3 SYN burst to port 80, nmap SYN fallback.
- `web_scan.sh`: Nikto + suspicious HTTP probes.
- `ssh_bruteforce_sim.sh`: repeated SSH attempts.
- `sql_injection_sim.sh`: sqlmap + SQLi-like requests.
- `udp_flood.sh`: UDP burst, default target port 53.
- `icmp_flood.sh`: ICMP burst.
- `fin_scan.sh`: nmap FIN scan.
- `slow_http.sh`: low-rate socket exhaustion style behavior.
- `credential_stuffing_http.sh`: repeated auth/login abuse.
- `command_injection_probe.sh`: encoded command-injection probe payloads.

Firewall implication:

- baseline policy must account for TCP, UDP (including 53), and ICMP behavior expected by these scripts.

## 10. ML Pipeline Details (`ml/`)

Files:

- `parse_logs.py`: converts raw logs into `features.csv`.
- `train.py`: trains preprocessor + IsolationForest (anomaly-only mode).
- `infer.py`: generates `predictions.json` for dashboard.

Output artifacts typically used by backend endpoints:

- `latest_results.json`
- `predictions.json`

Known caveat:

- ML scripts currently assign current timestamp during parse/infer output, not true event timestamp.

## 11. OPNsense Requirements Snapshot

### 11.1 Alias essentials

Project docs currently rely on aliases such as:

- `KALI_HOST` (Host(s))
- `AUTO_BAN_IPS` (Host(s))
- `UBUNTU_HOST`
- `ICMP_ALLOWED_TARGETS`
- `TEST_TARGET_PORTS` (includes 53)
- `DNS_PORT`

### 11.2 Rule model

Expected policy pattern:

- explicit allow rules for test traffic,
- explicit DNS control to firewall resolver,
- explicit ICMP allowance for intended checks,
- broad unintended egress block lower in rule order,
- dynamic ban block near top.

### 11.3 Logging and IDS

Expected environment supports:

- remote logging to Ubuntu/Debian path,
- Suricata ET Open subset,
- RFC5424-enabled syslog forwarding.

## 12. Developer Workflows

### 12.1 Start backend

Typical flow:

- create venv,
- install `control-api/requirements.txt`,
- export env vars,
- run uvicorn.

Example:

```bash
cd control-api
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
API_TOKEN='replace_me' uvicorn app:app --host 0.0.0.0 --port 5000
```

### 12.2 Start dashboard

Serve `dashboard/` as static files and open browser to the served page.

### 12.3 Run smoke validation

Use:

- `control-api/scripts/debian_smoke_test.sh`

This script validates:

- health/config,
- launch and run controls,
- stop-all cleanup,
- firewall status and optional hook test,
- optional Kali reassign path,
- telemetry and ML endpoint reachability.

## 13. Change Playbooks

### 13.1 Add a scenario safely

- Add script to `kali-scenarios` with `RUN_ID` arg + `TARGET_IP` env support.
- Register scenario in backend `SCENARIOS`.
- Add frontend metadata in `SCEN_DESCS` and `SCEN_META`.
- Validate launch and controls from dashboard.
- Update checklist docs if ports/protocol assumptions changed.

### 13.2 Add backend endpoint safely

- Implement route in `control-api/app.py`.
- Add auth guard unless intentionally public.
- Return robust error details using `HTTPException`.
- Integrate frontend only through `apiFetch()`.
- Update this reference file and related docs.

### 13.3 Add telemetry metric safely

- Compute in backend summary or frontend post-processing.
- Preserve lab-only and excluded-IP semantics.
- Keep chart windows bounded.
- Validate mock and live behavior parity.

### 13.4 Modify containment behavior safely

- Never merge mock and live ban stores.
- Keep red panel display-only.
- Keep blue panel actionable.
- Verify release fade does not rehydrate wrong mode state.

## 14. Validation Checklist Before Merge

- API health endpoint passes.
- Config endpoint returns scenarios and integration metadata.
- One launch + stop flow passes.
- Pause/resume tested for pause-capable scenario.
- Ban/unban validated in live mode when OPNsense is configured.
- Recent telemetry events show stable, non-drifting times.
- Mock mode has no seeded phantom live ban.
- Live mode requires intentional Apply for URL/token.
- UI renders without JS runtime errors.
- Smoke script has no hard failures for enabled capabilities.

## 15. Known Technical Debt

- Backend is monolithic in `control-api/app.py`.
- Frontend is monolithic in `dashboard/index.html`.
- No formal automated test suite for backend/frontend.
- ML timestamp fidelity is simplistic for production-grade analytics.
- Parser quality depends on log text variability.

## 16. Secret and Security Guidance

- Never commit real API tokens or OPNsense credentials.
- Keep secrets in private env files outside shared docs.
- Treat any `api key/` artifacts as sensitive data.
- Keep sudoers permissions as narrow as possible.

## 17. Documentation Sync Rules

When behavior changes, update in this order:

- source code,
- `LLM_Project_Reference.md`,
- operational checklists,
- validation test doc,
- theory guide links if anchors or workflow changed.

## 18. Suggested Agent Bootstrap Prompt

Use this for new LLM sessions:

"Read `LLM_Project_Reference.md` first. Then inspect `control-api/app.py` and `dashboard/index.html`. Preserve container baseline assumptions and mock/live separation. Make smallest safe change, run smoke-level validation, and update runbooks/docs when behavior changes."

## 19. Final Orientation

This project is most reliable when these stay aligned:

- backend API contracts,
- dashboard mode and state handling,
- firewall policy assumptions for scenario traffic.

If you change one pillar, review and validate the other two before finalizing.
# LLM Project Reference: NGFW Lab Automation Platform

## 1. Purpose of This File

This document is a deep technical reference for AI coding agents (and developers) who need to understand and extend this project without re-learning the whole lab from scratch.

Primary goal:
- Enable safe, consistent project development with minimal assumptions.

Secondary goals:
- Preserve important lab invariants.
- Prevent regressions in live firewall automation and dashboard behavior.
- Provide a clear map between theory docs, checklists, code, and runtime behavior.

## 2. What This Project Is

This project is a segmented next-generation firewall (NGFW) lab orchestration platform with:
- A FastAPI control backend.
- A single-page dashboard frontend.
- Kali attack scenario scripts executed in a container.
- OPNsense REST alias integration for ban/unban and source IP sync.
- Telemetry extraction from OPNsense logs.
- Basic ML pipeline (anomaly + classification) for analytics display.

It is designed for a red-team/blue-team lab workflow, not a production SOC platform.

## 3. Topology and Runtime Model

### 3.1 Host and VM model

- Windows host runs VirtualBox VMs.
- OPNsense VM acts as WAN/LAN/OPT1 firewall.
- Debian VM is control plane host.
- Kali and Ubuntu containers run inside Debian using Podman.

### 3.2 Network segments

- Blue network (LAN): `192.168.50.0/24`
- Red network (OPT1): `192.168.60.0/24`
- OPNsense LAN IP: `192.168.50.1`
- OPNsense OPT1 IP: `192.168.60.1`
- Ubuntu target default: `192.168.50.10`
- Kali default source: `192.168.60.10`

### 3.3 Core flow

1. Dashboard sends authenticated requests to FastAPI.
2. FastAPI launches/stops Kali scenario scripts via `sudo podman exec`.
3. FastAPI reads OPNsense logs, parses events, and serves telemetry summaries.
4. FastAPI ban/unban endpoints call OPNsense `alias_util` REST endpoints.
5. FastAPI can reassign Kali source IP inside OPT1 subnet and sync `KALI_HOST` alias.
6. Dashboard shows control state, telemetry, containment state, and ML summaries.

## 4. Repository Map (Authoritative)

Top-level directories and key files:

- `control-api/app.py`
  - Main backend application and all API routes.
- `control-api/requirements.txt`
  - Backend dependencies.
- `control-api/scripts/debian_smoke_test.sh`
  - End-to-end smoke test runner for API control and integration paths.
- `dashboard/index.html`
  - Entire frontend (HTML/CSS/JS in one file).
- `kali-scenarios/*.sh`
  - Attack generators executed inside `kali-lab` container.
- `kali-scenarios/trex-profiles/*`
  - Optional TRex traffic profiles and runner.
- `ml/parse_logs.py`, `ml/train.py`, `ml/infer.py`
  - ML data prep, training, and inference scripts.
- `ml/requirements.txt`
  - ML dependencies.
- `NGFW_Theory_to_Action_Guide.md`
  - Theory-first cross-link guide.
- `OPNsense_Click_By_Click_Checklist.md`
  - Firewall implementation runbook.
- `Ubuntu_Checklist.md`
  - Debian/Ubuntu control-plane runbook.
- `Kali_Checklist.md`
  - Kali attacker-side runbook.
- `OPNsense_Point_By_Point_Tests.md`
  - Validation tests.
- `TRex_3_Level_Setup_Guide.md`
  - TRex setup and staged load testing guide.
- `diagnostics/*`
  - Lab snapshots and service notes.

## 5. Critical Invariants (Do Not Break)

These are project-level guardrails.

1. Original container startup assumptions are considered baseline and should not be changed casually:
   - Kali baseline command includes:
     - `--network opt1 --ip 192.168.60.10`
     - `--cap-add=NET_RAW --cap-add=NET_ADMIN`
     - `--security-opt seccomp=unconfined`
     - `-v /opt/dev/kali-src:/app`
   - Ubuntu baseline command includes:
     - `--network lan1 --ip 192.168.50.10`
     - `--cap-add=NET_RAW --cap-add=NET_BIND_SERVICE`
     - `-v ./10-opnsense.conf:/etc/rsyslog.d/10-opnsense.conf:ro`
     - `-v ./logs:/var/log`
     - `-v /opt/dev/ubuntu-src:/app`
2. Firewall automation is REST-based (`alias_util`) and not SSH hook-script based.
3. Dashboard live mode must not silently call APIs unless URL/token are intentionally applied by user.
4. Mock ban state must remain isolated from live ban state.
5. Telemetry timestamps must parse actual log timestamps where possible.
6. Keep theory-guide anchors and checklist headings stable where possible to avoid broken deep links.

## 6. Backend Deep Dive (`control-api/app.py`)

### 6.1 Dependency profile

From `control-api/requirements.txt`:
- `fastapi`
- `uvicorn[standard]`
- `pydantic`

### 6.2 Authentication model

- Header: `X-API-Token`
- Token source: env var `API_TOKEN`
- Missing startup token causes runtime abort.
- Most routes require auth except `/health`.

### 6.3 State and persistence

Backend state is persisted as JSON files in a state directory (default: `./state`):
- `runs.json` -> run lifecycle records
- `bans.json` -> ban history/status
- `kali_network.json` -> current Kali network assignment metadata
- `dashboard_actions.log` -> JSONL action audit trail

### 6.4 Environment variables (important)

Required:
- `API_TOKEN`

Core optional runtime vars:
- `CONTROL_API_WORK_DIR`
- `CONTROL_API_STATE_DIR`
- `RUN_LOG_PATH`
- `BAN_LOG_PATH`
- `KALI_NETWORK_PATH`
- `OPNSENSE_LOG_PATH`
- `ML_RESULTS_PATH`
- `ML_PREDICTIONS_PATH`
- `DASHBOARD_ACTION_LOG_PATH`

Kali execution vars:
- `KALI_CONTAINER` (default `kali-lab`)
- `KALI_SCENARIOS_DIR` (default `/opt/lab/scenarios`)
- `TARGET_DEFAULT` (default `192.168.50.10`)
- `TARGET_PROFILE` (default `ubuntu-dvwa`)
- `SSH_USER` (default `root`)
- `MAX_CONCURRENT_RUNS` (default `3`)
- `KALI_ALLOWED_SUBNET` (default `192.168.60.0/24`)
- `KALI_INTERFACE` (default `eth0`)
- `KALI_GATEWAY_IP` (default `192.168.60.1`)
- `KALI_CURRENT_IP` (default `192.168.60.10`)
- `KALI_RESERVED_IPS` (default `192.168.60.1,192.168.60.2`)

OPNsense REST vars:
- `OPNSENSE_API_BASE_URL`
- `OPNSENSE_API_KEY`
- `OPNSENSE_API_SECRET`
- `OPNSENSE_API_VERIFY_TLS` (default false)
- `OPNSENSE_API_TIMEOUT_SECONDS` (default 4)
- `PODMAN_COMMAND_TIMEOUT_SECONDS` (default 8)
- `OPNSENSE_BAN_ALIAS_TABLE` (default `AUTO_BAN_IPS`)
- `OPNSENSE_KALI_ALIAS_TABLE` (default `KALI_HOST`)

CORS vars:
- `CORS_ALLOWED_ORIGINS`
- `CORS_ALLOW_PRIVATE_NETWORKS`
- `CORS_ALLOW_ORIGIN_REGEX`

Telemetry vars:
- `TELEMETRY_LAB_SUBNETS` (defaults include LAN and OPT1)
- `TELEMETRY_EXCLUDED_IPS` (defaults exclude infra IPs)

### 6.5 Scenario registry

`SCENARIOS` in backend is canonical for allowed launch IDs and metadata.

Current IDs:
- `tcp_syn_burst`
- `web_scan`
- `ssh_bruteforce_sim`
- `sql_injection_sim`
- `udp_flood`
- `icmp_flood`
- `fin_scan`
- `slow_http`
- `credential_stuffing_http`
- `command_injection_probe`

Each entry includes:
- script name
- description
- category
- osi_layer
- severity_hint
- supports_pause

### 6.6 Process control model

- Launch creates a UUID `run_id`.
- API spawns process using `subprocess.Popen` with `start_new_session=True`.
- Active handles tracked in `process_registry`.
- Additional container-side run signaling uses `pgrep -f run_id` pattern.
- Pause/resume/stop operations update run JSON state and emit action logs.
- Concurrency guard blocks launch when active count reaches max.

### 6.7 OPNsense integration model

REST only, via:
- `/api/firewall/alias_util/add/<alias>`
- `/api/firewall/alias_util/delete/<alias>`
- `/api/firewall/alias_util/flush/<alias>`

Used for:
- Ban add/remove in `AUTO_BAN_IPS` (or configured alias).
- Kali source alias replacement in `KALI_HOST` using flush+add.

### 6.8 Telemetry parsing model

Telemetry is derived from text log lines, not a normalized SIEM index.

Parsing behavior:
- Extract source and destination IPv4 values.
- Parse destination port from common key formats (`dpt`, `dst port`, etc).
- Parse protocol from token or protocol number hints.
- Parse signature from `msg="..."` where available.
- Infer action from keywords (`drop`, `block`, `reject`, `alert`).
- Infer severity using:
  - explicit priority/severity numbers where present
  - keyword heuristics
  - fallback mapping (`block` and `alert` -> at least medium)
- Timestamp extraction attempts:
  - RFC3339/RFC5424 datetime tokens
  - BSD syslog format (`May  6 13:14:15`)
  - fallback to now only if parse fails

### 6.9 ML endpoint contract

- `/ml/summary` reads JSON from `latest_results.json`.
- `/ml/predictions` reads JSON list from `predictions.json` and slices by limit.
- Backend does not train models itself; external scripts populate files.

### 6.10 API endpoint list

Public:
- `GET /health`

Authenticated:
- `GET /config`
- `POST /dashboard/action-log`
- `POST /launch`
- `GET /runs`
- `POST /runs/{run_id}/stop`
- `POST /runs/{run_id}/pause`
- `POST /runs/{run_id}/resume`
- `POST /runs/stop-all`
- `GET /firewall/status`
- `GET /firewall/bans`
- `POST /firewall/hook-test`
- `GET /kali/network`
- `POST /kali/network`
- `POST /firewall/ban`
- `POST /firewall/unban`
- `GET /telemetry/events`
- `GET /telemetry/summary`
- `GET /ml/summary`
- `GET /ml/predictions`

## 7. Frontend Deep Dive (`dashboard/index.html`)

### 7.1 Stack and shape

- Single static HTML file.
- No framework build system.
- CSS + JS embedded inline.
- Chart.js loaded from CDN.

### 7.2 Access control

- Client-side login overlay only:
  - username: `admin`
  - password: `rbbd`
- This is UI gating, not security boundary.

### 7.3 Global modes

- Mock mode (default):
  - API calls are simulated.
  - bans are stored in `mockBanRows` only.
- Live mode:
  - requires URL and token.
  - user explicitly applies settings using Apply button or Enter key.
  - if missing URL/token, API calls are intentionally gated with idle status messages.

### 7.4 Major UI modules

Control tab:
- Attack catalog table with launch, pause, stop controls.
- Active/recent run log.
- Kali IP reassignment control.
- Red team ban watch panel (display only).

Telemetry tab:
- Summary cards.
- Events timeline.
- Packet/protocol distribution.
- Top sources and destination ports.
- Blue team containment controls (ban/unban).
- Recent events table.

ML tab:
- Summary cards.
- Anomaly trend chart.
- Observed protocol distribution (parsed features).
- Recent prediction table.

### 7.5 Frontend state and behavior details

Core state variables:
- `runLog`
- `scenarioCatalog`
- `controlConfig`
- `kaliNetworkState`
- `latestBanRows` (live)
- `mockBanRows` (mock)
- `releasedBanRows` (transient fade map)
- `charts` (Chart.js handles)

Behavior notes:
- Refresh interval is user-configurable.
- Active tab drives which periodic refresh runs.
- `fmtTime()` renders full locale date+time for stable event visibility.
- Red ban panel has no release controls.
- Blue ban panel has release controls.
- Released entries fade for ~5 seconds.

### 7.6 Frontend API integration contract

All live API requests go through `apiFetch()` with:
- `X-API-Token` header
- `Content-Type: application/json`
- no-cache headers

Action logging:
- Most control actions send async log entries to `/dashboard/action-log`.
- Logging failures do not block main workflows.

## 8. Scenario Script Catalog (`kali-scenarios`)

Current scripts and behavior:

1. `tcp_syn_burst.sh`
- Sends 500 SYN packets to target port 80 using hping3.
- Fallback to nmap SYN scan if hping3 path fails.

2. `web_scan.sh`
- Runs Nikto HTTP scan.
- Sends SQLi/traversal-like curl payloads.

3. `ssh_bruteforce_sim.sh`
- 25 SSH attempts with short timeout.

4. `sql_injection_sim.sh`
- Runs sqlmap with constrained settings.
- Sends SQLi-like curl requests.

5. `udp_flood.sh`
- Sends 300 UDP packets.
- Default target port is 53 (`TARGET_PORT` override supported).

6. `icmp_flood.sh`
- Sends 200 ICMP packets.

7. `fin_scan.sh`
- nmap FIN scan of ports 1-1000.

8. `slow_http.sh`
- Python socket script that opens and drips HTTP headers to stress connection handling.

9. `credential_stuffing_http.sh`
- Basic auth and POST login abuse loops.

10. `command_injection_probe.sh`
- URL/POST payload probes with common command injection encodings.

Implication for firewall policy:
- Must account for TCP, UDP (including 53), and ICMP paths as intended by lab design.

## 9. ML Pipeline (`ml/`)

### 9.1 Files and outputs

- `parse_logs.py` -> reads log lines and writes `features.csv`.
- `train.py` -> trains models and writes:
  - `preprocessor.joblib`
  - `isolation_forest.joblib`
  - `latest_results.json`
- `infer.py` -> reads features/models and writes `predictions.json`.

Current parser defaults:
- Parses `filterlog` lines by default for ML.
- Includes Suricata lines only when `--include-suricata` is provided.
- Keeps lab-related (`192.168.*`) traffic by default unless `--all-events` is provided.

### 9.2 Current modeling approach

- Anomaly: IsolationForest.
- Classification: none (anomaly-only mode).
- Feature engineering:
  - categorical: event_source, source/destination IP, proto, action, signature, rule_label, direction
  - numeric: destination port, priority

### 9.3 Important caveat

Inference preserves parsed row timestamps when available; if missing, current UTC time is used as fallback.

## 10. OPNsense Integration Requirements

### 10.1 Alias requirements

Required aliases include:
- `KALI_HOST` (External advanced)
- `AUTO_BAN_IPS` (External advanced)
- `UBUNTU_HOST`
- `LAB_NET_RED`
- `LAB_NET_BLUE`
- `FIREWALL_LAN_IP`
- `FIREWALL_OPT1_IP`
- `ICMP_ALLOWED_TARGETS`
- `TEST_TARGET_PORTS` (includes 53)
- `OPSENSE_INFRA_PORTS`
- `DNS_PORT`

### 10.2 Rule semantics

Core idea:
- explicit allows for expected test traffic
- explicit DNS control
- explicit ICMP allowance where needed for tests
- broad unintended egress block below specific allows

### 10.3 Logging and IDS

- RFC5424 remote logging to Ubuntu/Debian path expected.
- Suricata should start in IDS before IPS tuning.
- ET Open subset is used to reduce noise.

## 11. Operations and Developer Quick Start

### 11.1 Backend start (example)

1. Create venv and install backend deps from `control-api/requirements.txt`.
2. Export env vars (minimum API token + OPNsense vars for live firewall automation).
3. Run Uvicorn on port 5000:

`uvicorn app:app --host 0.0.0.0 --port 5000`

### 11.2 Dashboard start

Serve `dashboard/` as static files (for example via Python http.server), then open in browser.

### 11.3 Smoke test

Use:
- `control-api/scripts/debian_smoke_test.sh`

It validates:
- health/config/runs
- launch + run controls
- stop-all cleanup
- firewall status/hook test (if integration enabled)
- optional Kali reassign/restore
- telemetry summary and ml summary availability

## 12. Extension Playbooks

### 12.1 Add a new attack scenario

1. Add script in `kali-scenarios/`.
2. Ensure script accepts `RUN_ID` as arg and uses `TARGET_IP` env.
3. Add executable permissions in deployment process.
4. Register scenario entry in backend `SCENARIOS` map.
5. Add frontend description/meta in `SCEN_DESCS` and `SCEN_META`.
6. Validate via `/config`, launch from UI, and smoke test.
7. Update checklist and theory docs if behavior changes expected firewall paths.

### 12.2 Add a new API endpoint

1. Implement route in `control-api/app.py`.
2. Enforce auth with `require_auth` unless intentionally public.
3. Add robust HTTPException messages.
4. Add or update frontend integration if needed.
5. Update this reference file and checklists if operator workflow changes.

### 12.3 Add a telemetry metric

1. Decide metric source in backend summary or frontend post-processing.
2. Preserve lab-only and excluded-IP behavior.
3. Keep chart windows bounded to avoid UI degradation.
4. Validate in both mock and live modes.

### 12.4 Modify ban behavior

1. Preserve separation between mock and live ban arrays.
2. Keep red panel display-only and blue panel actionable.
3. Keep release fade behavior deterministic.
4. Validate no cross-mode state leakage.

## 13. Validation Checklist for Changes

Before merging significant changes:

1. `GET /health` returns OK.
2. `GET /config` returns scenario metadata and integration flags.
3. Launch one scenario and stop it.
4. If pause-enabled scenario: pause/resume test.
5. Ban/unban test in live mode (if OPNsense configured).
6. Telemetry recent events show stable timestamps.
7. Mock mode starts with no phantom live bans.
8. Live mode requires explicit URL/token apply.
9. Dashboard still renders all charts/tables without JS errors.
10. Smoke test script finishes without failures for enabled features.

## 14. Known Technical Debt and Improvement Opportunities

1. Backend currently in one large module (`control-api/app.py`):
   - candidate split: auth, state, scenarios, firewall client, telemetry parser, routes.
2. Frontend in one large file:
   - candidate split: API client, state store, control module, telemetry module, ML module, UI helpers.
3. ML timestamp fidelity:
   - preserve event timestamps from parsed log lines.
4. Telemetry parser robustness:
   - consider structured syslog ingestion and parser tests.
5. Test coverage:
   - add backend unit/integration tests and frontend behavior tests.

## 15. Security and Secrets Guidance

1. Never commit real API keys/secrets/tokens.
2. Keep OPNsense credentials in private env files outside versioned docs.
3. Treat `api key/` directory as sensitive and avoid sharing raw credential artifacts.
4. Use least privilege for sudoers rules (narrow command allowance).

## 16. Documentation Sync Rules

When code changes, update docs in this order:

1. Source code (`control-api` and/or `dashboard`).
2. This file (`LLM_Project_Reference.md`).
3. Operational checklists:
   - `OPNsense_Click_By_Click_Checklist.md`
   - `Ubuntu_Checklist.md`
   - `Kali_Checklist.md`
4. Test reference:
   - `OPNsense_Point_By_Point_Tests.md`
5. Theory map:
   - `NGFW_Theory_to_Action_Guide.md` if anchor links or workflow changed.

## 17. Agent Handoff Prompt Seed (Optional)

Use the following prompt skeleton for another LLM working on this repo:

"Read `LLM_Project_Reference.md` first, then inspect `control-api/app.py` and `dashboard/index.html`. Preserve container startup invariants and mock/live separation rules. Make smallest safe change, update checklists if behavior changes, and run smoke-level validation before finalizing."

## 18. Summary

This project is stable when these three pillars stay aligned:
- Backend API contracts and state behavior.
- Dashboard mode handling and operator UX.
- Firewall policy and scenario traffic assumptions.

If a change touches any one pillar, validate and document the other two explicitly.
