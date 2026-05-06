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

Do not change flags, network, IP, or mount path in this baseline command if your environment already depends on it.

```bash
sudo podman run -d --name ubuntu-lab --replace --cap-add=NET_RAW --cap-add=NET_BIND_SERVICE --network lan1 --ip 192.168.50.10 -v ./10-opnsense.conf:/etc/rsyslog.d/10-opnsense.conf:ro -v ./lab/logs:/var/log -v /opt/dev/ubuntu-src:/app ubuntu-lab:custom rsyslogd -n
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
apt install -y apache2 curl rsyslog tcpdump python3 python3-venv python3-pip git jq netcat-openbsd nano \
  php php-mysqli php-gd php-xml libapache2-mod-php mariadb-server
```

Expected: command completes without package dependency errors.

### 2.2 Verify Python Version

`[ubuntu]`:

```bash
python3 --version
```

Expected: Python 3.10+ is available.

---

## 3. Start Apache and Deploy DVWA (Attack Target Service)

DVWA (Damn Vulnerable Web Application) replaces the plain Apache2 default page as the attack target. It
provides realistic web-application endpoints (SQLi, command injection, brute force, XSS, file inclusion)
that the Kali scenario scripts exploit. Apache2 is still the web server; DVWA runs on top of it.

### 3.1 Start Apache and MariaDB

`[ubuntu]`:

```bash
service mariadb start
service apache2 start
service apache2 status --no-pager || true
service mariadb status --no-pager || true
```

Expected: both services show **active (running)**.

### 3.2 Verify Apache Responds Locally

`[ubuntu]`:

```bash
curl -I http://127.0.0.1
```

Expected: HTTP status header returned.

### 3.3 Create DVWA Database and User

`[ubuntu]`:

```bash
mysql -u root << 'SQL'
CREATE DATABASE IF NOT EXISTS dvwa;
CREATE USER IF NOT EXISTS 'dvwa'@'localhost' IDENTIFIED BY 'p@ssw0rd';
GRANT ALL PRIVILEGES ON dvwa.* TO 'dvwa'@'localhost';
FLUSH PRIVILEGES;
SQL
```

Expected: no MySQL errors.

### 3.4 Clone and Configure DVWA

`[ubuntu]`:

```bash
git clone https://github.com/digininja/DVWA.git /var/www/html/dvwa
```

Write the DVWA config file:

```bash
cat > /var/www/html/dvwa/config/config.inc.php << 'EOF'
<?php
$_DVWA = array();
$_DVWA[ 'db_server' ]   = '127.0.0.1';
$_DVWA[ 'db_database' ] = 'dvwa';
$_DVWA[ 'db_user' ]     = 'dvwa';
$_DVWA[ 'db_password' ] = 'p@ssw0rd';
$_DVWA[ 'db_port']      = '3306';
$_DVWA[ 'default_security_level' ] = 'low';
$_DVWA[ 'security_level' ]         = 'low';
$_DVWA[ 'recaptcha_public_key' ]   = '';
$_DVWA[ 'recaptcha_private_key' ]  = '';
$_DVWA[ 'default_phpids_level' ]   = 'disabled';
$_DVWA[ 'default_phpids_verbose' ] = 'false';
?>
EOF
```

### 3.5 Set File Permissions

`[ubuntu]`:

```bash
chown -R www-data:www-data /var/www/html/dvwa
chmod -R 755 /var/www/html/dvwa
chmod -R 777 /var/www/html/dvwa/hackable/uploads
chmod -R 777 /var/www/html/dvwa/config
service apache2 restart
```

Expected: no errors; Apache restarts.

### 3.6 Initialize DVWA Database (Browser Step)

From your **Windows host** browser:

1. Open `http://192.168.50.10/dvwa/setup.php`
2. Scroll to the bottom and click **Create / Reset Database**.
3. DVWA redirects to the login page automatically.

Expected: green status rows for all PHP extensions; no red errors.

> **Troubleshooting:**
> - `php-xml not loaded` → run `apt install -y php-xml` then `service apache2 restart`
> - `Could not connect to database` → confirm MariaDB is running: `service mariadb status`
> - `404 on /dvwa/` → confirm the clone landed at `/var/www/html/dvwa/index.php`

### 3.7 Verify DVWA from Kali

`[kali]`:

```bash
curl -s -o /dev/null -w "%{http_code}" http://192.168.50.10/dvwa/login.php
nc -zv 192.168.50.10 80
```

Expected: HTTP `200` and TCP/80 open.

Default DVWA credentials: **admin / password** (security level: **Low**).

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
2. DVWA is accessible from Kali at `http://192.168.50.10/dvwa/login.php`.
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
          __path__: /var/log/opnsense.log
EOF
```

### 6.5 Create Docker Compose File

`[debian]`:

```bash
cat > ~/lab/siem/compose.yaml << 'EOF'
version: "3"

services:
  loki:
    image: grafana/loki:2.9.0
    user: "0:0"
    ports:
      - "3100:3100"
    volumes:
      - ./loki/loki-config.yaml:/etc/loki/local-config.yaml
      - loki_data:/loki
    command: -config.file=/etc/loki/local-config.yaml
    restart: unless-stopped

  promtail:
    image: docker.io/grafana/promtail:2.9.0
    volumes:
      - ./promtail/promtail-config.yaml:/etc/promtail/config.yml
      - /home/vbox/lab/logs/opnsense.log:/var/log/opnsense.log:ro
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
podman ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
```

Expected: `loki`, `promtail`, `grafana` are running.

#### if Loki fails with permission errors

`[debian]`:

```bash
podman-compose down
podman volume rm siem_loki_data || true
podman-compose up -d
```

### 6.7 Access Grafana

Open `http://192.168.50.2:3000`. Anonymous viewer access is enabled by default. To log in as admin use the default Grafana credentials (`admin` / `admin`) and change the password when prompted.

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
CORS_ALLOWED_ORIGINS='http://localhost,http://127.0.0.1,http://10.114.175.3:5000'
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

**What this day accomplishes:** You will teach a machine learning model what normal and attack traffic looks like based on the logs you have already collected. The pipeline has three steps: (1) parse the raw OPNsense log into a structured table, (2) train two models on that table, (3) run those models against all events and write a predictions file the dashboard reads. You do not need any ML background — just follow each step in order.

---

## 9. Set Up Python ML Environment

### 9.1 What is a virtual environment and why do we create one?

A Python virtual environment (`venv`) is an isolated folder that holds its own Python packages. It means the `pandas`, `scikit-learn`, and other ML packages you install here will not interfere with any other Python tools on the system, and they will not accidentally update something the control API depends on. Every time you want to work with the ML pipeline you first activate the venv (step 9.1), then all `python` and `pip` commands use that isolated environment.

### 9.2 Copy ML Scripts and Install Dependencies

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

What each line does:

1. The `for` loop searches known shared-folder paths to find where the repo is mounted inside Debian. It sets `REPO_SYNC` to the first one it finds. This is the same auto-detect pattern used in section 7.1.
2. `mkdir -p ~/lab/ml` creates the working directory for ML. `-p` means it will not error if it already exists.
3. The two `cp` commands copy the three Python scripts (`parse_logs.py`, `train.py`, `infer.py`) and `requirements.txt` from your repo into the ML working directory.
4. `python3 -m venv .venv` creates the virtual environment inside a hidden folder called `.venv` inside `~/lab/ml`.
5. `source .venv/bin/activate` turns on the virtual environment for this terminal session. Your prompt will change to show `(.venv)` at the start.
6. `pip install -r requirements.txt` reads the requirements file and installs: `pandas` (table manipulation), `numpy` (numbers), `scikit-learn` (the ML library), `joblib` (saving/loading trained models to disk).

This may take 2–5 minutes on first run as packages are downloaded.

Expected output ends with lines like `Successfully installed pandas-X.X numpy-X.X scikit-learn-X.X joblib-X.X`.

### 9.3 Verify Installs

`[debian]`:

```bash
cd ~/lab/ml
source .venv/bin/activate
python -c "import pandas, numpy, sklearn, joblib; print('ml_deps_ok')"
```

Expected output: `ml_deps_ok` on a single line. If you see an `ImportError`, the install failed. Re-run `pip install -r requirements.txt` inside the activated venv.

---

## 10. Collect and Parse Training Data

### 10.1 What does parse_logs.py do?

`parse_logs.py` reads every line of `/home/vbox/lab/logs/opnsense.log` and converts each line into a row of structured data. For each log line it extracts:

1. `src_ip` — the source IP address.
2. `dst_ip` — the destination IP address.
3. `dst_port` — the destination port number.
4. `proto` — TCP, UDP, or ICMP.
5. `action` — whether the packet was blocked, alerted on, or passed.
6. `signature` — the Suricata rule message if one fired, otherwise the raw line.
7. `severity` — low, medium, or high, parsed from the log line keywords.
8. `label` — set to `unknown` by the script. You will fill this in manually in the next step.

All of these rows get written to a CSV file called `features.csv`. A CSV is a spreadsheet-style text file where each row is one log event and each column is one field. This is the format that the ML training script reads.

### 10.2 Run the Parser

You need to have collected logs first. Make sure you have run at least a few attack scenarios from the dashboard before this step so that the log file has meaningful content.

`[debian]`:

```bash
cd ~/lab/ml
source .venv/bin/activate
python parse_logs.py --log ~/lab/logs/opnsense.log --out ~/lab/ml/features.csv
wc -l ~/lab/ml/features.csv
head -n 5 ~/lab/ml/features.csv
```

What each command does:

1. `python parse_logs.py --log ... --out ...` runs the parser. `--log` points it at your OPNsense log file. `--out` tells it where to write the resulting CSV.
2. `wc -l ~/lab/ml/features.csv` counts the number of lines. Expect at least a few hundred rows if you have run scenarios. The first line is a header row.
3. `head -n 5` shows the first 5 rows so you can confirm it looks correct.

Expected output from `head`:

```text
timestamp,src_ip,dst_ip,dst_port,proto,action,signature,severity,label
2026-05-06T10:00:00+00:00,192.168.60.10,192.168.50.10,80,TCP,pass,...,low,unknown
```

If the file has 1 line (only the header) the log file was empty. Go back to the dashboard, launch a scenario, let it run, then re-run this step.

### 10.3 Understand the label column and why it matters

The `label` column is your human annotation. It tells the ML model which class of traffic each row belongs to. Without labels the classifier cannot learn to distinguish attack types — it can only detect anomalies (unusual events). With labels it learns the difference between `benign`, `scan`, `web_attack`, `brute_force`, and `flood` traffic.

You know which attacks were running at which time because you launched them yourself from the dashboard. That timing knowledge is what you use to fill in the label column.

**If you have never labeled data before:** think of it like marking exam papers. Each row is an event. You are writing in the answer — what kind of traffic this row came from — based on what you know you were doing at the time.

Valid label values used by this pipeline:

1. `benign` — normal background traffic, nothing was running.
2. `scan` — a `tcp_syn_burst`, `fin_scan`, or `web_scan` scenario was active.
3. `web_attack` — `sql_injection_sim`, `command_injection_probe`, or `credential_stuffing_http` was active.
4. `brute_force` — `ssh_bruteforce_sim` was active.
5. `flood` — `udp_flood` or `icmp_flood` was active.

Rows from when nothing was running should be labeled `benign`. Rows generated during a specific scenario should be labeled with the class above. Rows you are unsure about leave as `unknown` — the training script skips `unknown` rows for the classifier but still uses them for anomaly detection.

### 10.4 Label the CSV

The most practical way to label is to use the `timestamp` column to match rows to the scenarios you ran.

Option A — edit directly in the terminal with a quick sed pass per time window (useful if you ran one scenario at a time with clear start/stop times):

```bash
# Example: mark rows between 10:05 and 10:12 as web_attack
# (adjust timestamps to match your actual run times)
cd ~/lab/ml
awk -F',' 'NR==1 {print; next}
  $1 >= "2026-05-06T10:05" && $1 <= "2026-05-06T10:12" {$9="web_attack"; print $0; next}
  {print}' OFS=',' features.csv > features_labeled.csv
mv features_labeled.csv features.csv
```

Option B — copy the file to Windows and open it in Excel or LibreOffice Calc:

```bash
# On Windows terminal (PowerShell), copy the file to desktop:
scp vbox@192.168.50.2:~/lab/ml/features.csv C:\Users\Bansi\Desktop\features.csv
```

Then open it, sort by `timestamp`, and manually type the label values in the last column. Save as CSV (not xlsx). Copy it back:

```bash
scp C:\Users\Bansi\Desktop\features.csv vbox@192.168.50.2:~/lab/ml/features.csv
```

Option C — if you want to skip labeling for now, leave all rows as `unknown`. The Isolation Forest anomaly detector will still train and work. Only the Random Forest classifier (which produces attack-type predictions) requires labels. You can label and re-train later.

After labeling, verify the distribution:

`[debian]`:

```bash
cd ~/lab/ml
source .venv/bin/activate
python -c "
import pandas as pd
df = pd.read_csv('features.csv')
print(df['label'].value_counts())
"
```

Expected: you should see your label classes printed with counts. If everything is still `unknown` and you intended to label, something went wrong with the CSV edit.

---

## 11. Train the Models

### 11.1 What train.py does — explained simply

`train.py` reads `features.csv` and trains two separate models:

#### Model 1: Isolation Forest (anomaly detector)

This model does not care about your labels at all. It learns what "normal" looks like by studying all the rows together, then identifies events that look statistically unusual. Think of it like a security guard who has watched a building for weeks and flags anything that looks out of the ordinary — they do not need to know the name of each threat, they just know it does not look normal. The result is an `anomaly_flag` (1 = normal, -1 = anomaly) and an `anomaly_score` (a number, more negative means more anomalous) for every event.

Output file: `isolation_forest.joblib` and `preprocessor.joblib`.

#### Model 2: Random Forest Classifier (attack-type classifier)

This model reads only the rows you labeled (anything not `unknown`) and learns the patterns that distinguish `benign` from `scan` from `web_attack` etc. It does need your labels. It splits your labeled data 80/20, trains on 80%, and tests on the remaining 20%, printing a classification report showing how accurately it learned each class. The more labeled rows you have and the more balanced the classes are, the better it performs.

Output file: `random_forest_pipeline.joblib`.

**If you have no labels yet:** `train.py` detects this and prints `Skipping Random Forest: no labeled data or only one class.` — this is fine. Only the Isolation Forest runs. You will still get anomaly detection working.

### 11.2 Run Training

`[debian]`:

```bash
cd ~/lab/ml
source .venv/bin/activate
python train.py
```

Training takes between 10 seconds and 2 minutes depending on how many rows are in `features.csv`. Watch the terminal output.

If you provided labels you will see a classification report like this:

```text
              precision    recall  f1-score   support
      benign       0.91      0.95      0.93        40
       flood       0.88      0.82      0.85        17
        scan       0.79      0.83      0.81        12
  web_attack       0.85      0.80      0.82        10
```

Higher numbers are better. `precision` means "of the events the model said were class X, what fraction actually were?". `recall` means "of all the actual class X events, what fraction did the model catch?". Do not worry if early numbers are low — you have limited data. The model improves with more labeled examples.

### 11.3 Verify Model Files Were Created

`[debian]`:

```bash
ls -lh ~/lab/ml/*.joblib ~/lab/ml/latest_results.json
```

Expected: you should see at minimum:

1. `preprocessor.joblib` — the data normalizer (always created).
2. `isolation_forest.joblib` — the anomaly detector (always created).
3. `latest_results.json` — summary stats the dashboard reads (always created).
4. `random_forest_pipeline.joblib` — the classifier (only if you had labels).

If any file is missing, re-run `python train.py` and read the error output carefully.

### 11.4 Inspect latest_results.json

`[debian]`:

```bash
cat ~/lab/ml/latest_results.json
```

This file is what the dashboard ML tab reads to populate the summary cards. It contains:

1. `total_scored` — how many events were scored.
2. `anomaly_pct` — what percentage of events were flagged as anomalies by the Isolation Forest.
3. `top_class` — the most common label in your dataset.
4. `distribution` — a count of each label class.
5. `trend` — currently empty (populated in a future extension).

---

## 12. Run Inference and Write Predictions

### 12.1 What infer.py does

`infer.py` loads the saved model files from disk and runs them against `features.csv` again to produce a `predictions.json` file. This file is what the dashboard reads for the row-level predictions table in the ML tab. It shows the 50 most recent events with their anomaly score, anomaly flag, predicted attack class, and confidence score.

You will re-run `infer.py` every time you collect new logs and want the dashboard to show fresh predictions. The workflow is: collect new logs → run `parse_logs.py` → run `infer.py` → dashboard refreshes automatically on next poll.

You do not need to re-run `train.py` every time — only when you have significantly more labeled data and want to retrain the models from scratch.

### 12.2 Run Inference

`[debian]`:

```bash
cd ~/lab/ml
source .venv/bin/activate
python infer.py
```

Expected output: `Inference done. 50 predictions written.`

If you see `FileNotFoundError: isolation_forest.joblib` it means training has not been run yet. Go back to section 11.2.

### 12.3 Inspect the Predictions File

`[debian]`:

```bash
cat ~/lab/ml/predictions.json | python3 -m json.tool | head -n 40
```

The `python3 -m json.tool` part pretty-prints the JSON so it is readable. You should see a list of objects, each looking like:

```json
{
  "timestamp": "2026-05-06T10:15:00+00:00",
  "src_ip": "192.168.60.10",
  "dst_ip": "192.168.50.10",
  "dst_port": 80,
  "anomaly_score": -0.0821,
  "anomaly_flag": -1,
  "predicted_class": "web_attack",
  "confidence": 0.74
}
```

What each field means:

1. `anomaly_flag: -1` means the Isolation Forest considered this event anomalous. `1` means normal.
2. `anomaly_score` — more negative = more anomalous. Values around 0.0 are borderline. Values below -0.1 are clearly anomalous in this dataset.
3. `predicted_class` — what the Random Forest classifier thinks this traffic is. Will be `unknown` if you did not label training data.
4. `confidence` — how sure the classifier is, between 0.0 and 1.0. Below 0.5 means low confidence.

### 12.4 Verify ML Data Appears in Dashboard

`[debian]` make sure the control API can reach the predictions file. The API serves ML data from `~/lab/ml/` by default:

```bash
set -a
source ~/lab/secrets/api_token.env
set +a

curl http://127.0.0.1:5000/ml/summary -H "X-API-Token: $TOKEN" | python3 -m json.tool
curl http://127.0.0.1:5000/ml/predictions?limit=5 -H "X-API-Token: $TOKEN" | python3 -m json.tool
```

Expected for `/ml/summary`: a JSON object with `total_scored`, `anomaly_pct`, `top_class`, `distribution`.

Expected for `/ml/predictions`: a JSON list of prediction objects.

If either returns `404` or an error about a missing file, the API cannot find `latest_results.json` or `predictions.json`. Check that `~/lab/ml/` contains both files and that the API process has read access to that path.

Now open the dashboard in the browser, click the **ML Analytics** tab, and confirm:

1. Summary cards show non-zero numbers.
2. The anomaly trend chart has bars.
3. The prediction distribution chart has segments.
4. The predictions table shows rows with anomaly scores and predicted classes.

If you see "No ML data" or blank cards, open browser developer tools (F12 → Network tab), reload the ML tab, and look for a failed request to `/ml/summary`. The error message in the response body will tell you what is wrong.

---

## 13. Day 3 Final Checks

### 13.1 Restart API with ML Data Ready

If the API was already running from Day 2 it does not need to be restarted — the ML endpoints read the files at request time, not at startup. However if you changed `api.env` or want a clean state:

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
sleep 1
tail -n 20 ~/lab/control-api/api.log
```

Confirm the last line of the log says `Application startup complete.` with no errors below it.

### 13.2 Run a Full End-to-End Scenario and Update Predictions

This step exercises the entire pipeline from attack launch through to ML output in one pass.

Step 1 — launch a scenario:

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

Step 2 — wait for it to complete (watch the dashboard control tab or wait ~60 seconds).

Step 3 — re-parse the updated log:

```bash
cd ~/lab/ml
source .venv/bin/activate
python parse_logs.py --log ~/lab/logs/opnsense.log --out ~/lab/ml/features.csv
```

Step 4 — re-run inference with the new rows (no need to retrain):

```bash
python infer.py
```

Step 5 — reload the dashboard ML tab. The predictions table and anomaly score chart should now include the new events from the scenario you just ran.

### 13.3 Common Problems and Fixes

**`features.csv` has only 1 line (just the header):**
The OPNsense log file is empty or was cleared. Launch scenarios from the dashboard first, wait for traffic to be generated, then run `parse_logs.py` again.

**`train.py` fails with `features.csv is empty`:**
Same root cause. The parser ran but found nothing. Check `wc -l ~/lab/logs/opnsense.log` — if it returns 0 the log is empty.

**`infer.py` fails with `FileNotFoundError`:**
Run `train.py` first. `infer.py` depends on the `.joblib` files that `train.py` creates.

**Dashboard ML tab shows "unknown" for all predicted classes:**
The Random Forest was not trained because all labels were `unknown`. Go back to section 10.3, label at least some rows, and re-run `train.py` followed by `infer.py`.

**Classification report shows very low precision/recall (below 0.5):**
Not enough labeled data, or classes are extremely imbalanced (e.g. 500 benign rows and 3 web_attack rows). Run more scenarios to collect more attack samples, label them, and retrain.

**`anomaly_pct` in the dashboard shows 0% or 100%:**
If 0%: the Isolation Forest's `contamination` parameter (set to 5% in `train.py`) is too low for your dataset — it expects anomalies to be rare. If your dataset is mostly attack traffic this will misfire. If 100%: the opposite — your dataset has almost no normal traffic. Run some benign sessions (no scenarios active) and include that data before retraining.

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
