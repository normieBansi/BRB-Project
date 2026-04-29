# Kali Container Checklist

**Navigation:** [OPNsense Checklist](OPNsense_Click_By_Click_Checklist.md) | [Ubuntu Checklist](Ubuntu_Checklist.md) | [Lab Guide](NGFW_3Day_Lab_Guide.md)

---

This checklist covers everything done on or from the Kali container. Kali is the attacker and traffic simulation node.

Lab context:

1. Kali runs as a Podman container on Debian.
2. Kali IP = 192.168.60.10.
3. Gateway = 192.168.60.1 (OPNsense OPT1).
4. Target = Ubuntu at 192.168.50.10.
5. Commands prefixed with `[debian]` are run on the Debian host. All others are run inside the Kali container.
6. Current architecture: Debian hosts the main dashboard and the control API at `http://<Debian-IP>:5000`.

---

## Day 1 - Setup, Tools, and IDS Trigger Traffic

## 1. Container Startup

### 1.1 Confirm Kali Container Is Running

On Debian:

```bash
podman ps
```

Expected: a container for Kali is listed as Up.

If not running, start it:

```bash
sudo podman run -it --name kali-lab --replace --cap-add=NET_RAW --cap-add=NET_ADMIN --security-opt seccomp=unconfined --network opt1 --ip 192.168.60.10 kalilinux/kali-rolling
```

Replace `kali` with your actual container name if different.

### 1.2 Get a Shell into Kali

```bash
sudo podman exec -it kali-lab bash
```

Replace `kali-lab` if your container name is different. All following commands in this file are run from inside this shell unless marked `[debian]`.

### 1.3 Verify IP and Gateway Inside Container

```bash
ip a
ip route
```

Expected:

1. An interface with 192.168.60.10 is present.
2. Default route via 192.168.60.1 is shown.

If IP or gateway is wrong, fix the Podman network assignment and restart the container before continuing.

### 1.4 Ping OPNsense OPT1

```bash
ping -c 2 192.168.60.1
```

Expected: replies from 192.168.60.1.

If this fails, stop. Fix the network before anything else.

---

## 2. Install Required Tools

### 2.1 Update Package List

```bash
apt update
```

### 2.2 Install Attack and Testing Tools

```bash
apt install -y nmap nikto curl netcat-openbsd hping3 hydra sqlmap tcpdump python3 python3-pip
```

Why each tool is needed:

1. nmap: port and service scanning, generates scan signatures in Suricata.
2. nikto: web vulnerability scanner, triggers web attack signatures.
3. curl: HTTP probing, can send custom headers and payloads.
4. netcat: raw TCP/UDP connectivity testing.
5. hping3: custom packet crafting, used for SYN burst traffic.
6. hydra: SSH brute force simulation.
7. sqlmap: SQL injection testing, generates known SQLi signatures.
8. tcpdump: local packet capture for verification.
9. python3/pip: needed for scripted traffic generation and TRex support.

### 2.3 Copy Scenario Scripts from the Workspace

The canonical scenario files are now in the workspace under `kali-scenarios/` and are copied into the Kali container from Debian.

`[debian]`:

```bash
sudo podman exec kali-lab mkdir -p /opt/lab/scenarios
for file in ~/lab/kali-scenarios/*.sh; do
  sudo podman cp "$file" kali-lab:/opt/lab/scenarios/
done
sudo podman exec kali-lab chmod +x /opt/lab/scenarios/*.sh
```

### 2.4 Verify Scripts Exist

```bash
ls -la /opt/lab/scenarios/
```

Expected: executable scripts including:

1. `tcp_syn_burst.sh`
2. `web_scan.sh`
3. `ssh_bruteforce_sim.sh`
4. `sql_injection_sim.sh`
5. `udp_flood.sh`
6. `icmp_flood.sh`
7. `fin_scan.sh`
8. `slow_http.sh`

Note: `ssh_bruteforce_sim.sh` now defaults to `SSH_USER=root`, which matches your current Ubuntu container usage.

---

## 3. Day 1 Connectivity Baseline

### 3.1 Test Allowed Ports to Ubuntu

```bash
nc -zv 192.168.50.10 22
nc -zv 192.168.50.10 80
nc -zv 192.168.50.10 443
nc -zv 192.168.50.10 5000
nc -zv 192.168.50.10 8080
```

Expected: ports with a listening service succeed. Others may refuse (service not running) or time out (blocked by firewall).

### 3.2 Test Blocked Ports

```bash
nc -zv 192.168.50.10 21
nc -zv 192.168.50.10 25
nc -zv 192.168.50.10 3306
```

Expected: these fail. If they connect, check OPNsense OPT1 rules.

### 3.3 Test Internet Egress (Should Fail)

```bash
curl -m 5 https://example.com
ping -c 2 1.1.1.1
```

Expected: both fail. If they succeed, check OPNsense OPT1 egress block rules.

---

## 4. Day 1 Suricata IDS Trigger Traffic

Run these after OPNsense Suricata is configured and running in IDS mode.

### 4.1 Confirm Ubuntu Apache Is Running

```bash
curl -I http://192.168.50.10
nc -zv 192.168.50.10 80
```

Expected: HTTP headers returned, port 80 connects.

If this fails, go to [Ubuntu Checklist](Ubuntu_Checklist.md) step 3 and start Apache first.

### 4.2 Run Scan-Style Traffic

```bash
nmap -sS -Pn -p 1-1000 192.168.50.10
```

Wait for completion.

```bash
nmap -sV -Pn 192.168.50.10
```

Wait for completion.

### 4.3 Run Web Probe Traffic

```bash
nikto -h http://192.168.50.10
```

Expected: nikto runs multiple probes. At least some should trigger Suricata signatures.

### 4.4 Run Manual Suspicious Probes

```bash
curl "http://192.168.50.10/?id=1'"
curl "http://192.168.50.10/../../../../etc/passwd"
curl -A "sqlmap/1.0" "http://192.168.50.10/"
curl "http://192.168.50.10/?q=UNION+SELECT+null,null--"
```

### 4.5 Verify Alerts in OPNsense

After running the above:

1. Open OPNsense > Services > Intrusion Detection > Alerts.
2. Sort by newest first.
3. Confirm alerts show source 192.168.60.10 and destination 192.168.50.10.

Minimum: at least one alert must appear for Day 1 to be complete.

---

## Day 2 - Control API Integration and Labeled Attack Runs

## 5. Use the FastAPI Control API

Prerequisite: the Debian control plane in the Ubuntu checklist section 7 must be done. The control API must be running on Debian at port 5000.

### 5.1 Test API Reachability

```bash
curl -m 5 http://<Debian-IP>:5000/docs
```

Expected: returns some JSON or HTML response. If it times out, check the Debian control API service.

### 5.2 Test Launch Endpoint

Replace `your_token_here` with the API token from Ubuntu checklist.

```bash
curl -X POST http://<Debian-IP>:5000/launch \
  -H "Content-Type: application/json" \
  -H "X-API-Token: your_token_here" \
  -d '{"scenario":"tcp_syn_burst","target_ip":"192.168.50.10"}'
```

Expected: JSON response with `status: accepted` and a `run_id`.

### 5.3 Run Each Scenario via API

Run one at a time and allow at least 60 seconds between each so events are clearly separated in logs.

```bash
curl -X POST http://<Debian-IP>:5000/launch \
  -H "X-API-Token: your_token_here" \
  -H "Content-Type: application/json" \
  -d '{"scenario":"web_scan","target_ip":"192.168.50.10"}'
```

```bash
curl -X POST http://<Debian-IP>:5000/launch \
  -H "X-API-Token: your_token_here" \
  -H "Content-Type: application/json" \
  -d '{"scenario":"ssh_bruteforce_sim","target_ip":"192.168.50.10"}'
```

```bash
curl -X POST http://<Debian-IP>:5000/launch \
  -H "X-API-Token: your_token_here" \
  -H "Content-Type: application/json" \
  -d '{"scenario":"sql_injection_sim","target_ip":"192.168.50.10"}'
```

Additional scenarios exposed by the new API:

1. `udp_flood`
2. `icmp_flood`
3. `fin_scan`
4. `slow_http`

The dashboard on Debian also exposes a kill switch for running attacks and progressive ban controls for attacker IPs.

### 5.4 Record run_id for Each Run

Keep a log of: scenario name, run_id, start time, expected label.

This is used later for ML training data labeling.

Example:

```text
web_scan | run_id=abc123 | 2026-04-27T10:05:00Z | label=web_attack
ssh_bruteforce_sim | run_id=def456 | 2026-04-27T10:07:30Z | label=brute_force
```

---

## 6. Manual Labeled Attack Runs

Run these if you want to generate labeled samples without the API.

### 6.1 TCP SYN Burst

```bash
echo "[label=scan][start=$(date -u +%Y-%m-%dT%H:%M:%SZ)]"
nmap -sS -Pn -p 1-1000 192.168.50.10
echo "[label=scan][end=$(date -u +%Y-%m-%dT%H:%M:%SZ)]"
```

### 6.2 Web Attack

```bash
echo "[label=web_attack][start=$(date -u +%Y-%m-%dT%H:%M:%SZ)]"
/opt/lab/scenarios/web_scan.sh manual-web-01
echo "[label=web_attack][end=$(date -u +%Y-%m-%dT%H:%M:%SZ)]"
```

### 6.3 SSH Brute Force

```bash
echo "[label=brute_force][start=$(date -u +%Y-%m-%dT%H:%M:%SZ)]"
/opt/lab/scenarios/ssh_bruteforce_sim.sh manual-ssh-01
echo "[label=brute_force][end=$(date -u +%Y-%m-%dT%H:%M:%SZ)]"
```

### 6.4 SQL Injection

```bash
echo "[label=sql_injection][start=$(date -u +%Y-%m-%dT%H:%M:%SZ)]"
/opt/lab/scenarios/sql_injection_sim.sh manual-sql-01
echo "[label=sql_injection][end=$(date -u +%Y-%m-%dT%H:%M:%SZ)]"
```

---

## Day 3 - TRex Traffic Generation

## 7. TRex on Debian (Recommended Path)

TRex works best when run directly on Debian because it needs raw socket access or DPDK. Running it from Kali container requires `--privileged` mode.

### 7.1 Install TRex on Debian

`[debian]` Run these on the Debian host, not inside any container.

```bash
cd /opt
sudo mkdir trex
cd trex
sudo wget --no-check-certificate https://trex-tgn.cisco.com/trex/release/latest
sudo tar -xzf latest
cd v3.*
```

Check what version unpacked:

```bash
ls /opt/trex/
```

### 7.2 Confirm TRex Can See Network Interfaces

```bash
sudo /opt/trex/v3.*/dpdk_setup_ports.py --show
```

If DPDK is not supported in VirtualBox, use the software packet mode. TRex falls back to kernel mode automatically in many cases.

Alternative: use hping3 from Kali for repeatable traffic generation without DPDK requirements. See step 7.5.

### 7.3 Create a Simple TRex Stateless Profile

```bash
sudo mkdir -p /opt/trex/profiles
```

```bash
sudo cat > /opt/trex/profiles/lab_http.py << 'EOF'
from trex_stl_lib.api import *

class STLHttpClientSimple(object):
    def create_stream(self):
        pkt = (Ether()/
               IP(src="192.168.60.10", dst="192.168.50.10")/
               TCP(dport=80, flags="S"))
        return STLStream(
            packet=STLPktBuilder(pkt=pkt, vm=[]),
            mode=STLTXCont(pps=100)
        )

    def get_streams(self, tunables, **kwargs):
        return [self.create_stream()]

def register():
    return STLHttpClientSimple()
EOF
```

### 7.4 Run TRex Profile

```bash
cd /opt/trex/v3.*
sudo ./t-rex-64 -f /opt/trex/profiles/lab_http.py -d 60 -m 1 --no-watchdog
```

Parameters:

1. `-d 60` = run for 60 seconds.
2. `-m 1` = multiplier, start low.
3. `--no-watchdog` = needed in some VirtualBox environments.

While it runs, watch OPNsense traffic counters in the web UI.

After run, check:

1. OPNsense Interfaces overview for rising packet/byte counters.
2. Suricata Alerts for new events.
3. Ubuntu SIEM for log ingestion.

### 7.5 Alternative: hping3 Repeatable Traffic from Kali

If TRex is too complex for your VirtualBox environment, use hping3 from inside Kali instead.

```bash
# SYN flood simulation (short burst, 300 packets)
hping3 -S -p 80 -c 300 192.168.50.10

# UDP flood
hping3 --udp -p 53 -c 200 192.168.50.10

# ICMP flood
hping3 --icmp -c 100 192.168.50.10
```

These produce observable traffic counters and Suricata alerts without needing DPDK.

---

## 8. Day 3 Final Labeled Runs for ML Training Data

After all scenarios run and alerts appear, do one final structured pass with run_id labels.

### 8.1 Run All Scenarios Once More in Sequence

```bash
for scenario in tcp_syn_burst web_scan ssh_bruteforce_sim sql_injection_sim; do
  RUN_ID=$(cat /proc/sys/kernel/random/uuid 2>/dev/null || date +%s)
  echo "[start] scenario=$scenario run_id=$RUN_ID ts=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  /opt/lab/scenarios/${scenario}.sh "$RUN_ID"
  echo "[end] scenario=$scenario run_id=$RUN_ID ts=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  sleep 30
done
```

### 8.2 Record the Run Log

Copy the terminal output containing run_ids, timestamps, and scenario names. This will be used in the ML training step on Ubuntu.

---

## 9. Verification Checklist for Kali Side

You are done when all are true:

1. Container starts and has correct IP and gateway.
2. Allowed ports to Ubuntu connect.
3. Blocked ports and internet egress fail.
4. All four scenario scripts exist and are executable.
5. At least one scenario run produced Suricata alerts visible in OPNsense.
6. Control API launch endpoint responded with accepted status.
7. run_id log is saved for ML labeling.
8. TRex or hping3 produced observable traffic in OPNsense counters.
