# Ubuntu Container Checklist

**Navigation:** [OPNsense Checklist](OPNsense_Click_By_Click_Checklist.md) | [Kali Checklist](Kali_Checklist.md) | [Theory Guide](NGFW_Theory_to_Action_Guide.md)

**Theory Quick Index (Most Used):**

1. [Telemetry Quality and Signal-to-Noise](NGFW_Theory_to_Action_Guide.md#6-theory-telemetry-quality-and-signal-to-noise)
2. [Containment and Incident Response Loop](NGFW_Theory_to_Action_Guide.md#7-theory-containment-and-incident-response-loop)
3. [Safe Orchestration and Reproducibility](NGFW_Theory_to_Action_Guide.md#8-theory-safe-orchestration-and-reproducibility)
4. [ML-Augmented NGFW Analytics](NGFW_Theory_to_Action_Guide.md#9-theory-ml-augmented-ngfw-analytics)
5. [Minimal Exposure for External Access](NGFW_Theory_to_Action_Guide.md#11-theory-minimal-exposure-for-external-access)

---

This checklist is a deterministic runbook for Ubuntu-container and Debian-control-plane work.

Execution tags used in this file:

1. `[debian]` run on Debian host terminal.
2. `[ubuntu]` run inside Ubuntu container shell.
3. `[kali]` run inside Kali container shell.
4. `[windows]` run on Windows host terminal.

Lab constants used by this checklist:

1. Ubuntu target IP: `192.168.50.10`
2. Ubuntu gateway: `192.168.50.1`
3. OPNsense LAN IP: `192.168.50.1`
4. Kali subnet: `192.168.60.0/24`
5. Debian LAN-side API address: `http://192.168.50.2:5000`
6. Debian OPT1-side API address: `http://192.168.60.2:5000`

---

## Day 1 - Base Services, Log Receiver, and Attack Target

## 1. Container Startup

### 1.1 Confirm Ubuntu Container Is Running

`[debian]`:

```bash
podman ps --format "table {{.Names}}\t{{.Status}}\t{{.Networks}}"
```

Expected: `ubuntu-lab` is listed as running.

If not running, create and start it exactly:

```bash
sudo podman run -d --name ubuntu-lab --replace \
  --cap-add=NET_RAW --cap-add=NET_BIND_SERVICE \
  --network lan1 --ip 192.168.50.10 \
  ubuntu sleep infinity
```

### 1.2 Get a Shell into Ubuntu

`[debian]`:

```bash
sudo podman exec -it ubuntu-lab bash
```

### 1.3 Verify IP and Gateway

`[ubuntu]`:

```bash
ip -4 addr show eth0
ip route
```

Expected:

1. `eth0` has `192.168.50.10`.
2. default route is via `192.168.50.1`.

### 1.4 Ping OPNsense LAN

`[ubuntu]`:

```bash
ping -c 2 192.168.50.1
```

Expected: replies from `192.168.50.1`.

---

## 2. Install Base Packages

### 2.1 Update and Install

`[ubuntu]`:

```bash
apt update
apt -y upgrade
apt install -y apache2 curl rsyslog tcpdump python3 python3-venv python3-pip git jq netcat-openbsd nano
```

Expected: command completes without package dependency errors.

### 2.2 Verify Python Version

`[ubuntu]`:

```bash
python3 --version
```

Expected: Python 3.10+ is available.

---

## 3. Start Apache (Attack Target Service)

### 3.1 Start and Enable Apache

`[ubuntu]`:

```bash
service apache2 start
service apache2 status --no-pager || true
```

Expected: Apache is active.

### 3.2 Verify Apache Responds Locally

`[ubuntu]`:

```bash
curl -I http://127.0.0.1
```

Expected: HTTP status header is returned.

### 3.3 Verify Apache Responds from Kali

`[kali]`:

```bash
curl -I http://192.168.50.10
nc -zv 192.168.50.10 80
```

Expected: HTTP response and open TCP/80 check.

---

## 4. Configure rsyslog Log Receiver

### 4.1 Create rsyslog Config for OPNsense

`[ubuntu]`:

```bash
cat > /etc/rsyslog.d/10-opnsense.conf << 'EOF'
module(load="imudp")
input(type="imudp" port="514")

module(load="imtcp")
input(type="imtcp" port="5514")

if $fromhost-ip startswith '192.168.50.' or $fromhost-ip startswith '192.168.60.' then /var/log/opnsense.log
& stop
EOF
```

### 4.2 Restart rsyslog

`[ubuntu]`:

```bash
service rsyslog restart
service rsyslog status --no-pager || true
```

### 4.3 Confirm Listener Sockets Are Open

`[ubuntu]`:

```bash
ss -lunpt | grep -E '(:514|:5514)'
```

Expected: UDP 514 and/or TCP 5514 listeners are visible.

### 4.4 Create the Log File Early

`[ubuntu]`:

```bash
touch /var/log/opnsense.log
chmod 664 /var/log/opnsense.log
```

---

## 5. Day 1 Log Validation

### 5.1 Confirm OPNsense Logs Are Arriving

`[ubuntu]`:

```bash
tcpdump -ni any 'udp port 514 or tcp port 5514'
```

Generate traffic from Kali while tcpdump runs. Then stop capture with Ctrl+C.

Expected: packets from OPNsense appear.

### 5.2 Check rsyslog Is Writing to File

`[ubuntu]`:

```bash
tail -n 30 /var/log/opnsense.log
```

Expected: recent firewall/suricata entries are present.

### 5.3 Day 1 Complete Conditions

Day 1 is complete only if all are true:

1. Ubuntu container networking is correct.
2. Apache is reachable from Kali.
3. rsyslog listeners are active.
4. OPNsense logs are present in `/var/log/opnsense.log`.

#### Extra: Clean up log files

Optional reset before day 2:

```bash
: > /var/log/opnsense.log
```

---

## Day 2 - SIEM, Control API, and Dashboard

## 6. Choose and Deploy SIEM

This runbook uses Loki + Promtail + Grafana on Debian.

### 6.1 Install Podman Compose on Debian

`[debian]`:

```bash
sudo apt update
sudo apt install -y podman podman-compose
podman --version
podman-compose --version
```

### 6.2 Create Compose Directory on Debian

`[debian]`:

```bash
mkdir -p ~/lab/siem/loki ~/lab/siem/promtail ~/lab/logs
```

Ensure OPNsense log file is available to Debian runtime path:

```bash
touch ~/lab/logs/opnsense.log
```

### 6.3 Create Loki Config File

`[debian]`:

```bash
cat > ~/lab/siem/loki/loki-config.yaml << 'EOF'
auth_enabled: false

server:
  http_listen_port: 3100

ingester:
  lifecycler:
    address: 127.0.0.1
    ring:
      kvstore:
        store: inmemory
      replication_factor: 1
    final_sleep: 0s
  chunk_idle_period: 5m
  chunk_retain_period: 30s

schema_config:
  configs:
    - from: 2024-01-01
      store: boltdb-shipper
      object_store: filesystem
      schema: v13
      index:
        prefix: index_
        period: 24h

storage_config:
  boltdb_shipper:
    active_index_directory: /loki/index
    cache_location: /loki/cache
  filesystem:
    directory: /loki/chunks

limits_config:
  enforce_metric_name: false
  reject_old_samples: true
  reject_old_samples_max_age: 168h

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
cat > ~/lab/siem/promtail/promtail-config.yaml << 'EOF'
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
          host: debian
          __path__: /var/log/opnsense.log
EOF
```

### 6.5 Create Docker Compose File

`[debian]`:

```bash
cat > ~/lab/siem/compose.yaml << 'EOF'
services:
  loki:
    image: grafana/loki:2.9.8
    container_name: loki
    command: -config.file=/etc/loki/local-config.yaml
    volumes:
      - ./loki/loki-config.yaml:/etc/loki/local-config.yaml:ro
      - ./loki/data:/loki
    ports:
      - "3100:3100"

  promtail:
    image: grafana/promtail:2.9.8
    container_name: promtail
    command: -config.file=/etc/promtail/config.yaml
    volumes:
      - ./promtail/promtail-config.yaml:/etc/promtail/config.yaml:ro
      - ~/lab/logs/opnsense.log:/var/log/opnsense.log:ro
    depends_on:
      - loki

  grafana:
    image: grafana/grafana:11.0.0
    container_name: grafana
    environment:
      - GF_SECURITY_ADMIN_USER=admin
      - GF_SECURITY_ADMIN_PASSWORD=admin
    volumes:
      - ./grafana-data:/var/lib/grafana
    ports:
      - "3000:3000"
    depends_on:
      - loki
EOF
```

### 6.6 Start the SIEM Stack

`[debian]`:

```bash
cd ~/lab/siem
podman-compose up -d
podman ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
```

Expected: `loki`, `promtail`, `grafana` are running.

#### if Loki fails with permission errors

`[debian]`:

```bash
mkdir -p ~/lab/siem/loki/data ~/lab/siem/grafana-data
chmod -R 777 ~/lab/siem/loki/data ~/lab/siem/grafana-data
podman-compose down
podman-compose up -d
```

### 6.7 Access Grafana

Open `http://192.168.50.2:3000` and log in with `admin/admin`.

### 6.8 Add Loki Data Source in Grafana

1. Open **Connections > Data Sources > Add data source**.
2. Select Loki.
3. URL: `http://loki:3100`.
4. Save and test.

Expected: data source test is successful.

### 6.9 Create a Basic Log Dashboard in Grafana

1. Add a panel with Loki query `{job="opnsense"}`.
2. Set visualization to logs.
3. Save dashboard.

Expected: firewall logs appear when traffic is generated.

---

## 7. Deploy the Debian Control Plane

### 7.1 Copy the Real Control API Files to Debian

`[debian]` detect repo path automatically and copy canonical files.

```bash
REPO_SYNC=""
for p in /media/sf_Debian-NGFW "$HOME/Desktop/test" /mnt/hgfs/Debian-NGFW; do
  if [ -d "$p/control-api" ] && [ -d "$p/kali-scenarios" ]; then
    REPO_SYNC="$p"
    break
  fi
done

if [ -z "$REPO_SYNC" ]; then
  echo "Could not locate synced repo path on Debian." >&2
  exit 1
fi

echo "Using REPO_SYNC=$REPO_SYNC"
mkdir -p ~/lab/control-api/scripts ~/lab/kali-scenarios ~/lab/dashboard
cp "$REPO_SYNC/control-api/app.py" ~/lab/control-api/app.py
cp "$REPO_SYNC/control-api/requirements.txt" ~/lab/control-api/requirements.txt
cp "$REPO_SYNC/control-api/scripts/debian_smoke_test.sh" ~/lab/control-api/scripts/debian_smoke_test.sh
cp "$REPO_SYNC/kali-scenarios"/*.sh ~/lab/kali-scenarios/
cp "$REPO_SYNC/dashboard/index.html" ~/lab/dashboard/index.html
chmod +x ~/lab/control-api/scripts/*.sh ~/lab/kali-scenarios/*.sh
```

### 7.2 Copy Scenario Files into the Kali Container

`[debian]`:

```bash
sudo podman exec kali-lab mkdir -p /opt/lab/scenarios
sudo podman cp ~/lab/kali-scenarios/. kali-lab:/opt/lab/scenarios/
sudo podman exec kali-lab chmod +x /opt/lab/scenarios/*.sh
sudo podman exec kali-lab ls -la /opt/lab/scenarios
```

Expected: all scenario scripts exist and are executable in Kali container.

### 7.3 Allow the Debian API Process to Execute Podman Commands

`[debian]` add sudoers entry for non-interactive podman exec calls.

```bash
echo "$USER ALL=(root) NOPASSWD:/usr/bin/podman" | sudo tee /etc/sudoers.d/90-control-api-podman >/dev/null
sudo chmod 440 /etc/sudoers.d/90-control-api-podman
sudo visudo -cf /etc/sudoers.d/90-control-api-podman
```

Expected: visudo validation returns parsed OK.

### 7.4 Create and Start the Debian Control API

Create Python venv and install requirements:

```bash
cd ~/lab/control-api
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

Prepare secrets files (do not hardcode secrets in markdown):

```bash
mkdir -p ~/lab/secrets
chmod 700 ~/lab/secrets
```

Create API token file:

```bash
TOKEN_VALUE="$(python3 - << 'PY'
import secrets
print(secrets.token_urlsafe(48))
PY
)"

cat > ~/lab/secrets/api_token.env << EOF
TOKEN='$TOKEN_VALUE'
API_TOKEN='$TOKEN_VALUE'
EOF
chmod 600 ~/lab/secrets/api_token.env
```

Ensure OPNsense API secret file exists from OPNsense checklist section 13.5:

```bash
test -f ~/lab/secrets/opnsense_api.env && echo "opnsense_api.env found"
```

Create control API runtime env file:

```bash
cat > ~/lab/control-api/api.env << 'EOF'
KALI_CONTAINER='kali-lab'
TARGET_DEFAULT='192.168.50.10'
TARGET_PROFILE='ubuntu-apache2'
MAX_CONCURRENT_RUNS='3'
OPNSENSE_LOG_PATH="$HOME/lab/logs/opnsense.log"
TELEMETRY_EXCLUDED_IPS='192.168.50.1,192.168.50.2,192.168.60.1,192.168.60.2'
DASHBOARD_ACTION_LOG_PATH="$HOME/lab/control-api/state/dashboard_actions.log"
CORS_ALLOWED_ORIGINS='http://localhost,http://127.0.0.1,http://192.168.50.10:8888'
OPNSENSE_BAN_ALIAS_TABLE='AUTO_BAN_IPS'
OPNSENSE_KALI_ALIAS_TABLE='KALI_HOST'
OPNSENSE_API_TIMEOUT_SECONDS='4'
PODMAN_COMMAND_TIMEOUT_SECONDS='8'
OPNSENSE_API_VERIFY_TLS='false'
EOF
chmod 600 ~/lab/control-api/api.env
```

Start in foreground once for immediate validation:

```bash
set -a
source ~/lab/secrets/api_token.env
source ~/lab/secrets/opnsense_api.env
source ~/lab/control-api/api.env
set +a

cd ~/lab/control-api
source .venv/bin/activate
uvicorn app:app --host 0.0.0.0 --port 5000
```

In another terminal, validate:

```bash
curl http://127.0.0.1:5000/health
curl http://127.0.0.1:5000/config -H "X-API-Token: $TOKEN"
```

Stop foreground server with Ctrl+C after validation.

### 7.5 Run the API in the Background Without Losing the Token

`[debian]`:

```bash
set -a
source ~/lab/secrets/api_token.env
source ~/lab/secrets/opnsense_api.env
source ~/lab/control-api/api.env
set +a

cd ~/lab/control-api
source .venv/bin/activate
nohup uvicorn app:app --host 0.0.0.0 --port 5000 > ~/lab/control-api/api.log 2>&1 &
echo $! > ~/lab/control-api/api.pid
sleep 1
tail -n 20 ~/lab/control-api/api.log
```

Stop later:

```bash
kill "$(cat ~/lab/control-api/api.pid)"
```

### 7.6 Verify OPNsense REST Wiring Before Dashboard Use

`[debian]`:

```bash
set -a
source ~/lab/secrets/api_token.env
set +a

curl http://127.0.0.1:5000/config -H "X-API-Token: $TOKEN" | jq
```

Expected fields:

1. `firewall_integration_mode` is `opnsense-rest`.
2. `opnsense_api_enabled` is `true`.
3. `default_target_profile` is `ubuntu-apache2`.
4. `dashboard_action_log_path` is present.
5. `telemetry_excluded_ips` includes infra IP list.

Run hook self-test:

```bash
curl -X POST http://127.0.0.1:5000/firewall/hook-test \
  -H "X-API-Token: $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"ip":"192.168.60.222","reason":"ubuntu_preflight_hook_test"}'
```

Expected: returns `status: ok` with ban/unban mode `opnsense-rest`.

### 7.7 New Control Endpoints To Test

`[debian]`:

```bash
curl http://127.0.0.1:5000/runs -H "X-API-Token: $TOKEN"

curl -X POST http://127.0.0.1:5000/launch \
  -H "X-API-Token: $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"scenario":"tcp_syn_burst","target_ip":"192.168.50.10"}'

curl -X POST http://127.0.0.1:5000/runs/stop-all \
  -H "X-API-Token: $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"reason":"ubuntu_checklist_stop_all"}'

curl -X POST http://127.0.0.1:5000/kali/network \
  -H "X-API-Token: $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"ip":"192.168.60.20"}'
```

Expected:

1. Launch returns `run_id` and `running`.
2. stop-all returns count of stopped runs.
3. kali/network returns updated IP and sync mode.

### 7.8 Place Dashboard HTML

`[debian]` host dashboard quickly for lab use:

```bash
cd ~/lab/dashboard
nohup python3 -m http.server 8888 > ~/lab/dashboard/http.log 2>&1 &
echo $! > ~/lab/dashboard/http.pid
```

Stop later:

```bash
kill "$(cat ~/lab/dashboard/http.pid)"
```

### 7.9 Run One-Shot Debian Smoke Test

`[debian]`:

```bash
set -a
source ~/lab/secrets/api_token.env
set +a

cd ~/lab/control-api/scripts
API_TOKEN="$TOKEN" ./debian_smoke_test.sh --api-base http://127.0.0.1:5000
```

Expected: script prints pass/warn/fail summary and exits non-zero only for hard failures.

### 7.10 Manual Dashboard Action Log Workflow

`[debian]` inspect and clear action audit file:

```bash
set -a
source ~/lab/control-api/api.env
set +a

wc -l "$DASHBOARD_ACTION_LOG_PATH"
tail -n 20 "$DASHBOARD_ACTION_LOG_PATH"
```

Manual clear:

```bash
: > "$DASHBOARD_ACTION_LOG_PATH"
```

---

## 8. Test Dashboard

### 8.1 Open Dashboard in Browser

Open `http://192.168.50.2:8888`.

### 8.2 Test in Mock Mode

1. Enable Mock mode.
2. Launch one scenario in UI.
3. Validate table, counters, and charts update with mock data.

### 8.3 Test in Live Mode

1. Disable Mock mode.
2. Set API Base URL to `http://192.168.50.2:5000`.
3. Set API token value from `~/lab/secrets/api_token.env`.
4. Launch one scenario.
5. Validate run table updates and stop-all works.
6. Reassign Kali IP and verify operation succeeds.
7. Use containment ban/release and verify action log entries are appended.
8. Verify telemetry counters update and infra IP noise is excluded.

---

## Day 3 - ML Pipeline

## 9. Set Up Python ML Environment

### 9.1 Create ML Directory

`[debian]`:

```bash
REPO_SYNC=""
for p in /media/sf_Debian-NGFW "$HOME/Desktop/test" /mnt/hgfs/Debian-NGFW; do
  if [ -f "$p/ml/parse_logs.py" ]; then
    REPO_SYNC="$p"
    break
  fi
done

if [ -z "$REPO_SYNC" ]; then
  echo "Could not locate ml scripts in synced repo path." >&2
  exit 1
fi

mkdir -p ~/lab/ml
cp "$REPO_SYNC/ml"/*.py ~/lab/ml/
cp "$REPO_SYNC/ml/requirements.txt" ~/lab/ml/
cd ~/lab/ml
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### 9.2 Verify Installs

`[debian]`:

```bash
cd ~/lab/ml
source .venv/bin/activate
python -c "import pandas, numpy, sklearn, joblib; print('ml_deps_ok')"
```

---

## 10. Collect and Parse Training Data

### 10.1 Export OPNsense Log to CSV for Training

`[debian]`:

```bash
cd ~/lab/ml
source .venv/bin/activate
python parse_logs.py --log ~/lab/logs/opnsense.log --out ~/lab/ml/features.csv
wc -l ~/lab/ml/features.csv
head -n 5 ~/lab/ml/features.csv
```

### 10.2 Manually Label Rows Using run_id Log

1. Open `~/lab/ml/features.csv` in spreadsheet editor.
2. Set `label` values for known runs (for example: `benign`, `scan`, `web_attack`, `brute_force`, `flood`).
3. Save back to `~/lab/ml/features.csv`.

Expected: CSV keeps original columns and has labeled rows.

---

## 11. Train Isolation Forest

### 11.1 Create and Run Training Script

`[debian]`:

```bash
cd ~/lab/ml
source .venv/bin/activate
python train.py
ls -la ~/lab/ml/*.joblib ~/lab/ml/latest_results.json
```

Expected: model files and `latest_results.json` are created.

---

## 12. Run Inference and Write Predictions

### 12.1 Create Inference Script

This repo already ships `infer.py`. Run it directly.

`[debian]`:

```bash
cd ~/lab/ml
source .venv/bin/activate
python infer.py
```

### 12.2 Verify Predictions File

`[debian]`:

```bash
ls -la ~/lab/ml/predictions.json
head -n 20 ~/lab/ml/predictions.json
```

### 12.3 Verify ML Data Appears in Dashboard

1. Open dashboard ML tab.
2. Confirm summary cards load.
3. Confirm recent prediction rows appear.
4. Confirm no API errors in browser dev tools.

---

## 13. Day 3 Final Checks

### 13.1 Restart API with ML Data Ready

`[debian]`:

```bash
kill "$(cat ~/lab/control-api/api.pid)" || true
set -a
source ~/lab/secrets/api_token.env
source ~/lab/secrets/opnsense_api.env
source ~/lab/control-api/api.env
set +a

cd ~/lab/control-api
source .venv/bin/activate
nohup uvicorn app:app --host 0.0.0.0 --port 5000 > ~/lab/control-api/api.log 2>&1 &
echo $! > ~/lab/control-api/api.pid
```

### 13.2 Run a Final Scenario and Watch Pipeline End-to-End

`[debian]`:

```bash
set -a
source ~/lab/secrets/api_token.env
set +a

curl -X POST http://127.0.0.1:5000/launch \
  -H "X-API-Token: $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"scenario":"web_scan","target_ip":"192.168.50.10"}'
```

Expected:

1. Run appears in dashboard control tab.
2. Telemetry updates in near real time.
3. ML tab continues to load predictions summary.

---

## 14. Migration: Deploy Dashboard to Free Web Hosting

### 14.1 Prepare Cloudflare Tunnel for FastAPI (on Debian)

Optional if remote demo is required. Keep API protected and authenticated.

### 14.2 Update CORS in Control API

1. Add the hosted dashboard origin to `CORS_ALLOWED_ORIGINS` in `~/lab/control-api/api.env`.
2. Restart API.

### 14.3 Deploy Dashboard to GitHub Pages

1. Push `dashboard/index.html` to a Pages-enabled repository.
2. Enable Pages in repo settings.

### 14.4 Update API URL in the Live Dashboard

Set API Base URL in dashboard UI to your tunnel/public endpoint.

### 14.5 Alternative: Deploy to Netlify

Upload the same dashboard file and use the same API endpoint approach.

### 14.6 Security Checklist Before Going Public

1. Keep API token required.
2. Do not expose OPNsense credentials.
3. Do not expose internal log storage directly.
4. Remove temporary public endpoints after demo.

---

## 15. Ubuntu Minimum Success Checklist

You are done only when all are true:

1. Ubuntu target responds on expected service ports.
2. OPNsense logs are collected and visible in Loki/Grafana.
3. Control API starts with no runtime errors.
4. `/config` shows `opnsense-rest` integration enabled.
5. Hook test and Kali reassign operations succeed.
6. Dashboard live mode can launch/stop runs and view telemetry.
7. ML pipeline produces `latest_results.json` and `predictions.json`.
8. End-to-end final scenario can be observed in control + telemetry + ML views.
