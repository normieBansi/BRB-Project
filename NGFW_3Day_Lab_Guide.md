# NGFW + AI + TRex Lab Guide (3 Days, Zero Cost)

## 1) Goal and Scope

Build a practical, no-cost NGFW lab using your existing topology:

- Kali (attacker/test generator): 192.168.60.10
- Ubuntu (target + SIEM + AI + orchestration): 192.168.50.10
- OPNsense:
  - LAN: 192.168.50.1
  - OPT1: 192.168.60.1
  - WAN: dynamic (for updates and optional internet exposure)

Desired outcome:

1. OPNsense enforces segmented security policy (default deny, explicit allow).
2. Suricata IDS/IPS runs inline and generates actionable alerts.
3. Logs and network telemetry are visible in a SIEM dashboard.
4. AI analytics runs on Ubuntu with:
   - Isolation Forest (unsupervised anomaly detection)
   - Random Forest (supervised attack classification)
5. TRex is used to relearn high-volume traffic generation and stress-test the stack.
6. Optional internet-accessible dashboard/API is set up at zero cost.

Important constraints:

- Testing and learning only.
- Keep attacks contained to your private lab.
- Do not target external systems.

---

## 2) Architecture (Practical NGFW Interpretation)

OPNsense provides most core NGFW controls in this lab:

- Stateful firewalling
- IDS/IPS (Suricata)
- Threat feed blocking (aliases/blocklists)
- DNS policy controls (Unbound blocklists)
- Rate limiting/shaping
- Central log forwarding

Ubuntu complements what OPNsense does not do deeply:

- SIEM and analytics at scale
- AI/ML model training and inference
- Attack orchestration API (safe, controlled)
- Internet-facing dashboard publishing

Data flow:

1. Kali generates attack/test traffic to Ubuntu through OPNsense.
2. OPNsense enforces policy, inspects traffic, logs events.
3. Ubuntu ingests firewall + Suricata logs, enriches and scores events.
4. Dashboard shows both controls and observations.

---

## 3) 3-Day Success Criteria

By end of Day 3 you should have:

1. Confirmed segmentation and strict policy between subnets.
2. Suricata inline mode catching at least 3 known attack patterns.
3. SIEM dashboard with:
   - live alerts/events
   - top talkers (src/dst/protocol)
   - attack timeline
4. Isolation Forest producing anomaly scores.
5. Random Forest predicting class labels from labeled traffic.
6. TRex traffic profile run and visible across firewall + SIEM + ML.
7. Optional secure internet link to dashboard/API.

---

## 4) Time Box Plan (Detailed)

## Day 1: OPNsense NGFW Baseline and Validation

### 4.1 OPNsense Preparation

1. Update OPNsense packages and reboot if needed.
2. Set correct timezone and NTP.
3. Enable SSH (optional), keep GUI admin restricted.
4. Create aliases:
   - KALI_HOST = 192.168.60.10
   - UBUNTU_HOST = 192.168.50.10
   - LAB_NET_RED = 192.168.60.0/24
   - LAB_NET_BLUE = 192.168.50.0/24

### 4.2 Firewall Policy (Minimal, Secure, Test-Friendly)

Use interface rule order carefully.

On OPT1 (Kali side):

1. Allow KALI_HOST -> UBUNTU_HOST on explicit test ports only (for example 22, 80, 443, 5000, 8080 as needed).
2. Block KALI_HOST -> any WAN net.
3. Block KALI_HOST -> host LAN ranges.
4. Final implicit deny all.

On LAN (Ubuntu side):

1. Allow UBUNTU_HOST -> OPNsense for syslog/API as required.
2. Allow UBUNTU_HOST outbound only for updates and tunnel endpoint if you publish internet dashboard later.
3. Block LAN lateral traffic not needed for project.

NAT:

- Keep default outbound NAT for OPNsense WAN where required.
- Do not add broad port forwards yet.

### 4.3 IDS/IPS (Suricata Inline)

1. Install/enable Suricata plugin.
2. Interfaces: LAN and OPT1.
3. IPS mode: inline if supported in your setup.
4. Rulesets:
   - Start with ET Open only.
   - Disable excessive noisy categories initially.
5. Enable alert logging (EVE JSON if available in your config path).
6. Set home net to both lab subnets.

### 4.4 Threat Feed and DNS Controls

1. Add IP/domain blocklists through aliases (curated sources only).
2. Enable Unbound DNS and optional blocklist mode.
3. Force lab clients to use firewall DNS (block external DNS egress from clients if possible).

### 4.5 Day 1 Validation Checklist

From Kali:

1. Confirm allowed test ports on Ubuntu are reachable.
2. Confirm blocked ports are not reachable.
3. Confirm internet egress from Kali is blocked.

From Ubuntu:

1. Confirm expected update/tunnel egress path works.
2. Confirm logs generated on OPNsense for both allow and deny cases.

Store screenshots/log snippets for final report.

---

## Day 2: SIEM, Dashboard, and Safe Remote Access

## 5.1 Ubuntu Base Setup

On Ubuntu VM:

1. Update system.
2. Install Podman and compose support.
3. Create project folders:

- ~/lab/siem
- ~/lab/collector
- ~/lab/ml
- ~/lab/control-api
- ~/lab/trex

### 5.2 SIEM Option (No-Cost, Practical)

Recommended path for 3-day outcome:

Option A (faster): Wazuh all-in-one + dashboard.
Option B (lighter custom): OpenSearch + Dashboards + Filebeat/Vector.

If speed matters most, choose Option A.

Minimum ingest sources:

1. OPNsense firewall logs
2. Suricata alerts/events
3. Ubuntu service logs

### 5.3 Log Forwarding from OPNsense

1. Configure remote syslog destination to Ubuntu IP and chosen port.
2. Enable forwarding categories:
   - firewall
   - system
   - Suricata/IDS
3. Validate events appear in SIEM index.

### 5.4 Build Your Two-Panel Dashboard

Create these visual groups:

Panel Group 1: Attack Control

1. Scenario buttons (not arbitrary shell):
   - tcp_syn_burst
   - web_scan
   - ssh_bruteforce_sim
   - sql_injection_sim
2. Queue status and last run metadata.
3. Safety toggle: max duration and max concurrency.

Panel Group 2: Security Telemetry

1. Live event stream
2. Alert counts by severity
3. Top source IPs, destination IPs, destination ports
4. Bytes and packet rate over time
5. Suricata signature leaderboard
6. Model outputs:
   - anomaly score trend
   - predicted class distribution

### 5.5 Internet Exposure (Free, Secure Enough for Demo)

Choose one:

1. Cloudflare Tunnel (free tier)
2. Ngrok free tier

Do not expose Kali directly.
Expose only:

- dashboard URL
- control API endpoint with authentication

Hardening for exposure:

1. Add strong auth (token/JWT or basic auth behind tunnel).
2. Add IP allowlist if possible.
3. Restrict API to predefined scenarios only.
4. Add request rate limits.

### 5.6 Day 2 Validation Checklist

1. OPNsense logs visible in dashboard.
2. Suricata alerts visible and filterable.
3. Attack control buttons trigger expected job queue entries.
4. Internet URL reachable with authentication.
5. No direct inbound path to Kali.

---

## Day 3: AI Models + TRex Relearning + Final Demo

## 6.1 Data Pipeline for ML

Collect and normalize features from Suricata EVE + firewall logs:

Candidate features:

- src_ip
- dst_ip
- src_port
- dst_port
- proto
- flow_duration
- packets
- bytes
- tcp_flags
- alert_signature_id
- alert_severity
- hour_of_day
- inter_arrival_time

Preprocessing:

1. Handle missing values.
2. Encode categorical fields (protocol, flags).
3. Normalize numeric fields for anomaly model.
4. Split train/validation/test by time or scenario.

### 6.2 Isolation Forest (Unsupervised)

Use mostly benign baseline window for training.

Suggested starter parameters:

- n_estimators: 200
- contamination: 0.02 to 0.08 (tune)
- random_state: fixed

Outputs:

- anomaly_score
- anomaly_flag

Push outputs back to SIEM index for dashboarding.

### 6.3 Random Forest (Supervised)

Define initial labels:

- benign
- scan
- brute_force
- web_attack
- flood

Suggested starter parameters:

- n_estimators: 300
- max_depth: 12 to 20
- class_weight: balanced

Metrics to report:

- precision/recall/F1 per class
- confusion matrix
- feature importance chart

### 6.4 TRex Relearning Path

Goal: generate repeatable, controlled traffic mixes.

Approach options:

1. Stateless mode first (easier)
2. Stateful mode next (optional if time permits)

Relearning sequence:

1. Install TRex docs/tools references.
2. Run simple profile with low PPS.
3. Increase rate gradually and observe OPNsense + SIEM behavior.
4. Run mixed profiles (benign + attack-like) for model training data.

If VirtualBox performance is limited:

1. Lower pps and flow counts.
2. Short runs with repeat loops.
3. Focus on correctness and visibility, not maximum throughput.

### 6.5 Controlled Attack Scenarios (Kali)

Run only inside lab against Ubuntu targets you own:

1. Port scan simulation
2. HTTP burst and malformed request simulation
3. Credential spray simulation on test service
4. Mixed concurrency runs

Each scenario should emit:

- run_id
- start/end time
- target
- expected signature family

This helps clean labeling for Random Forest.

### 6.6 Day 3 Validation Checklist

1. Isolation Forest flags high-rate or anomalous flows.
2. Random Forest predicts expected label for known scenarios.
3. Dashboard displays model outputs next to raw alerts.
4. TRex run is visible in firewall counters and SIEM panels.
5. Full demonstration script can run in 10 to 15 minutes.

---

## 7) Implementation Cookbook (Commands and Examples)

Note: adapt commands to your exact distro versions and package sources.

### 7.1 Ubuntu Packages

```bash
sudo apt update && sudo apt -y upgrade
sudo apt -y install podman podman-compose python3 python3-venv python3-pip git jq curl
```

### 7.2 Python Environment for ML

```bash
cd ~/lab/ml
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install pandas numpy scikit-learn matplotlib seaborn fastapi uvicorn[standard] joblib pydantic
```

### 7.3 Minimal ML Training Skeleton

```python
# train_models.py
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.ensemble import IsolationForest, RandomForestClassifier
from sklearn.metrics import classification_report
import joblib

# Replace with your parsed feature dataset
df = pd.read_csv("features.csv")

feature_cols = [c for c in df.columns if c not in ["label"]]
X = df[feature_cols]

# Isolation Forest on all data or benign subset
iso = IsolationForest(n_estimators=200, contamination=0.05, random_state=42)
iso.fit(X)
df["anomaly_flag"] = iso.predict(X)
df["anomaly_score"] = iso.decision_function(X)
joblib.dump(iso, "isolation_forest.joblib")

# Random Forest supervised path
if "label" in df.columns:
    y = df["label"]
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)
    rf = RandomForestClassifier(
        n_estimators=300,
        max_depth=16,
        class_weight="balanced",
        random_state=42,
        n_jobs=-1,
    )
    rf.fit(X_train, y_train)
    pred = rf.predict(X_test)
    print(classification_report(y_test, pred))
    joblib.dump(rf, "random_forest.joblib")
```

### 7.4 FastAPI Control Endpoint (Safe Pattern)

```python
# control_api.py
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import subprocess

app = FastAPI()

ALLOWED_SCENARIOS = {
    "tcp_syn_burst": ["/opt/lab/scenarios/tcp_syn_burst.sh"],
    "web_scan": ["/opt/lab/scenarios/web_scan.sh"],
    "ssh_bruteforce_sim": ["/opt/lab/scenarios/ssh_bruteforce_sim.sh"],
    "sql_injection_sim": ["/opt/lab/scenarios/sql_injection_sim.sh"],
}

class LaunchRequest(BaseModel):
    scenario: str

@app.post("/launch")
def launch(req: LaunchRequest):
    if req.scenario not in ALLOWED_SCENARIOS:
        raise HTTPException(status_code=400, detail="Scenario not allowed")
    subprocess.Popen(ALLOWED_SCENARIOS[req.scenario])
    return {"status": "accepted", "scenario": req.scenario}
```

Security note:

- Never execute arbitrary user-provided commands.

### 7.5 TRex Relearning Checklist

1. Start with a single simple profile and low rate.
2. Confirm packets traverse OPT1 -> OPNsense -> LAN.
3. Correlate timestamps:
   - TRex send window
   - firewall session counters
   - Suricata alerts
   - SIEM ingest chart
4. Increase load only if telemetry remains consistent.

---

## 8) Operational Guardrails

1. Keep WAN exposure off until local validation is complete.
2. Snapshot VMs at end of each day.
3. Save rule exports and SIEM dashboard exports daily.
4. Keep attack scripts deterministic and parameter-limited.
5. Use separate API token for dashboard controls.

---

## 9) Troubleshooting Matrix

1. No Suricata alerts:
   - verify interface assignment and home net
   - verify rule categories enabled
   - check IPS/IDS mode mismatch
2. No logs in SIEM:
   - verify remote syslog target/port
   - check Ubuntu firewall and listener
   - inspect parser/index pipeline errors
3. Model quality poor:
   - improve labels and scenario metadata
   - rebalance classes
   - tune contamination and depth
4. TRex unstable in VM:
   - lower packet rate
   - simplify profile
   - pin VM resources and reduce competing load

---

## 10) Deliverables for Your Final Demo

1. Architecture diagram and subnet policy table.
2. OPNsense ruleset export (sanitized).
3. Suricata alert examples per scenario.
4. Dashboard screenshots for:
   - attack launcher
   - telemetry
   - model outputs
5. ML training metrics report.
6. TRex run summary with observed detections.
7. Lessons learned and next improvements.

---

## 11) Nice-to-Have Next (Post 3 Days)

1. Add Zeek for richer protocol metadata.
2. Add MITRE ATT&CK mapping in dashboard.
3. Add auto-response with strict confidence threshold + human confirmation.
4. Add replay datasets for repeatable benchmarking.

---

## 12) Suggested Hour-by-Hour Schedule

### Day 1 (8 to 10 hours)

1. 2h: OPNsense update, aliases, baseline rules
2. 2h: Suricata setup and first detections
3. 2h: DNS/blocklist hardening
4. 2h: validation tests from Kali and Ubuntu
5. 1h: documentation and VM snapshots

### Day 2 (8 to 10 hours)

1. 3h: SIEM deployment and parsing
2. 2h: dashboard construction
3. 2h: control API and scenario wrappers
4. 1h: internet publication hardening and test
5. 1h: documentation and snapshots

### Day 3 (8 to 10 hours)

1. 3h: feature extraction and ML training
2. 2h: inference pipeline and dashboard integration
3. 2h: TRex runs and tuning
4. 1h: final demo rehearsal
5. 1h: final report and backup

---

## 13) If You Get Blocked

Keep an issue log with this structure:

- timestamp
- component (OPNsense / SIEM / ML / TRex / API)
- expected behavior
- observed behavior
- error text/log snippet
- what you already tried

I can quickly debug from that format.

Good luck. This is absolutely doable in 3 focused days with your current setup.
