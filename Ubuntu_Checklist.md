# Ubuntu Container Checklist

**Navigation:** [OPNsense Checklist](OPNsense_Click_By_Click_Checklist.md) | [Kali Checklist](Kali_Checklist.md) | [Lab Guide](NGFW_3Day_Lab_Guide.md)

---

This checklist covers everything done on or from the Ubuntu container: attack target services, log receiver, SIEM, ML pipeline, control API, and dashboard.

Lab context:

1. Ubuntu runs as a Podman container on Debian.
2. Ubuntu IP = 192.168.50.10.
3. Gateway = 192.168.50.1 (OPNsense LAN).
4. Debian host has 4 vCPU, 4 GB RAM, 40 GB storage.
5. Commands prefixed with `[debian]` are run on the Debian host. All others are inside the Ubuntu container.

---

## Day 1 - Base Services, Log Receiver, and Attack Target

## 1. Container Startup

### 1.1 Confirm Ubuntu Container Is Running

On Debian:

```bash
podman ps
```

Expected: Ubuntu container is listed as Up.

If not running:

```bash
sudo podman run -d --name ubuntu-lab --replace  --cap-add=NET_RAW --cap-add=NET_BIND_SERVICE --network lan1 --ip 192.168.50.10 -v ./10-opnsense.conf:/etc/rsyslog.d/10-opnsense.conf:ro -v ./logs:/var/log ubuntu rsyslogd -n
```

Replace `ubuntu` with your actual container name.

### 1.2 Get a Shell into Ubuntu

```bash
podman exec -it ubuntu bash
```

All following commands are run inside this shell unless marked `[debian]`.

### 1.3 Verify IP and Gateway

```bash
ip a
ip route
```

Expected:

1. Interface with 192.168.50.10.
2. Default route via 192.168.50.1.

### 1.4 Ping OPNsense LAN

```bash
ping -c 2 192.168.50.1
```

Expected: replies from 192.168.50.1. If this fails, stop and fix Podman networking first.

---

## 2. Install Base Packages

### 2.1 Update and Install

```bash
apt update && apt upgrade -y
apt install -y \
  apache2 \
  curl \
  rsyslog \
  tcpdump \
  python3 \
  python3-venv \
  python3-pip \
  git \
  jq \
  netcat-openbsd \
  nano
```

#### Also error "The apache2 configtest failed."
```bash
# Missing log directory
mkdir -p /var/log/apache2
chown -R www-data:www-data /var/log/apache2
# ServerName warning (non-fatal)
echo "ServerName 192.168.50.10" >> /etc/apache2/apache2.conf
```
as `/var/log` is a mounted volume → default Apache dirs absent

### 2.2 Verify Python Version

```bash
python3 --version
```

Expected: 3.9 or higher.

---

## 3. Start Apache (Attack Target Service)

### 3.1 Start and Enable Apache

```bash
service apache2 start
```

If systemd is available inside the container:

```bash
systemctl enable --now apache2
```

### 3.2 Verify Apache Responds Locally

```bash
curl http://127.0.0.1
```

Expected: HTML of the default Apache page is printed.

### 3.3 Verify Apache Responds from Kali

From the Kali container:

```bash
curl -I http://192.168.50.10
```

Expected: HTTP 200 or 403 headers. If the connection times out, check OPNsense LAN rules allow Kali to Ubuntu on port 80.

---

## 4. Configure rsyslog Log Receiver

Ubuntu must receive logs from OPNsense before anything else in the SIEM pipeline can work.

### 4.1 Create rsyslog Config for OPNsense

run it inside bash only, not fish.

```bash
cat > /etc/rsyslog.d/10-opnsense.conf << 'EOF'
# OPNsense remote syslog receiver

module(load="imudp")
input(type="imudp" port="514")

module(load="imtcp")
input(type="imtcp" port="5514")

# Write OPNsense logs to a dedicated file
if $fromhost-ip == '192.168.50.1' then /var/log/opnsense.log
& stop
EOF
```

Replace `192.168.50.1` with the actual OPNsense LAN IP if different.

### 4.2 Restart rsyslog

```bash
sudo podman restart ubuntu-lab
ps aux | grep rsyslogd
```

Expected: rsyslog is active and running.

### 4.3 Confirm Listener Sockets Are Open

```bash
ss -lunpt | grep -E '514|5514'
```

Expected: UDP 514 and TCP 5514 appear as listening.

### 4.4 Create the Log File Early

```bash
touch /var/log/opnsense.log
chmod 640 /var/log/opnsense.log
```
and immediately run
```bash
chown syslog:syslog /var/log/opnsense.log
chmod 644 /var/log/opnsense.log
rsyslogd -N1
```

---

## 5. Day 1 Log Validation

### 5.1 Confirm OPNsense Logs Are Arriving

On Ubuntu, run a live capture:

```bash
tcpdump -ni any port 514 or port 5514
```

In OPNsense UI, go to Firewall > Log Files > Live View. This generates log traffic.

Expected: packets from 192.168.50.1 appear in tcpdump output.

### 5.2 Check rsyslog Is Writing to File

After a few seconds:

```bash
tail -f /var/log/opnsense.log
```

Expected: log lines from OPNsense appear. Ctrl+C to stop.

### 5.3 Day 1 Complete Conditions

Day 1 is done when:

1. Apache serves HTTP responses.
2. rsyslog listens on UDP 514 and TCP 5514.
3. OPNsense log packets arrive and are written to /var/log/opnsense.log.

#### Extra: Clean up log files
```bash
truncate -s 0 /var/log/opnsense.log
# or
: > /var/log/opnsense.log
```
incase issue arises
```bash
chown syslog:syslog /var/log/opnsense.log
```

---

## Day 2 - SIEM, Control API, and Dashboard

## 6. Choose and Deploy SIEM

Given the Debian VM has 4 GB total RAM across all containers, use Grafana + Loki as the primary stack. It uses roughly 300 to 500 MB total and still gives dashboard + log search capability.

If you have more RAM available, Wazuh or OpenSearch can be substituted, but both need 2 to 4 GB alone.

### 6.1 Install Podman Compose on Debian

`[debian]`:

```bash
pip3 install podman-compose
```

Or:

```bash
apt install -y podman-compose
```

### 6.2 Create Compose Directory on Debian

`[debian]`:

```bash
mkdir -p ~/lab/siem
cd ~/lab/siem
```

### 6.3 Create Loki Config File

`[debian]`:

```bash
cat > loki-config.yaml << 'EOF'
auth_enabled: false

server:
  http_listen_port: 3100

ingester:
  wal:
    enabled: true
    dir: /loki/wal
  lifecycler:
    address: 127.0.0.1
    ring:
      kvstore:
        store: inmemory
      replication_factor: 1
  chunk_idle_period: 3m
  chunk_retain_period: 1m

schema_config:
  configs:
    - from: 2024-01-01
      store: boltdb-shipper
      object_store: filesystem
      schema: v11
      index:
        prefix: index_
        period: 24h

storage_config:
  boltdb_shipper:
    active_index_directory: /loki/index
    cache_location: /loki/cache
    shared_store: filesystem
  filesystem:
    directory: /loki/chunks

limits_config:
  reject_old_samples: false

chunk_store_config:
  max_look_back_period: 0s

table_manager:
  retention_deletes_enabled: false
  retention_period: 0s
EOF
```

### 6.4 Create Promtail Config (Reads OPNsense Log File)

`[debian]`:

```bash
cat > promtail-config.yaml << 'EOF'
server:
  http_listen_port: 9080
  grpc_listen_port: 0

positions:
  filename: /tmp/positions.yaml

clients:
  - url: http://loki:3100/loki/api/v1/push

scrape_configs:
  - job_name: opnsense
    static_configs:
      - targets:
          - localhost
        labels:
          job: opnsense
          __path__: /home/vbox/logs/opnsense.log
EOF
```

### 6.5 Create Docker Compose File

`[debian]`:

```bash
cat > docker-compose.yml << 'EOF'
version: "3"

services:
  loki:
    image: grafana/loki:2.9.0
    ports:
      - "3100:3100"
    volumes:
      - ./loki-config.yaml:/etc/loki/local-config.yaml
      - loki_data:/loki
    command: -config.file=/etc/loki/local-config.yaml
    restart: unless-stopped

  promtail:
    image: docker.io/grafana/promtail:2.9.0
    volumes:
      - ./promtail-config.yaml:/etc/promtail/config.yml
      - /home/vbox/logs/opnsense.log:/var/log/opnsense.log:ro
    command: -config.file=/etc/promtail/config.yml
    depends_on:
      - loki
    restart: unless-stopped

  grafana:
    image: grafana/grafana:10.0.0
    ports:
      - "3000:3000"
    environment:
      - GF_AUTH_ANONYMOUS_ENABLED=true
      - GF_AUTH_ANONYMOUS_ORG_ROLE=Viewer
      - GF_AUTH_DISABLE_LOGIN_FORM=false
    volumes:
      - grafana_data:/var/lib/grafana
    depends_on:
      - loki
    restart: unless-stopped

volumes:
  loki_data:
  grafana_data:
EOF
```

### 6.6 Start the SIEM Stack

`[debian]`:

```bash
cd ~/lab/siem
podman-compose up -d
```

Wait 30 seconds then check:

```bash
podman ps
```

Expected: loki, promtail, and grafana containers are running.

### 6.7 Access Grafana

Open in browser on your Windows host: `http://192.168.50.1:3000` or `http://<Debian-LAN-IP>:3000`.

Note: you may need to access via the Debian IP if OPNsense NAT is not forwarding port 3000.

Default credentials: admin / admin (change on first login).

### 6.8 Add Loki Data Source in Grafana

1. Go to Configuration (gear icon) > Data Sources.
2. Click Add data source.
3. Select Loki.
4. URL = `http://loki:3100`.
5. Click Save and Test.

Expected: connection successful.

### 6.9 Create a Basic Log Dashboard in Grafana

1. Click + > Dashboard > Add panel.
2. Select Loki as the data source.
3. In the query field, enter: `{job="opnsense"}`.
4. Set visualization to Logs.
5. Save the dashboard as OPNsense Logs.

---

## 7. Deploy FastAPI Control API

### 7.1 Create Project Directory on Ubuntu

Inside Ubuntu container:

```bash
mkdir -p ~/lab/control-api
cd ~/lab/control-api
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install fastapi uvicorn[standard] pydantic
```

### 7.2 Create the Control API File

```bash
cat > ~/lab/control-api/app.py << 'PYEOF'
from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import subprocess
import uuid
import json
import os
from datetime import datetime, timezone

app = FastAPI(title="NGFW Lab Control API")

API_TOKEN = os.environ.get("API_TOKEN", "change_this_token_now")

# Add CORS so the hosted dashboard can call this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost",
        "http://127.0.0.1",
        "https://yourusername.github.io",  # Update with your GitHub Pages URL
        "*",  # Remove this in production and list origins explicitly
    ],
    allow_methods=["GET", "POST"],
    allow_headers=["X-API-Token", "Content-Type"],
)

ALLOWED_SCENARIOS = {
    "tcp_syn_burst": ["/opt/lab/scenarios/tcp_syn_burst.sh"],
    "web_scan": ["/opt/lab/scenarios/web_scan.sh"],
    "ssh_bruteforce_sim": ["/opt/lab/scenarios/ssh_bruteforce_sim.sh"],
    "sql_injection_sim": ["/opt/lab/scenarios/sql_injection_sim.sh"],
}

run_log = []  # In-memory run log, resets on restart


class LaunchRequest(BaseModel):
    scenario: str


def require_auth(token: str):
    if token != API_TOKEN:
        raise HTTPException(status_code=401, detail="Unauthorized")


@app.post("/launch")
def launch(req: LaunchRequest, x_api_token: str = Header(default="")):
    require_auth(x_api_token)
    if req.scenario not in ALLOWED_SCENARIOS:
        raise HTTPException(status_code=400, detail="Scenario not allowed")
    run_id = str(uuid.uuid4())
    cmd = ALLOWED_SCENARIOS[req.scenario] + [run_id]
    subprocess.Popen(cmd)
    entry = {
        "run_id": run_id,
        "scenario": req.scenario,
        "submitted_at": datetime.now(timezone.utc).isoformat(),
        "status": "accepted",
    }
    run_log.insert(0, entry)
    if len(run_log) > 100:
        run_log.pop()
    return entry


@app.get("/runs")
def get_runs(x_api_token: str = Header(default="")):
    require_auth(x_api_token)
    return {"runs": run_log[:20]}


@app.get("/telemetry/events")
def get_events(limit: int = 20, x_api_token: str = Header(default="")):
    require_auth(x_api_token)
    events = []
    log_path = "/var/log/opnsense.log"
    try:
        with open(log_path, "r") as f:
            lines = f.readlines()
        for line in reversed(lines):
            line = line.strip()
            if not line:
                continue
            events.append({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "raw": line[:300],
                "src_ip": "192.168.60.10",
                "dst_ip": "192.168.50.10",
                "dst_port": 80,
                "proto": "TCP",
                "action": "alert",
                "signature": line[:80] if len(line) > 0 else "firewall_event",
                "severity": "medium",
            })
            if len(events) >= limit:
                break
    except FileNotFoundError:
        pass
    return {"events": events}


@app.get("/telemetry/summary")
def get_summary(x_api_token: str = Header(default="")):
    require_auth(x_api_token)
    # Stub: replace with real log parsing as needed
    return {
        "total_alerts": len(run_log) * 12,
        "blocked": len(run_log) * 3,
        "high_sev": len(run_log) * 4,
        "medium_sev": len(run_log) * 5,
        "low_sev": len(run_log) * 3,
        "anomalies": len(run_log) * 2,
        "active_flows": 0,
        "over_time": [],
        "top_sources": [{"ip": "192.168.60.10", "count": len(run_log) * 10}],
        "top_ports": [
            {"port": 80, "count": len(run_log) * 5},
            {"port": 22, "count": len(run_log) * 3},
        ],
    }


@app.get("/ml/summary")
def get_ml_summary(x_api_token: str = Header(default="")):
    require_auth(x_api_token)
    ml_path = os.path.expanduser("~/lab/ml/latest_results.json")
    try:
        with open(ml_path) as f:
            return json.load(f)
    except FileNotFoundError:
        return {
            "total_scored": 0,
            "anomaly_pct": "0.0",
            "top_class": "none",
            "distribution": {},
            "trend": [],
        }


@app.get("/ml/predictions")
def get_ml_predictions(limit: int = 15, x_api_token: str = Header(default="")):
    require_auth(x_api_token)
    pred_path = os.path.expanduser("~/lab/ml/predictions.json")
    try:
        with open(pred_path) as f:
            data = json.load(f)
            return {"predictions": data[:limit]}
    except FileNotFoundError:
        return {"predictions": []}
PYEOF
```

### 7.3 Start the Control API

```bash
cd ~/lab/control-api
source .venv/bin/activate
API_TOKEN=your_strong_token_here uvicorn app:app --host 0.0.0.0 --port 5000
```

Replace `your_strong_token_here` with an actual token. Use at least 20 random characters.

Test it locally first:

```bash
curl http://127.0.0.1:5000/runs \
  -H "X-API-Token: your_strong_token_here"
```

Expected: `{"runs": []}`.

### 7.4 Run the API as a Background Service

```bash
nohup uvicorn app:app --host 0.0.0.0 --port 5000 &> ~/lab/control-api/api.log &
echo $! > ~/lab/control-api/api.pid
```

To stop it later:

```bash
kill $(cat ~/lab/control-api/api.pid)
```

### 7.5 Place Dashboard HTML

Copy `dashboard/index.html` from your Windows host into the Ubuntu container or serve it from Debian.

Option A: Serve from Debian directly:

`[debian]`:

```bash
cd ~/Desktop/test/dashboard
python3 -m http.server 8888
```

Open on Windows host: `http://<Debian-IP>:8888`.

Option B: Copy into Ubuntu and serve:

```bash
mkdir -p ~/lab/dashboard
# Copy the file via podman cp or mount a volume
```

`[debian]`:

```bash
podman cp ~/Desktop/test/dashboard/index.html ubuntu:/root/lab/dashboard/
podman exec ubuntu bash -c "cd /root/lab/dashboard && python3 -m http.server 8888 &"
```

---

## 8. Test Dashboard

### 8.1 Open Dashboard in Browser

Open `http://<Debian-IP>:8888` on your Windows host.

### 8.2 Test in Mock Mode

1. Confirm Mock Mode toggle is ON (default).
2. Click the Telemetry tab.
3. Confirm charts load with mock data.
4. Click the ML Analytics tab.
5. Confirm ML charts load.

### 8.3 Test in Live Mode

1. Enter API Base URL = `http://192.168.50.10:5000`.
2. Enter API Token = the token you set.
3. Turn off Mock Mode.
4. Click Attack Control tab.
5. Select a scenario and click Launch.
6. Expected: run appears in the Recent Runs table with status accepted.

---

## Day 3 - ML Pipeline

## 9. Set Up Python ML Environment

### 9.1 Create ML Directory

```bash
mkdir -p ~/lab/ml
cd ~/lab/ml
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install pandas numpy scikit-learn matplotlib seaborn joblib pyarrow
```

### 9.2 Verify Installs

```bash
python3 -c "import sklearn; print(sklearn.__version__)"
```

Expected: version number printed.

---

## 10. Collect and Parse Training Data

### 10.1 Export OPNsense Log to CSV for Training

```bash
cat > ~/lab/ml/parse_logs.py << 'PYEOF'
import re
import csv
import sys
from datetime import datetime

LOG_PATH = "/var/log/opnsense.log"
OUT_PATH = "/root/lab/ml/features.csv"

FIELDS = ["timestamp", "src_ip", "dst_ip", "dst_port", "proto",
          "action", "signature", "severity", "label"]

rows = []
with open(LOG_PATH) as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        # Very basic extraction - adapt regex to your actual log format
        row = {
            "timestamp": datetime.utcnow().isoformat(),
            "src_ip": "192.168.60.10",
            "dst_ip": "192.168.50.10",
            "dst_port": 80,
            "proto": "TCP",
            "action": "alert" if "block" not in line.lower() else "block",
            "signature": line[:100],
            "severity": "medium",
            "label": "unknown",
        }
        rows.append(row)

with open(OUT_PATH, "w", newline="") as out:
    writer = csv.DictWriter(out, fieldnames=FIELDS)
    writer.writeheader()
    writer.writerows(rows)

print(f"Wrote {len(rows)} rows to {OUT_PATH}")
PYEOF
```

```bash
source .venv/bin/activate
python3 ~/lab/ml/parse_logs.py
```

### 10.2 Manually Label Rows Using run_id Log

Open `features.csv` in nano and update the `label` column for rows that correspond to known attack windows:

```text
label values: benign, scan, web_attack, brute_force, flood, sql_injection
```

Use the run_id timestamps from the Kali run log to identify attack windows.

---

## 11. Train Isolation Forest

### 11.1 Create and Run Training Script

```bash
cat > ~/lab/ml/train.py << 'PYEOF'
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.impute import SimpleImputer
from sklearn.ensemble import IsolationForest, RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report
import joblib
import json

df = pd.read_csv("/root/lab/ml/features.csv")

# Feature columns
cat_cols = ["proto", "action", "signature"]
num_cols = ["dst_port", "severity"]

# Encode severity to numeric if needed
severity_map = {"high": 1, "medium": 2, "low": 3, "unknown": 2}
df["severity"] = df["severity"].map(severity_map).fillna(2)

feature_cols = cat_cols + num_cols
X = df[feature_cols].copy()

pre = ColumnTransformer(transformers=[
    ("num", Pipeline([
        ("imp", SimpleImputer(strategy="median")),
        ("sc", StandardScaler()),
    ]), num_cols),
    ("cat", Pipeline([
        ("imp", SimpleImputer(strategy="most_frequent")),
        ("ohe", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
    ]), cat_cols),
])

X_pre = pre.fit_transform(X)

# Isolation Forest (unsupervised anomaly detection)
iso = IsolationForest(n_estimators=200, contamination=0.05, random_state=42)
iso.fit(X_pre)
df["anomaly_flag"] = iso.predict(X_pre)
df["anomaly_score"] = iso.decision_function(X_pre)

joblib.dump(pre, "/root/lab/ml/preprocessor.joblib")
joblib.dump(iso, "/root/lab/ml/isolation_forest.joblib")
print("Isolation Forest trained and saved.")

# Random Forest (supervised classification, if labels available)
if "label" in df.columns and df["label"].nunique() > 1 and \
   not (df["label"] == "unknown").all():
    df_labeled = df[df["label"] != "unknown"].copy()
    y = df_labeled["label"]
    X_labeled = df_labeled[feature_cols]

    X_train, X_test, y_train, y_test = train_test_split(
        X_labeled, y, test_size=0.2, random_state=42, stratify=y
    )

    clf = Pipeline([
        ("pre", pre),
        ("rf", RandomForestClassifier(
            n_estimators=300, max_depth=16,
            class_weight="balanced", random_state=42, n_jobs=-1,
        )),
    ])
    clf.fit(X_train, y_train)
    pred = clf.predict(X_test)
    print(classification_report(y_test, pred))
    joblib.dump(clf, "/root/lab/ml/random_forest_pipeline.joblib")
    print("Random Forest trained and saved.")
else:
    print("Skipping Random Forest: no labeled data or only one class.")

# Write latest results for API
results = {
    "total_scored": len(df),
    "anomaly_pct": str(round((df["anomaly_flag"] == -1).mean() * 100, 1)),
    "top_class": "benign",
    "distribution": dict(df["label"].value_counts()),
    "trend": [],
}
with open("/root/lab/ml/latest_results.json", "w") as f:
    json.dump(results, f)
print("Results written to latest_results.json")
PYEOF
```

```bash
source .venv/bin/activate
python3 ~/lab/ml/train.py
```

---

## 12. Run Inference and Write Predictions

### 12.1 Create Inference Script

```bash
cat > ~/lab/ml/infer.py << 'PYEOF'
import pandas as pd
import joblib
import json
from datetime import datetime, timezone

pre = joblib.load("/root/lab/ml/preprocessor.joblib")
iso = joblib.load("/root/lab/ml/isolation_forest.joblib")

try:
    clf = joblib.load("/root/lab/ml/random_forest_pipeline.joblib")
    has_clf = True
except FileNotFoundError:
    has_clf = False

df = pd.read_csv("/root/lab/ml/features.csv")

cat_cols = ["proto", "action", "signature"]
num_cols = ["dst_port", "severity"]
severity_map = {"high": 1, "medium": 2, "low": 3, "unknown": 2}
df["severity"] = df["severity"].map(severity_map).fillna(2)

X = df[cat_cols + num_cols].copy()
X_pre = pre.transform(X)

df["anomaly_flag"] = iso.predict(X_pre)
df["anomaly_score"] = iso.decision_function(X_pre)

if has_clf:
    df["predicted_class"] = clf.predict(X)
    proba = clf.predict_proba(X)
    df["confidence"] = proba.max(axis=1)
else:
    df["predicted_class"] = "unknown"
    df["confidence"] = 0.0

preds = []
for _, row in df.tail(50).iterrows():
    preds.append({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "src_ip": str(row.get("src_ip", "unknown")),
        "dst_port": int(row["dst_port"]),
        "anomaly_score": round(float(row["anomaly_score"]), 4),
        "anomaly_flag": int(row["anomaly_flag"]),
        "predicted_class": str(row["predicted_class"]),
        "confidence": round(float(row["confidence"]), 4),
    })

with open("/root/lab/ml/predictions.json", "w") as f:
    json.dump(list(reversed(preds)), f)

print(f"Inference done. {len(preds)} predictions written.")
PYEOF
```

```bash
source .venv/bin/activate
python3 ~/lab/ml/infer.py
```

### 12.2 Verify Predictions File

```bash
cat ~/lab/ml/predictions.json | python3 -m json.tool | head -40
```

Expected: JSON array with prediction records.

### 12.3 Verify ML Data Appears in Dashboard

1. Open dashboard in browser.
2. Turn off Mock Mode.
3. Click ML Analytics tab.
4. Click Refresh.

Expected: real prediction data loads instead of mock data.

---

## 13. Day 3 Final Checks

### 13.1 Restart API with ML Data Ready

```bash
kill $(cat ~/lab/control-api/api.pid) 2>/dev/null || true
cd ~/lab/control-api
source .venv/bin/activate
nohup API_TOKEN=your_strong_token_here \
  uvicorn app:app --host 0.0.0.0 --port 5000 &> api.log &
echo $! > api.pid
```

### 13.2 Run a Final Scenario and Watch Pipeline End-to-End

From Kali:

```bash
curl -X POST http://192.168.50.10:5000/launch \
  -H "X-API-Token: your_strong_token_here" \
  -H "Content-Type: application/json" \
  -d '{"scenario":"web_scan"}'
```

While it runs:

1. Watch OPNsense Alerts page for new events.
2. Watch Grafana Loki dashboard for new log lines.
3. After completion, rerun inference: `python3 ~/lab/ml/infer.py`.
4. Refresh ML Analytics tab in dashboard.

---

## 14. Migration: Deploy Dashboard to Free Web Hosting

This section covers publishing the static dashboard HTML file so it can be accessed from the internet, with the FastAPI backend exposed via Cloudflare Tunnel.

### 14.1 Prepare Cloudflare Tunnel for FastAPI (on Debian)

`[debian]`:

```bash
# Install cloudflared
wget -q https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb
sudo dpkg -i cloudflared-linux-amd64.deb

# Start a quick tunnel to the control API on Ubuntu (port 5000)
cloudflared tunnel --url http://192.168.50.10:5000
```

The command prints a public URL like `https://random-words.trycloudflare.com`.

Copy that URL. You will use it as the API Base URL in the dashboard.

### 14.2 Update CORS in Control API

In `~/lab/control-api/app.py`, update the `allow_origins` list to include your GitHub Pages URL.

Replace:

```python
"https://yourusername.github.io",
```

With your actual GitHub Pages URL. Then restart the API.

### 14.3 Deploy Dashboard to GitHub Pages

On your Windows host:

1. Create a new GitHub repository (public or private with Pages enabled).
2. Create a folder `docs` in the repository.
3. Copy `dashboard/index.html` into `docs/index.html`.
4. Push to GitHub.
5. Go to repository Settings > Pages.
6. Set source to Deploy from a branch.
7. Select branch main and folder /docs.
8. Save.

Access at: `https://yourusername.github.io/your-repo-name/`.

### 14.4 Update API URL in the Live Dashboard

When you open the dashboard on GitHub Pages:

1. In the Config Bar, set API Base URL to your Cloudflare Tunnel URL.
2. Enter your API token.
3. Turn off Mock Mode.
4. Test the Launch Scenario button.

### 14.5 Alternative: Deploy to Netlify

1. Go to netlify.com and log in.
2. Click Sites > Drag and drop site folder.
3. Drag the `dashboard/` folder from your Windows machine.
4. Netlify gives you a URL like `https://yourname.netlify.app`.
5. Update CORS and API URL as above.

### 14.6 Security Checklist Before Going Public

1. Remove the `"*"` from the `allow_origins` CORS list in the API.
2. Use a strong API token (20+ random characters, not a dictionary word).
3. Cloudflare Tunnel exposes only the API, not the log files, SIEM internals, or Kali.
4. Do not expose OPNsense web UI or Grafana directly.
5. Cloudflare Tunnel URL changes each time you restart without a named tunnel. Use a named tunnel for stable URL.

---

## 15. Ubuntu Minimum Success Checklist

You are done when all are true:

1. Apache responds on port 80.
2. rsyslog receives logs from OPNsense on UDP 514.
3. OPNsense logs are written to /var/log/opnsense.log.
4. Grafana is accessible and shows OPNsense log data.
5. Control API responds and accepts launch requests.
6. All four scenario scripts are reachable from the API.
7. features.csv contains parsed log data.
8. Isolation Forest model is trained and saved.
9. Random Forest model is trained if labeled data exists.
10. Predictions are written to predictions.json.
11. Dashboard shows real data in live mode.
12. Migration path to GitHub Pages or Netlify is tested.
