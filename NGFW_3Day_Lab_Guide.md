# NGFW + AI + TRex Lab Runbook (3 Days, Zero Cost)

## 1) Goal and Scope

Build a practical, no-cost NGFW lab using your existing topology:

- Kali (traffic/attack simulation source): 192.168.60.10
- Ubuntu (target + SIEM + ML + orchestration): 192.168.50.10
- OPNsense firewall:
  - LAN: 192.168.50.1
  - OPT1: 192.168.60.1
  - WAN: dynamic

Desired outcomes:

1. OPNsense enforces segmented policy with least privilege.
2. Suricata runs in IDS/IPS mode and catches known malicious patterns.
3. Firewall and IDS telemetry are centralized in a dashboard.
4. Ubuntu trains and runs:
   - Isolation Forest for anomaly scoring.
   - Random Forest for attack class prediction.
5. TRex is used for controlled traffic generation and stress validation.
6. Optional internet access to dashboard/control endpoint is enabled safely at no cost.

Boundaries:

- Lab use only.
- Keep traffic contained to owned systems.
- Do not target internet hosts.

---

## 2) Architecture and Technical Rationale

Why this split works:

1. OPNsense is good at real-time packet policy, state tracking, and inline inspection.
2. Ubuntu is better for heavier analytics and model inference because ML can consume CPU/RAM.
3. Keeping ML off the firewall preserves forwarding and inspection performance.

Practical NGFW mapping in this lab:

- L3/L4 control: OPNsense stateful firewall rules.
- L7-ish signature detection: Suricata ET Open rules.
- Threat intelligence: aliases/blocklists and DNS policy.
- Visibility: syslog + SIEM.
- Adaptive analytics: ML scoring pipeline on Ubuntu.

Data path:

1. Kali traffic enters OPT1.
2. OPNsense applies interface rules, then Suricata checks packet/flow signatures.
3. Allowed traffic reaches Ubuntu services on LAN.
4. OPNsense + Suricata events are forwarded to Ubuntu SIEM.
5. ML job consumes normalized events and writes scores back to dashboard index.

---

## 3) Success Criteria (What "Done" Looks Like)

By end of Day 3, validate all of these:

1. Segmentation: Kali reaches only explicitly allowed Ubuntu ports.
2. Detection: at least 3 scenario types generate Suricata alerts.
3. SIEM: real-time event stream with source/destination/port dimensions.
4. ML: anomaly scores visible and supervised labels predicted with report metrics.
5. Load test: TRex run visible in firewall counters, Suricata alerts, and dashboard timelines.
6. Optional remote view: dashboard/API reachable through authenticated tunnel only.

---

## 4) Before You Start (30-Min Preflight)

### 4.1 VirtualBox and VM Resource Baseline

Set minimum practical resources:

1. OPNsense VM: 2 vCPU, 4 GB RAM.
2. Ubuntu VM: 4 vCPU, 8 GB RAM (recommended for SIEM + ML).
3. Ensure Intel VT-x/AMD-V is enabled in BIOS/UEFI.

Why: Suricata and indexing are CPU-sensitive. Under-provisioning causes false troubleshooting paths.

### 4.2 Interface Assignment Sanity Check

On each VM, confirm IP settings:

1. Kali default gateway = 192.168.60.1
2. Ubuntu default gateway = 192.168.50.1
3. OPNsense LAN/OPT1 are assigned and active.

Quick verification commands:

```bash
ip a
ip route
ping -c 2 192.168.60.1
ping -c 2 192.168.50.1
```

Expected: each host reaches only its own interface gateway at this stage.

### 4.3 Snapshot Strategy

Take VM snapshots at milestones:

1. Snapshot A: clean network baseline.
2. Snapshot B: after Day 1 firewall + Suricata setup.
3. Snapshot C: after Day 2 SIEM/dashboard working.

Why: fastest rollback when troubleshooting breaks multiple layers.

---

## Day 1: OPNsense NGFW Baseline and Validation

## 5) OPNsense Foundation (with explicit actions)

### 5.1 Update and Base Security

In OPNsense Web UI:

1. Go to System > Firmware > Updates.
2. Install updates and reboot if requested.
3. Go to System > Settings > General:
   - set timezone.
   - ensure NTP servers are reachable.
4. Go to System > Access > Administration:
   - disable web GUI from untrusted interfaces.
   - if using SSH, allow key auth and disable password auth where possible.

Why: consistent time is required for event correlation across firewall, SIEM, and ML labels.

### 5.2 Create Network Aliases (Do this first)

Go to Firewall > Aliases and add:

1. KALI_HOST = 192.168.60.10
2. UBUNTU_HOST = 192.168.50.10
3. LAB_NET_RED = 192.168.60.0/24
4. LAB_NET_BLUE = 192.168.50.0/24
5. Optional HOST_LAN_NET = your physical host LAN CIDR

Why: aliases reduce rule mistakes and make policy readable.

### 5.3 Policy Design Rules (Order Matters)

Packet filtering on OPNsense is top-down first-match per interface.

Important behavior:

1. If a broad allow appears above a specific block, the block never hits.
2. Floating rules can override per-interface expectations if quick is enabled.

Recommendation: use interface rules first, avoid floating rules in this 3-day lab unless required.

### 5.4 OPT1 (Kali-side) Rules

Go to Firewall > Rules > OPT1 and create in this order:

1. Allow test traffic:
   - source: KALI_HOST
   - destination: UBUNTU_HOST
   - destination ports: create alias TEST_TARGET_PORTS (22, 80, 443, 5000, 8080 as needed)
   - log: enabled
2. Block Kali to WAN net:
   - source: KALI_HOST
   - destination: any
   - destination invert for RFC1918 optional depending policy
   - log: enabled
3. Block Kali to host LAN/networks:
   - source: KALI_HOST
   - destination: HOST_LAN_NET
   - log: enabled

Why this order: explicit allow to target services, then hard blocks for unintended egress.

### 5.5 LAN (Ubuntu-side) Rules

Go to Firewall > Rules > LAN and set:

1. Allow Ubuntu to OPNsense infra services as required:
   - DNS to firewall (53), NTP (123), syslog/API if needed.
2. Allow Ubuntu outbound only where needed:
   - package update endpoints and tunnel endpoint.
   - use FQDN aliases if possible.
3. Block unnecessary lateral/internal movement.

Why: Ubuntu is your analytics hub; give only operational egress.

### 5.6 NAT and Outbound Behavior

Go to Firewall > NAT > Outbound:

1. Keep Automatic or Hybrid mode initially.
2. Do not add broad outbound NAT exceptions on day 1.
3. Avoid inbound port forwards until day 2 tunnel path is ready.

Why: broad NAT rules make troubleshooting harder and can accidentally expose services.

### 5.7 Day 1 Connectivity Validation

From Kali:

```bash
nc -zv 192.168.50.10 80
nc -zv 192.168.50.10 22
nc -zv 192.168.50.10 3306
curl -m 5 http://192.168.50.10
```

Expected:

1. Allowed ports connect.
2. Disallowed ports fail or timeout.

Internet egress check from Kali:

```bash
curl -m 5 https://example.com
```

Expected: fail (blocked).

In OPNsense logs:

1. Firewall > Log Files > Live View.
2. Filter by source 192.168.60.10.
3. Confirm both pass and block entries for your tests.

---

## 6) Suricata IDS/IPS Setup (Detailed)

### 6.1 Enable and Attach Interfaces

1. Install plugin if not present.
2. Services > Intrusion Detection > Administration:
   - enable IDS.
   - add LAN and OPT1 interfaces.
3. Enable Promiscuous mode where needed by driver/VM NIC behavior.

Why: if the interface is not selected, no traffic is inspected there.

### 6.2 Rulesets and Home Net

1. Services > Intrusion Detection > Download:
   - enable ET Open rules.
2. Services > Intrusion Detection > Policy:
   - start with balanced policy.
   - disable very noisy categories initially.
3. Set HOME_NET to both subnets:
   - 192.168.50.0/24,192.168.60.0/24

Why: Home net influences how signatures classify internal/external roles.

### 6.3 IDS vs IPS Mode

1. Start in IDS (alert only) for 15-30 minutes.
2. Verify expected alerts appear.
3. Switch to IPS inline mode and verify allowed traffic is still functional.

Why: staging prevents accidental traffic blackouts due to false positives.

### 6.4 Suricata Validation

Generate known trigger traffic from Kali against Ubuntu test app.

Check:

1. Services > Intrusion Detection > Alerts.
2. Suricata logs include signature ID and source/destination.
3. In IPS mode, blocked events are marked as drop/reject when applicable.

---

## 7) DNS Control and Blocklists

### 7.1 Unbound Setup

1. Services > Unbound DNS > General:
   - enable Unbound.
   - bind to LAN and OPT1.
2. Force clients to use firewall DNS:
   - allow DNS to firewall.
   - block outbound DNS from clients to other destinations.

Why: DNS egress control is foundational for NGFW policy observability.

### 7.2 Blocklist Strategy

1. Start with conservative feeds.
2. Enable logging for DNS blocks.
3. Maintain allowlist for false positives.

Why: aggressive feeds create noise and break expected traffic in small labs.

---

## Day 2: SIEM, Dashboard, Safe Remote Access

## 8) Ubuntu Platform Setup

### 8.1 Base Packages

```bash
sudo apt update && sudo apt -y upgrade
sudo apt -y install podman podman-compose python3 python3-venv python3-pip git jq curl rsyslog
```

Why: this gives container runtime, Python stack, and syslog receiver support.

### 8.2 Project Layout

```bash
mkdir -p ~/lab/{siem,collector,ml,control-api,trex,data,scenarios}
```

Recommended purpose:

1. siem: compose files and dashboard config.
2. collector: parsers/transforms.
3. ml: feature extraction, training, inference scripts.
4. control-api: safe scenario launcher service.
5. trex: traffic profiles and notes.

### 8.3 Choose SIEM Path

For 3-day speed, prefer Wazuh all-in-one.

Technical reason:

1. Faster to deploy than hand-rolling OpenSearch ingest pipelines.
2. Includes dashboard + indexing + basic security controls.

If resource limits block Wazuh, switch to lighter OpenSearch + Dashboards + Vector/Filebeat.

---

## 9) OPNsense Log Forwarding to Ubuntu

### 9.1 Receiver on Ubuntu

Configure rsyslog UDP/TCP listener (example ports 514/5514), then restart rsyslog.

Quick check:

```bash
sudo ss -lunpt | grep -E '514|5514'
```

Expected: listener sockets active.

### 9.2 OPNsense Remote Syslog

1. System > Settings > Logging / Targets.
2. Add remote target = Ubuntu IP.
3. Enable facility categories:
   - firewall
   - system
   - IDS/Suricata

### 9.3 Validation

On Ubuntu:

```bash
sudo tcpdump -ni any port 514 or port 5514
```

Expected: packets arriving from OPNsense.

Then verify SIEM index receives parsed events.

---

## 10) Dashboard with Two Required Sections

## 10.1 Section A: Attack Control

Design objective: controlled orchestration, not arbitrary command execution.

Required widgets:

1. Scenario selector with allowlisted scenario IDs.
2. Start button triggers control API /launch.
3. Run metadata panel: run_id, start time, status, duration.
4. Safety controls:
   - max concurrent jobs
   - max duration per job

### 10.2 Section B: Security Telemetry

Required widgets:

1. Live event table (firewall + Suricata + model results).
2. Alerts by severity over time.
3. Top sources and destinations.
4. Destination port distribution.
5. Bytes/packets time series.
6. Signature frequency chart.
7. ML charts:
   - anomaly score trend
   - predicted class distribution

Why this split: it lets you correlate "what was launched" with "what was detected" in one view.

---

## 11) Safe Internet Exposure at Zero Cost

### 11.1 Tunnel Choice

Use one:

1. Cloudflare Tunnel (free tier)
2. Ngrok free tier

### 11.2 Exposure Rules

Expose only:

1. dashboard endpoint
2. control API endpoint

Do not expose:

1. Kali host
2. raw SIEM internal ports
3. unauthenticated service endpoints

### 11.3 Hardening Controls

1. Require auth at tunnel edge and API.
2. Restrict API methods to predefined scenario names.
3. Add simple rate limit (for example 5 requests/min per token/IP).
4. Log all launch requests with run_id and requester identity.

---

## Day 3: AI Models + TRex Relearning + Demo

## 12) ML Data Engineering Pipeline

### 12.1 Source Data

Primary sources:

1. Suricata EVE/alerts.
2. OPNsense firewall logs.
3. Scenario run metadata (run_id, scenario, expected class).

Add run_id to generated traffic events when possible so labels are easy.

### 12.2 Feature Schema (Starter)

Use these fields:

1. src_ip, dst_ip
2. src_port, dst_port
3. proto
4. flow_duration_ms
5. packets, bytes
6. tcp_flags
7. alert_signature_id, alert_severity
8. hour_of_day, day_of_week
9. inter_arrival_ms

Technical note: do not feed raw IP strings directly to model without encoding strategy.

### 12.3 Preprocessing Steps

1. Impute missing values (median for numeric, unknown for categorical).
2. Encode categorical values (one-hot or ordinal where stable).
3. Scale numeric features for anomaly model.
4. Keep train/test split by time windows to reduce leakage.

Why: random splitting mixed with near-identical flows can overstate model quality.

### 12.4 Isolation Forest Workflow

1. Train primarily on benign baseline period.
2. Start contamination in 0.02 to 0.08 range.
3. Publish:
   - anomaly_score (continuous)
   - anomaly_flag (binary)

Tune contamination based on false positive rate in your dashboard.

### 12.5 Random Forest Workflow

Labels:

1. benign
2. scan
3. brute_force
4. web_attack
5. flood

Train:

1. class_weight=balanced
2. n_estimators around 300
3. max_depth between 12 and 20

Report metrics:

1. precision/recall/F1 by class
2. confusion matrix
3. feature importances

If one class dominates, rebalance by undersampling benign or weighting classes.

---

## 13) TRex Relearning and Integration

### 13.1 What TRex Adds Here

TRex gives repeatable, scriptable traffic bursts so you can:

1. stress test policy and telemetry pipelines.
2. generate controlled labeled samples for ML.
3. validate dashboard behavior under concurrent events.

### 13.2 Relearning Sequence (Hands-on)

1. Start with stateless profiles at low PPS.
2. Validate packet path and counters before increasing rates.
3. Run short bursts (30-90 seconds) and log run_id.
4. Increment PPS gradually and observe dropped packets, VM CPU, alert lag.

If VirtualBox limits throughput:

1. lower PPS.
2. shorten profile duration.
3. reduce concurrent scenario count.

### 13.3 Correlation Checklist per TRex Run

For each run_id capture:

1. TRex start/end and profile name.
2. OPNsense live session/traffic counters during run.
3. Suricata alert count and signature mix.
4. SIEM ingest rate and delay.
5. ML anomaly/class outputs.

This gives clean evidence for final demo and model validation.

---

## 14) Implementation Cookbook (Updated)

### 14.1 Python Environment for ML

```bash
cd ~/lab/ml
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install pandas numpy scikit-learn matplotlib seaborn fastapi uvicorn[standard] joblib pydantic pyarrow
```

### 14.2 Training Script Skeleton

```python
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.impute import SimpleImputer
from sklearn.ensemble import IsolationForest, RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report
import joblib

df = pd.read_csv("features.csv")

target_col = "label" if "label" in df.columns else None
feature_cols = [c for c in df.columns if c != target_col]
X = df[feature_cols]

num_cols = X.select_dtypes(include=["number"]).columns.tolist()
cat_cols = [c for c in X.columns if c not in num_cols]

pre = ColumnTransformer(
    transformers=[
        (
            "num",
            Pipeline([
                ("impute", SimpleImputer(strategy="median")),
                ("scale", StandardScaler()),
            ]),
            num_cols,
        ),
        (
            "cat",
            Pipeline([
                ("impute", SimpleImputer(strategy="most_frequent")),
                ("oh", OneHotEncoder(handle_unknown="ignore")),
            ]),
            cat_cols,
        ),
    ]
)

X_pre = pre.fit_transform(X)

iso = IsolationForest(n_estimators=200, contamination=0.05, random_state=42)
iso.fit(X_pre)
df["anomaly_flag"] = iso.predict(X_pre)
df["anomaly_score"] = iso.decision_function(X_pre)

joblib.dump(pre, "preprocessor.joblib")
joblib.dump(iso, "isolation_forest.joblib")

if target_col:
    y = df[target_col]
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    clf = Pipeline([
        ("pre", pre),
        (
            "rf",
            RandomForestClassifier(
                n_estimators=300,
                max_depth=16,
                class_weight="balanced",
                random_state=42,
                n_jobs=-1,
            ),
        ),
    ])

    clf.fit(X_train, y_train)
    pred = clf.predict(X_test)
    print(classification_report(y_test, pred))
    joblib.dump(clf, "random_forest_pipeline.joblib")
```

### 14.3 Safe Control API Pattern

```python
from fastapi import FastAPI, HTTPException, Header
from pydantic import BaseModel
import subprocess
import uuid
from datetime import datetime

app = FastAPI()
API_TOKEN = "replace_with_strong_token"

ALLOWED_SCENARIOS = {
    "tcp_syn_burst": ["/opt/lab/scenarios/tcp_syn_burst.sh"],
    "web_scan": ["/opt/lab/scenarios/web_scan.sh"],
    "ssh_bruteforce_sim": ["/opt/lab/scenarios/ssh_bruteforce_sim.sh"],
    "sql_injection_sim": ["/opt/lab/scenarios/sql_injection_sim.sh"],
}

class LaunchRequest(BaseModel):
    scenario: str

@app.post("/launch")
def launch(req: LaunchRequest, x_api_token: str = Header(default="")):
    if x_api_token != API_TOKEN:
        raise HTTPException(status_code=401, detail="Unauthorized")
    if req.scenario not in ALLOWED_SCENARIOS:
        raise HTTPException(status_code=400, detail="Scenario not allowed")

    run_id = str(uuid.uuid4())
    cmd = ALLOWED_SCENARIOS[req.scenario] + [run_id]
    subprocess.Popen(cmd)

    return {
        "status": "accepted",
        "scenario": req.scenario,
        "run_id": run_id,
        "submitted_at": datetime.utcnow().isoformat() + "Z",
    }
```

Technical note: pass run_id into scenario scripts to make SIEM/ML labeling easier.

---

## 15) Troubleshooting Matrix (Expanded)

### 15.1 Suricata Silent (No Alerts)

Check in this order:

1. Interface attached in IDS settings.
2. Home net includes both lab subnets.
3. Rules downloaded and enabled.
4. Traffic actually crossing OPNsense (not bypassing via wrong NIC route).
5. Timestamp consistency (timezone/NTP).

### 15.2 SIEM Missing Logs

Check in this order:

1. OPNsense remote target configured correctly.
2. Ubuntu listener active on expected protocol/port.
3. Host firewall allows syslog port.
4. Parser not dropping messages due to format mismatch.

### 15.3 ML Looks Inaccurate

Common causes:

1. weak labels or missing run_id mapping.
2. heavy class imbalance.
3. leakage from random split across nearly identical flows.
4. stale model after changing feature schema.

### 15.4 TRex Runs but No Security Signal

Common causes:

1. traffic profile not matching enabled signatures.
2. packets dropped before Suricata due to interface/resource constraints.
3. low traffic rate below detection thresholds.

---

## 16) Deliverables for Final Demo

1. Architecture diagram + policy table.
2. OPNsense rule export (sanitized).
3. Suricata alert examples by scenario.
4. Dashboard screenshots:
   - attack control panel
   - telemetry panel
   - ML panel
5. ML metrics report (classification report + confusion matrix).
6. TRex test log with run_id correlation.
7. 10-15 minute demo script.

---

## 17) Hour-by-Hour Plan

### Day 1 (8-10h)

1. 2h: firewall baseline + aliases + route checks.
2. 2h: Suricata IDS then IPS staged enablement.
3. 2h: DNS control + blocklists.
4. 2h: validation from Kali/Ubuntu + logging evidence.
5. 1h: notes + snapshots.

### Day 2 (8-10h)

1. 3h: SIEM deployment and ingestion.
2. 2h: dashboard panels and saved queries.
3. 2h: control API + scenario wrappers.
4. 1h: tunnel publication and hardening.
5. 1h: notes + snapshots.

### Day 3 (8-10h)

1. 3h: feature engineering and model training.
2. 2h: inference outputs into dashboard.
3. 2h: TRex profile runs and tuning.
4. 1h: full dry-run demo.
5. 1h: final report and backup.

---

## 18) If You Get Blocked

Use the issue template and include:

1. timestamp
2. component
3. expected vs observed behavior
4. exact error text
5. what you already tried
6. last known good state/snapshot

With that, debugging can usually be done quickly and systematically.
