# Kali Container Checklist

**Navigation:** [OPNsense Checklist](OPNsense_Click_By_Click_Checklist.md) | [Ubuntu Checklist](Ubuntu_Checklist.md) | [Theory Guide](NGFW_Theory_to_Action_Guide.md)

**Theory Quick Index (Most Used):**

1. [Least Privilege Segmentation (L3/L4)](NGFW_Theory_to_Action_Guide.md#3-theory-least-privilege-segmentation-l3l4)
2. [Detection Pipeline (IDS then IPS)](NGFW_Theory_to_Action_Guide.md#5-theory-detection-pipeline-ids-then-ips)
3. [Containment and Incident Response Loop](NGFW_Theory_to_Action_Guide.md#7-theory-containment-and-incident-response-loop)
4. [Safe Orchestration and Reproducibility](NGFW_Theory_to_Action_Guide.md#8-theory-safe-orchestration-and-reproducibility)
5. [Controlled Load and Stress Characterization](NGFW_Theory_to_Action_Guide.md#10-theory-controlled-load-and-stress-characterization)

---

This checklist is a deterministic runbook for Kali-side actions.

Execution tags used in this file:

1. `[debian]` run on Debian host terminal.
2. `[kali]` run inside Kali container shell.

Lab constants used by this checklist:

1. Kali default IP: `192.168.60.10`
2. Kali allowed subnet: `192.168.60.0/24`
3. Reserved Kali IPs: `192.168.60.1, 192.168.60.2`
4. Ubuntu target IP: `192.168.50.10`
5. OPNsense OPT1 gateway: `192.168.60.1`
6. Control API base URL (from Kali/OPT1 side): `http://192.168.60.2:5000`

---

## Day 1 - Setup, Tools, and IDS Trigger Traffic

## 1. Container Startup

### 1.1 Confirm Kali Container Is Running

`[debian]`:

```bash
podman ps --format "table {{.Names}}\t{{.Status}}\t{{.Networks}}"
```

Expected: `kali-lab` is listed and running.

If missing, create and start it exactly:

Do not change flags, network, IP, or mount path in this baseline command if your environment already depends on it.

```bash
sudo podman run -d --name kali-lab --replace --cap-add=NET_RAW --cap-add=NET_ADMIN --security-opt seccomp=unconfined --network opt1 --ip 192.168.60.10 -v /opt/dev/kali-src:/app kali-lab:custom sleep infinity
```

### 1.2 Get a Shell into Kali

`[debian]`:

```bash
sudo podman exec -it kali-lab bash
```

### 1.3 Verify IP and Gateway Inside Container

`[kali]`:

```bash
ip -4 addr show eth0
ip route
```

Expected:

1. `eth0` has `192.168.60.x`.
2. default route is via `192.168.60.1`.

### 1.4 Ping OPNsense OPT1

`[kali]`:

```bash
ping -c 2 192.168.60.1
```

Expected: replies received from OPT1 gateway.

---

## 2. Install Required Tools

### 2.1 Update Package List

`[kali]`:

```bash
apt update
```

### 2.2 Install Attack and Testing Tools

`[kali]`:

```bash
apt install -y nmap nikto curl netcat-openbsd hping3 hydra sqlmap tcpdump python3 python3-pip jq
```

Expected: all command-line tools are available after install.

### 2.3 Copy Scenario Scripts from the Workspace

`[debian]` copy canonical scenario scripts into Kali runtime path:

```bash
REPO_SYNC=""
for p in /media/sf_Debian-NGFW "$HOME/Desktop/test" /mnt/hgfs/Debian-NGFW; do
  if [ -d "$p/kali-scenarios" ]; then
    REPO_SYNC="$p"
    break
  fi
done

if [ -z "$REPO_SYNC" ]; then
  echo "Could not locate synced repo path on Debian." >&2
  exit 1
fi

sudo podman exec kali-lab mkdir -p /opt/lab/scenarios
sudo podman cp "$REPO_SYNC/kali-scenarios/." kali-lab:/opt/lab/scenarios/
sudo podman exec kali-lab chmod +x /opt/lab/scenarios/*.sh
```

### 2.4 Verify Scripts Exist

`[kali]`:

```bash
ls -la /opt/lab/scenarios
```

Expected: scenario scripts such as `tcp_syn_burst.sh`, `web_scan.sh`, `sql_injection_sim.sh`, `udp_flood.sh` exist and are executable.

---

## 3. Day 1 Connectivity Baseline

### 3.1 Test Allowed Ports to Ubuntu

`[kali]`:

```bash
nc -zv 192.168.50.10 22
nc -zv 192.168.50.10 80
nc -zv 192.168.50.10 443
```

Expected: only services actually running on Ubuntu return successful connection.

### 3.2 Test Blocked Ports

`[kali]`:

```bash
nc -zv 192.168.50.10 3306
nc -zv 192.168.50.10 5432
```

Expected: blocked/non-open ports fail.

### 3.3 Test Internet Egress (Should Fail)

`[kali]`:

```bash
curl -m 5 https://example.com
```

Expected: request fails due to OPT1 egress policy.

---

## 4. Day 1 Suricata IDS Trigger Traffic

### 4.1 Confirm Ubuntu Apache Is Running

`[kali]`:

```bash
curl -I http://192.168.50.10
```

Expected: HTTP headers return.

### 4.2 Run Scan-Style Traffic

`[kali]`:

```bash
nmap -sS -Pn -p 1-1000 192.168.50.10
nmap -sV -Pn 192.168.50.10
```

### 4.3 Run Web Probe Traffic

`[kali]`:

```bash
nikto -h http://192.168.50.10
```

### 4.4 Run Manual Suspicious Probes

`[kali]`:

```bash
curl "http://192.168.50.10/?id=1'"
curl "http://192.168.50.10/../../../../etc/passwd"
curl -A "sqlmap/1.0" "http://192.168.50.10/"
```

### 4.5 Verify Alerts in OPNsense

1. Open OPNsense UI: **Services > Intrusion Detection > Alerts**.
2. Filter for current Kali source IP.
3. Confirm alert rows match generated traffic.

---

## Day 2 - Control API Integration and Labeled Attack Runs

## 5. Use the FastAPI Control API

Before running this section, ensure API is running on Debian and token is available.

### 5.1 Test API Reachability

`[kali]`:

```bash
export API_BASE="http://192.168.60.2:5000"
export TOKEN="replace_with_your_api_token"

curl "$API_BASE/health"
curl "$API_BASE/config" -H "X-API-Token: $TOKEN"
```

Expected:

1. `/health` returns `status: ok`.
2. `/config` returns scenario list and integration details.

### 5.2 Test Launch Endpoint

`[kali]`:

```bash
curl -X POST "$API_BASE/launch" \
  -H "X-API-Token: $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"scenario":"tcp_syn_burst","target_ip":"192.168.50.10"}'
```

Expected: response includes `run_id` and status `running`.

### 5.3 Run Each Scenario via API

`[kali]` run each scenario once:

```bash
for s in tcp_syn_burst web_scan ssh_bruteforce_sim sql_injection_sim udp_flood icmp_flood fin_scan slow_http credential_stuffing_http command_injection_probe; do
  echo "Launching $s"
  curl -s -X POST "$API_BASE/launch" \
    -H "X-API-Token: $TOKEN" \
    -H "Content-Type: application/json" \
    -d "{\"scenario\":\"$s\",\"target_ip\":\"192.168.50.10\"}"
  echo
  sleep 1
done
```

### 5.4 Record run_id for Each Run

`[kali]`:

```bash
curl "$API_BASE/runs" -H "X-API-Token: $TOKEN" | jq
```

Expected: each launched run has a `run_id` you can track.

### 5.5 Validate Pause, Resume, and Stop-All

Pause/resume are supported for flood scenarios only.

`[kali]`:

```bash
RUN_ID="replace_with_udp_or_icmp_flood_run_id"

curl -X POST "$API_BASE/runs/$RUN_ID/pause" \
  -H "X-API-Token: $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"reason":"kali_pause_test"}'

curl -X POST "$API_BASE/runs/$RUN_ID/resume" \
  -H "X-API-Token: $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"reason":"kali_resume_test"}'

curl -X POST "$API_BASE/runs/stop-all" \
  -H "X-API-Token: $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"reason":"kali_stop_all_test"}'
```

Expected:

1. Pause returns `paused` for flood scenario runs.
2. Resume returns `running`.
3. stop-all returns number of stopped runs.

### 5.6 Validate Dynamic Kali Reassignment Path

`[kali]`:

```bash
curl -X POST "$API_BASE/kali/network" \
  -H "X-API-Token: $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"ip":"192.168.60.20","reason":"kali_reassign_test"}'
```

Then check network state:

```bash
ip -4 addr show eth0
ip route
```

Expected:

1. Kali IP changes to requested value.
2. Default route remains `192.168.60.1`.
3. OPNsense logs now show the new source IP.

### 5.7 Validate Updated Telemetry and Ban UX from Live Traffic

1. Open dashboard Telemetry tab in browser.
2. Confirm quick counters show Alerts, Blocked, Banned Drops, High Sev, Flows.
3. Apply one ban to current Kali source IP.
4. Generate traffic while banned:

`[kali]`:

```bash
hping3 -S -p 80 -c 50 192.168.50.10
curl -m 2 http://192.168.50.10/ || true
```

Expected:

1. `Banned Drops` increases.
2. Ban row can be released and fades after release.

---

## 6. Manual Labeled Attack Runs

Goal: create clean, label-aware attack evidence for ML.

### 6.1 TCP SYN Burst

`[kali]`:

```bash
RUN_ID="manual-$(date +%s)-syn"
LABEL="flood"
TARGET_IP="192.168.50.10"
/opt/lab/scenarios/tcp_syn_burst.sh "$RUN_ID"
```

### 6.2 Web Attack

`[kali]`:

```bash
RUN_ID="manual-$(date +%s)-web"
LABEL="web_attack"
TARGET_IP="192.168.50.10"
/opt/lab/scenarios/web_scan.sh "$RUN_ID"
```

### 6.3 SSH Brute Force

`[kali]`:

```bash
RUN_ID="manual-$(date +%s)-ssh"
LABEL="brute_force"
TARGET_IP="192.168.50.10"
/opt/lab/scenarios/ssh_bruteforce_sim.sh "$RUN_ID"
```

### 6.4 SQL Injection

`[kali]`:

```bash
RUN_ID="manual-$(date +%s)-sqli"
LABEL="web_attack"
TARGET_IP="192.168.50.10"
/opt/lab/scenarios/sql_injection_sim.sh "$RUN_ID"
```

Keep a separate label note file on Debian mapping `RUN_ID -> LABEL`.

---

## Day 3 - TRex Traffic Generation

## 7. TRex on Debian (Recommended Path)

TRex is recommended on Debian host, not inside Kali container.

### 7.1 Copy 3-Level TRex Profiles to Debian Runtime Path

`[debian]`:

```bash
sudo mkdir -p /opt/trex/profiles
sudo cp ~/lab/kali-scenarios/trex-profiles/*.py /opt/trex/profiles/
sudo cp ~/lab/kali-scenarios/trex-profiles/run_trex_3_levels.sh /opt/trex/profiles/
sudo chmod +x /opt/trex/profiles/run_trex_3_levels.sh
ls -la /opt/trex/profiles/
```

### 7.2 Install TRex on Debian

`[debian]`:

```bash
cd /opt
sudo mkdir -p trex
cd trex
sudo wget --no-check-certificate https://trex-tgn.cisco.com/trex/release/latest
sudo tar -xzf latest
ls -la /opt/trex/
```

### 7.3 Confirm TRex Can See Network Interfaces

`[debian]`:

```bash
sudo /opt/trex/v3.*/dpdk_setup_ports.py --show
```

### 7.4 Run the 3 Levels Sequentially

`[debian]`:

```bash
cd /opt/trex/profiles
sudo ./run_trex_3_levels.sh
```

### 7.5 Run Per-Level Manually (Optional)

`[debian]`:

```bash
cd /opt/trex/v3.*
sudo ./t-rex-64 -f /opt/trex/profiles/level1_baseline.py -d 30 -m 1 --no-watchdog --software -t src=192.168.60.10,dst=192.168.50.10
sudo ./t-rex-64 -f /opt/trex/profiles/level2_pressure.py -d 30 -m 1 --no-watchdog --software -t src=192.168.60.10,dst=192.168.50.10
sudo ./t-rex-64 -f /opt/trex/profiles/level3_surge.py -d 15 -m 1 --no-watchdog --software -t src=192.168.60.10,dst=192.168.50.10
```

### 7.6 Alternative: hping3 Repeatable Traffic from Kali

If TRex is unavailable in your environment, use:

`[kali]`:

```bash
hping3 -S -p 80 --flood 192.168.50.10
```

Use short controlled durations and stop with Ctrl+C.

---

## 8. Day 3 Final Labeled Runs for ML Training Data

### 8.1 Run All Scenarios Once More in Sequence

`[kali]`:

```bash
for s in tcp_syn_burst web_scan ssh_bruteforce_sim sql_injection_sim udp_flood icmp_flood fin_scan slow_http credential_stuffing_http command_injection_probe; do
  RUN_ID="final-$(date +%s)-$s"
  echo "run_id=$RUN_ID scenario=$s" | tee -a ~/final_run_ids.log
  TARGET_IP="192.168.50.10" /opt/lab/scenarios/$s.sh "$RUN_ID"
done
```

### 8.2 Record the Run Log

`[kali]`:

```bash
tail -n 50 ~/final_run_ids.log
```

Also export API-side run view:

```bash
curl "$API_BASE/runs" -H "X-API-Token: $TOKEN" | jq
```

---

## 9. Verification Checklist for Kali Side

Kali side is complete only if all are true:

1. Kali container networking and gateway are correct.
2. Required tools are installed.
3. Scenario scripts are present and executable in `/opt/lab/scenarios`.
4. Connectivity baseline behaves as expected (allowed and blocked paths).
5. Suricata-trigger traffic produces alerts in OPNsense.
6. API launch and run management endpoints work.
7. Flood scenarios support pause/resume and stop-all works.
8. Kali reassignment works within `192.168.60.0/24` and stays off reserved IPs.
9. Ban/release behavior is visible in dashboard telemetry.
10. Final labeled run set is captured for ML workflow.
