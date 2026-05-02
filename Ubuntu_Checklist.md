# Ubuntu Container Checklist

**Navigation:** [OPNsense Checklist](OPNsense_Click_By_Click_Checklist.md) | [Kali Checklist](Kali_Checklist.md) | [Lab Guide](NGFW_3Day_Lab_Guide.md)

---

This checklist covers everything done on or from the Ubuntu container and the Debian control plane: target services, log receiver, SIEM, ML pipeline, Debian-hosted control API, and the Debian-hosted dashboard.

Lab context:

1. Ubuntu runs as a Podman container on Debian.
2. Ubuntu IP = 192.168.50.10.
3. Gateway = 192.168.50.1 (OPNsense LAN).
4. Debian host has 4 vCPU, 4 GB RAM, 40 GB storage.
5. Commands prefixed with `[debian]` are run on the Debian host. All others are inside the Ubuntu container.
6. Current architecture: Debian is the control plane. Ubuntu is primarily the target, log receiver, and ML execution environment.

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

compactor:
  working_directory: /loki/compactor
  shared_store: filesystem
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
          __path__: /var/log/opnsense.log
EOF
```
<!--
- **📌 Small Detour: what I broke — Promtail Path (Critical)**
  - **Rule:** Use **container path**, not host path in `promtail-config.yaml`.
  - **❌ Incorrect:** `__path__: /home/vbox/logs/opnsense.log`
  - **✅ Correct:** `__path__: /var/log/opnsense.log`
  - **Why:** Promtail runs inside the container. The host file `/home/vbox/logs/opnsense.log` is mounted to `/var/log/opnsense.log`, so only the container path is visible.
  - **Symptom if wrong:** “No labels received” in Grafana; Promtail logs show the host path.
  - **Fix:** `podman-compose down && podman-compose up -d`
-->

<div style="border: 1px solid var(--vscode-widget-border, #cbd5e1); background: var(--vscode-editor-background, #f8fafc); color: var(--vscode-editor-foreground, #0f172a); padding: 14px; border-radius: 8px; margin: 16px 0; font-family: inherit;">
  <div style="font-weight: 600; margin-bottom: 8px;">📌 Small Detour: What I broke — Promtail Path (Critical)</div>
  <div style="margin-bottom: 8px;"><strong>Rule:</strong> Use <strong>container path</strong>, not host path.</div>
  <div style="margin-bottom: 4px;"><strong>❌ Incorrect</strong></div>
  <pre style="background: var(--vscode-editor-selectionBackground, #e2e8f0); padding: 8px; border-radius: 4px; overflow-x: auto;"><code>__path__: /home/vbox/logs/opnsense.log</code></pre>
  <div style="margin: 8px 0 4px;"><strong>✅ Correct</strong></div>
  <pre style="background: var(--vscode-editor-selectionBackground, #e2e8f0); padding: 8px; border-radius: 4px; overflow-x: auto;"><code>__path__: /var/log/opnsense.log</code></pre>
  <div style="margin: 8px 0 4px;"><strong>Why</strong></div>
  <ul style="margin: 4px 0; padding-left: 20px;">
    <li>Promtail runs inside a container</li>
    <li>File is mounted: <code>/home/vbox/logs/opnsense.log</code> → <code>/var/log/opnsense.log</code></li>
    <li>Only the container path is visible to Promtail</li>
  </ul>
  <div style="margin: 8px 0 4px;"><strong>Symptom if wrong</strong></div>
  <ul style="margin: 4px 0; padding-left: 20px;">
    <li>“No labels received” in Grafana</li>
    <li>Promtail logs show host path instead of <code>/var/log/...</code></li>
  </ul>
  <div style="margin: 8px 0 4px;"><strong>Fix action</strong></div>
  <pre style="background: var(--vscode-editor-selectionBackground, #e2e8f0); padding: 8px; border-radius: 4px; overflow-x: auto;"><code>podman-compose down
podman-compose up -d</code></pre>
</div>

### 6.5 Create Docker Compose File

`[debian]`:

```bash
cat > docker-compose.yml << 'EOF'
version: "3"

services:
  loki:
    image: grafana/loki:2.9.0
    user: "0:0"
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

#### if Loki fails with permission errors

```bash
podman logs siem_loki_1
# ctrl+C immediately, then check if its volume ownership issue, then proceed with this
podman-compose down
rm -rf ~/.local/share/containers/storage/volumes/<project>_loki_data
podman-compose up -d
```

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

## 7. Deploy the Debian Control Plane

The control API and the dashboard now live on Debian, not inside the Ubuntu container. Ubuntu stays the target, log receiver, and ML execution node.

### 7.1 Copy the Real Control API Files to Debian

The canonical files are now in the workspace:

1. `control-api/app.py`
2. `control-api/requirements.txt`
3. `kali-scenarios/*.sh`

If you use a VirtualBox shared folder, copy them from the shared mount into Debian.

`[debian]`:

```bash
mkdir -p ~/lab/control-api ~/lab/kali-scenarios
cp /path/to/shared/test/control-api/app.py ~/lab/control-api/app.py
cp /path/to/shared/test/control-api/requirements.txt ~/lab/control-api/requirements.txt
cp /path/to/shared/test/kali-scenarios/*.sh ~/lab/kali-scenarios/
chmod +x ~/lab/kali-scenarios/*.sh
```

If you do not use a shared folder, use `scp`, Git, or paste the files manually.

### 7.2 Copy Scenario Files into the Kali Container

`[debian]`:

```bash
sudo podman exec kali-lab mkdir -p /opt/lab/scenarios
for file in ~/lab/kali-scenarios/*.sh; do
  sudo podman cp "$file" kali-lab:/opt/lab/scenarios/
done
sudo podman exec kali-lab chmod +x /opt/lab/scenarios/*.sh
sudo podman exec kali-lab ls -la /opt/lab/scenarios
```

Expected: the copied scripts include the original four plus the extended set such as `udp_flood.sh`, `icmp_flood.sh`, `fin_scan.sh`, and `slow_http.sh`.

### 7.3 Allow the Debian API Process to Execute Podman Commands

Because your Kali and Ubuntu containers are managed with `sudo podman`, the API user on Debian needs passwordless access for the exact Podman exec path used by the API.

`[debian]`:

```bash
sudo visudo
```

Add a rule like this for your Debian user:

```text
vbox ALL=(root) NOPASSWD:/usr/bin/podman exec *
```

If your Podman binary lives elsewhere, correct the path with:

```bash
command -v podman
```

### 7.4 Create and Start the Debian Control API

`[debian]`:

```bash
cd ~/lab/control-api
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

Set the required runtime variables. This removes the old fallback-token confusion and makes the log path explicit.

`[debian]`:

```bash
export TOKEN='replace_with_a_long_random_token'
# export TOKEN='RamyaBinduBansiDurbadalSirToken2022-2026'
export API_TOKEN="$TOKEN"
export KALI_CONTAINER='kali-lab'
export SSH_USER='root'
export TARGET_DEFAULT='192.168.50.10'
export MAX_CONCURRENT_RUNS='3'
export OPNSENSE_LOG_PATH="$HOME/logs/opnsense.log"
export CORS_ALLOWED_ORIGINS='http://localhost,http://127.0.0.1'
export KALI_IP_ASSIGN_CMD='echo assign $KALI_IP inside Kali here'
uvicorn app:app --host 0.0.0.0 --port 5000
```

Notes:

1. `MAX_CONCURRENT_RUNS` limits how many attacks can run at once from the dashboard or API. Start with `3` unless you have already verified the host can handle more.
2. `KALI_IP_ASSIGN_CMD` is optional. Without it, the API falls back to `sudo podman exec kali-lab ... ip addr ...` inside the Kali container.
3. Valid dashboard-assigned Kali addresses must stay inside `192.168.60.0/24`. `192.168.60.1` and `192.168.60.2` stay reserved.

Test it locally from a second terminal before backgrounding it:

`[debian]`:

```bash
curl http://127.0.0.1:5000/runs \
  -H "X-API-Token: $TOKEN"
```

Expected: `{"runs": []}`.

### 7.5 Run the API in the Background Without Losing the Token

Do not start a second `uvicorn` process without the environment variables. That was the source of the earlier token confusion.

`[debian]`:

```bash
pkill -f "uvicorn app:app" || true
cd ~/lab/control-api
source .venv/bin/activate
nohup env \
  API_TOKEN="$TOKEN" \
  KALI_CONTAINER="$KALI_CONTAINER" \
  SSH_USER="$SSH_USER" \
  TARGET_DEFAULT="$TARGET_DEFAULT" \
  MAX_CONCURRENT_RUNS="$MAX_CONCURRENT_RUNS" \
  OPNSENSE_LOG_PATH="$OPNSENSE_LOG_PATH" \
  CORS_ALLOWED_ORIGINS="$CORS_ALLOWED_ORIGINS" \
  KALI_IP_ASSIGN_CMD="$KALI_IP_ASSIGN_CMD" \
  uvicorn app:app --host 0.0.0.0 --port 5000 > ~/lab/control-api/api.log 2>&1 &
echo $! > ~/lab/control-api/api.pid
```

To stop it later:

`[debian]`:

```bash
kill $(cat ~/lab/control-api/api.pid)
```

### 7.6 Optional Firewall Hooks for Progressive Bans

The new API supports `/firewall/ban`, `/firewall/unban`, and automatic expiry. To make those buttons actually change OPNsense, wire the API to either an OPNsense API call or an SSH helper script.

Example pattern:

`[debian]`:

```bash
export FIREWALL_BAN_CMD='echo add $BAN_IP to OPNsense alias here'
export FIREWALL_UNBAN_CMD='echo remove $BAN_IP from OPNsense alias here'
```

Until you replace those placeholders with a real OPNsense integration, the dashboard still tracks bans in record-only mode.

### 7.7 New Control Endpoints To Test

The current control API also exposes:

1. `POST /runs/stop-all` for the dashboard master stop button.
2. `GET /kali/network` to show the currently assigned Kali address and reserved addresses.
3. `POST /kali/network` to reassign Kali inside `192.168.60.0/24`.

Quick checks:

`[debian]`:

```bash
curl http://127.0.0.1:5000/kali/network \
  -H "X-API-Token: $TOKEN"
```

```bash
curl -X POST http://127.0.0.1:5000/runs/stop-all \
  -H "X-API-Token: $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"reason":"manual_test"}'
```

If you want the dashboard to change Kali's IP directly, replace the placeholder `KALI_IP_ASSIGN_CMD` or let the default `podman exec` path handle it.

### 7.8 Place Dashboard HTML

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
podman cp ~/Desktop/test/dashboard/index.html ubuntu-lab:/root/lab/dashboard/
podman exec ubuntu-lab bash -c "cd /root/lab/dashboard && python3 -m http.server 8888 &"
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

1. Enter API Base URL = `http://<Debian-IP>:5000`.
2. Enter API Token = the token you set.
3. Turn off Mock Mode.
4. Click Attack Control tab.
5. Expand an attack row, set the shared target IP if needed, and click Launch on one or more rows.
6. Expected: runs appear in the Active And Recent Runs table with status `running` while live and later transition to `completed` or `failed` automatically.
7. Verify the dashboard blocks new launches once the `MAX_CONCURRENT_RUNS` cap is reached.
8. Use the row stop action and the master stop button to verify both kill-switch paths.
9. Use the Kali network panel to test reassignment inside `192.168.60.0/24`.
10. If you readdress Kali, update any OPNsense aliases that were pinned to the old source IP.
11. Use the firewall controls to test 1 hour, 5 hour, 10 hour, and 24 hour progressive bans.

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

Prefer using the canonical workspace files under `ml/` now:

1. `ml/parse_logs.py`
2. `ml/train.py`
3. `ml/infer.py`
4. `ml/requirements.txt`

Copy them to Debian or Ubuntu the same way you copied the control API files.

### 9.2 Verify Installs

```bash
python3 -c "import sklearn; print(sklearn.__version__)"
```

Expected: version number printed.

---

## 10. Collect and Parse Training Data

### 10.1 Export OPNsense Log to CSV for Training

The older inline parser hardcoded source and destination IPs. Use the standalone `ml/parse_logs.py` file instead, because it extracts IPs, ports, protocol, and action dynamically from the log lines.

```bash
source .venv/bin/activate
python3 ~/lab/ml/parse_logs.py --log ~/logs/opnsense.log --out ~/lab/ml/features.csv
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

Use the standalone `ml/train.py` file from the workspace. It no longer assumes a single attacker IP and includes `src_ip` and `dst_ip` as categorical features.

```bash
source .venv/bin/activate
python3 ~/lab/ml/train.py
```

---

## 12. Run Inference and Write Predictions

### 12.1 Create Inference Script

Use the standalone `ml/infer.py` file from the workspace. It preserves the parsed source and destination IPs instead of replacing them with fixed values.

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
nohup env \
  API_TOKEN="$TOKEN" \
  KALI_CONTAINER="$KALI_CONTAINER" \
  SSH_USER="$SSH_USER" \
  TARGET_DEFAULT="$TARGET_DEFAULT" \
  OPNSENSE_LOG_PATH="$OPNSENSE_LOG_PATH" \
  CORS_ALLOWED_ORIGINS="$CORS_ALLOWED_ORIGINS" \
  uvicorn app:app --host 0.0.0.0 --port 5000 > api.log 2>&1 &
echo $! > api.pid
```

### 13.2 Run a Final Scenario and Watch Pipeline End-to-End

From Kali:

```bash
curl -X POST http://<Debian-IP>:5000/launch \
  -H "X-API-Token: $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"scenario":"web_scan","target_ip":"192.168.50.10"}'
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

# Start a quick tunnel to the control API on Debian (port 5000)
cloudflared tunnel --url http://127.0.0.1:5000
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

---
---

## Appendix

### Appendix 1

<div style="border: 1px solid var(--vscode-widget-border, #cbd5e1); background: var(--vscode-editor-background, #f8fafc); color: var(--vscode-editor-foreground, #0f172a); padding: 14px; border-radius: 8px; margin: 16px 0; font-family: inherit;">
  <div style="font-weight: 600; margin-bottom: 8px;">📌 Small Detour: The "Quote Trap" — Shell vs. Python Syntax</div>
  <div style="margin-bottom: 8px;"><strong>Context:</strong> When writing Python files from Fish/Bash using <code>bash -c</code>, you are nesting three layers of syntax: <strong>Fish → Bash → Python</strong>. Mismanaging quotes causes silent failures or syntax errors.</div>
  
  <div style="margin: 12px 0 4px;"><strong>1. The Golden Rule: Use Double Quotes for the Outer Wrapper</strong></div>
  <div style="margin-bottom: 4px;">Wrap your entire <code>bash -c</code> command in double quotes (<code>"..."</code>). This allows single quotes (<code>'</code>) to exist freely inside your Python code without escaping.</div>
  <pre style="background: var(--vscode-editor-selectionBackground, #e2e8f0); padding: 8px; border-radius: 4px; overflow-x: auto;"><code>bash -c "cat > app.py << 'PYEOF'
# Single quotes are safe here!
msg = 'Hello World'
print(msg)
PYEOF"</code></pre>

  <div style="margin: 12px 0 4px;"><strong>2. Handling Double Quotes in Python</strong></div>
  <div style="margin-bottom: 4px;">If your Python code requires double quotes (e.g., <code>print("Hi")</code>), you must escape them with a backslash (<code>\</code>) because the outer shell wrapper is using double quotes.</div>
  <pre style="background: var(--vscode-editor-selectionBackground, #e2e8f0); padding: 8px; border-radius: 4px; overflow-x: auto;"><code>bash -c "cat > app.py << 'PYEOF'
# Escape internal double quotes
print(\"It works!\")
PYEOF"</code></pre>

  <div style="margin: 12px 0 4px;"><strong>3. The "Quote Sandwich" (Advanced/POSIX Standard)</strong></div>
  <div style="margin-bottom: 4px;">If you must use single quotes for the outer wrapper, you cannot simply use <code>\'</code> inside. You must use the <code>'\''</code> sequence to "pause" quoting, insert a literal quote, and resume.</div>
  <ul style="margin: 4px 0; padding-left: 20px;">
    <li><code>'</code> : End current single-quoted string.</li>
    <li><code>\'</code> : Insert a literal single quote.</li>
    <li><code>'</code> : Start new single-quoted string.</li>
  </ul>
  <pre style="background: var(--vscode-editor-selectionBackground, #e2e8f0); padding: 8px; border-radius: 4px; overflow-x: auto;"><code># Complex but 100% reliable
bash -c 'echo '\''It'\''s working'\'''</code></pre>

  <div style="margin: 12px 0 4px;"><strong>❌ Common Pitfall: The "Simple" Backslash</strong></div>
  <div style="margin-bottom: 4px;">Using <code>\'</code> inside a single-quoted <code>bash -c</code> string is unreliable in Fish/Bash. It may work for simple words but fails when quotes are nested or used as delimiters (like in Heredocs).</div>
  <pre style="background: var(--vscode-editor-selectionBackground, #e2e8f0); padding: 8px; border-radius: 4px; overflow-x: auto;"><code># ⚠️ Risky: May break if internal quotes exist
bash -c 'cat > app.py << \'PYEOF\' ... PYEOF'</code></pre>

  <div style="margin: 12px 0 4px;"><strong>💡 Recommendation</strong></div>
  <ul style="margin: 4px 0; padding-left: 20px;">
    <li><strong>For small snippets:</strong> Use <code>bash -c "..."</code> (Double Quote Wrapper).</li>
    <li><strong>For complex files:</strong> Use <code>nano app.py</code> or <code>vim app.py</code> to avoid shell quoting entirely.</li>
    <li><strong>For automation scripts:</strong> Use the <code>'\''</code> method for maximum POSIX compatibility.</li>
  </ul>
</div>