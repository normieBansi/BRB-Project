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
5. Optional HOST_LAN_NET = your physical host LAN CIDR {probably not needed as host cidr changed}

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

Goal of LAN rules: Ubuntu must be able to function as your target, log receiver, and management node, but it should not become a general-purpose internet client or gain accidental access to networks you do not need.

Before creating the rules, create these aliases in Firewall > Aliases:

1. FIREWALL_LAN_IP = 192.168.50.1
2. OPSENSE_INFRA_PORTS = 53, 123, 514, 5514, 443
3. UBUNTU_REQUIRED_PORTS = 22, 80, 443, 5000, 8080
4. Optional later: TUNNEL_ENDPOINTS as FQDN alias for Cloudflare or ngrok endpoints

Now go to Firewall > Rules > LAN and create rules in this exact order:

1. Pass: Ubuntu to firewall infrastructure
   - Action: Pass
   - Interface: LAN
   - Protocol: TCP/UDP
   - Source: UBUNTU_HOST
   - Destination: FIREWALL_LAN_IP
   - Destination port: OPSENSE_INFRA_PORTS
   - Description: Allow Ubuntu to firewall services
   - Log: enabled

2. Pass: Ubuntu service exposure for Kali testing
   - Action: Pass
   - Interface: LAN
   - Protocol: TCP
   - Source: KALI_HOST or LAB_NET_RED
   - Destination: UBUNTU_HOST
   - Destination port: UBUNTU_REQUIRED_PORTS
   - Description: Allow Kali to Ubuntu test services
   - Log: enabled

3. Pass: Ubuntu outbound for updates only if you need them right now
   - Action: Pass
   - Interface: LAN
   - Protocol: TCP/UDP
   - Source: UBUNTU_HOST
   - Destination: any or TUNNEL_ENDPOINTS if already known
   - Description: Temporary Ubuntu outbound for updates/tunnel
   - Log: enabled

4. Block: Ubuntu to OPT1 network if you want strict one-way testing behavior
   - Action: Block
   - Interface: LAN
   - Protocol: any
   - Source: UBUNTU_HOST
   - Destination: LAB_NET_RED
   - Description: Block Ubuntu to Kali network except reply traffic
   - Log: enabled

5. Leave implicit deny below these rules

Why this rule order matters:

1. The firewall infra rule allows Ubuntu to use DNS/NTP/syslog/API against OPNsense.
2. The Kali-to-Ubuntu service rule makes your test services reachable without broadly opening LAN.
3. The temporary outbound rule gives you an operational escape hatch for package installation and tunnel setup.
4. The block rule prevents Ubuntu from becoming an unrestricted pivot point.

Important note about state tracking:

1. If Kali starts a connection to Ubuntu on an allowed port, reply traffic is automatically allowed back because OPNsense is stateful.
2. That means you do not need separate LAN allow rules just for return packets.

Validation for LAN rules:

From Ubuntu:

```bash
ping -c 2 192.168.50.1
dig @192.168.50.1 example.com
curl -k https://192.168.50.1
```

Expected:

1. Ubuntu reaches firewall LAN IP.
2. DNS works against firewall if Unbound is enabled.
3. HTTPS to firewall GUI only works if GUI is bound to LAN and credentials are valid.

From Kali:

```bash
nc -zv 192.168.50.10 22
nc -zv 192.168.50.10 80
nc -zv 192.168.50.10 443
```

Expected: only the ports you intentionally expose on Ubuntu should connect.

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

This is the part that usually blocks first-time users because OPNsense exposes rulesets, policies, metadata, and custom variables in different places. Follow these steps exactly.

Step A: Decide which rulesets to enable right now

Go to Services > Intrusion Detection > Download.

You may see categories like:

1. ET Open/...
2. abuse.ch/...
3. OPNsense-App-detect/...

For initial setup, do this:

1. Enable ET Open only for the first pass.
2. Do not enable all abuse.ch feeds on day 1.
3. Do not enable all OPNsense-App-detect categories on day 1.

Reason:

1. ET Open is the safest baseline for general IDS/IPS learning and testing.
2. abuse.ch feeds are useful later for reputation/blocklist style detection, but they add more moving parts and can create confusion while you are still validating packet flow.
3. OPNsense-App-detect is more useful when you specifically want application identification experiments, not for first IDS validation.

So your initial state should be:

1. ET Open = enabled
2. abuse.ch = disabled for now
3. OPNsense-App-detect = disabled for now

After ET Open works, you can later enable one additional family at a time and retest.

Step B: Download and update rules

Still in Services > Intrusion Detection > Download:

1. Enable ET Open subscription/download checkbox.
2. Click Download or Update Rules.
3. Wait for completion.

Expected result:

1. Rule files appear as downloaded.
2. No red error on the page.

Step C: Set HOME_NET explicitly

Go to Services > Intrusion Detection > Administration.

Look for:

1. Advanced settings, or
2. Custom home networks / Home networks / HOME_NET depending on OPNsense version.

Set HOME_NET to:

```text
192.168.50.0/24,192.168.60.0/24
```

If the field expects one value per line, enter:

```text
192.168.50.0/24
192.168.60.0/24
```

What HOME_NET means:

1. Suricata uses it to know which networks are considered internal.
2. Many rules depend on internal-to-external or external-to-internal direction.
3. If HOME_NET is wrong, some rules will never fire or will classify traffic incorrectly.

Step D: Understand what “policy” means here

Go to Services > Intrusion Detection > Policy.

There is usually not a literal button named “balanced”. What I meant was: create a moderate starting policy that does not enable everything and does not aggressively drop traffic.

Use this exact practical interpretation:

1. Create a new policy entry if required.
2. Target ET Open rules.
3. Start with ALERT action rather than DROP for the first stage.
4. Apply the policy to both LAN and OPT1 monitored traffic if the UI asks.

If the Policy page asks for fields, use this pattern:

1. Enabled: yes
2. Action: Alert
3. Ruleset/source: ET Open
4. Description: ET Open baseline alert policy
5. Priority/filter fields: leave default unless required by your version

If your OPNsense version shows rule categories instead of one global action, use this method:

1. Enable common exploit/web/malware/scan-related ET Open categories.
2. Leave highly broad informational/chatty categories disabled for now.

Step E: What “noisy categories” means in practice

For a first lab pass, prefer keeping enabled categories related to:

1. attack response
2. exploit
3. scan
4. web server / web attack
5. malware or trojan where available

Be cautious or leave disabled initially categories that are often noisy in small labs, such as:

1. informational-only policy categories
2. generic protocol chatter categories
3. browser/client behavior categories that trigger on common normal traffic
4. large app-detect groups that you are not explicitly testing

If the UI only shows long category names and you are unsure, use this simpler rule:

1. Anything clearly labeled exploit, scan, attack, malware = enable first
2. Anything clearly labeled policy, info, chat, games, p2p, generic app behavior = skip first

Step F: Apply configuration safely

1. Save changes.
2. Return to Services > Intrusion Detection > Administration.
3. Start Suricata in IDS mode first.
4. Do not enable IPS/drop yet.

Your day-1 Suricata baseline should therefore be:

1. Interfaces monitored: LAN and OPT1
2. Ruleset source: ET Open only
3. HOME_NET: both lab subnets
4. Policy action: alert only
5. abuse.ch and App-detect feeds: off for now

Why this works:

1. It reduces moving parts.
2. It makes validation deterministic.
3. It gives you a clean baseline before moving to IPS/drop or extra feeds.

### 6.3 IDS vs IPS Mode

1. Start in IDS (alert only) for 15-30 minutes.
2. Verify expected alerts appear.
3. Switch to IPS inline mode and verify allowed traffic is still functional.

Why: staging prevents accidental traffic blackouts due to false positives.

### 6.4 Suricata Validation

Do this in two phases: first make Ubuntu host a deliberately simple web target, then make Kali send traffic that is likely to trigger ET Open web/scan signatures.

Phase 1: Prepare a very simple target on Ubuntu

On Ubuntu, install and start a temporary web server:

```bash
sudo apt update
sudo apt install -y apache2 curl
sudo systemctl enable --now apache2
curl http://127.0.0.1
```

Expected:

1. Apache starts successfully.
2. `curl http://127.0.0.1` returns the default Apache page HTML.

Now make sure OPNsense rules allow Kali to reach Ubuntu on TCP 80.

From Kali, confirm reachability first:

```bash
curl -I http://192.168.50.10
nc -zv 192.168.50.10 80
```

Expected: HTTP headers return and TCP 80 is reachable.

Phase 2: Generate scan-style traffic from Kali

Install tools on Kali if needed:

```bash
sudo apt update
sudo apt install -y nmap curl nikto
```

Run these in order.

Test 1: SYN/port scan style traffic

```bash
nmap -sS -Pn -p 1-1000 192.168.50.10
```

Why this helps:

1. ET Open commonly has scan-related signatures.
2. Even if Suricata does not alert on every scan, this creates observable scan behavior in logs.

Test 2: Service/version scan

```bash
nmap -sV -Pn 192.168.50.10
```

Why this helps:

1. Generates more application-probing traffic than a simple port check.

Test 3: Web probing with Nikto

```bash
nikto -h http://192.168.50.10
```

Why this helps:

1. Nikto often triggers web reconnaissance/attack signatures.
2. It is one of the easiest lab-safe ways to produce signature-worthy HTTP noise.

Test 4: Suspicious URL probes with curl

Run a few manual probes:

```bash
curl "http://192.168.50.10/?id=1'"
curl "http://192.168.50.10/../../../../etc/passwd"
curl -A "sqlmap/1.0" "http://192.168.50.10/"
```

Why this helps:

1. Strange paths, traversal patterns, and scanner-like user agents may match ET Open HTTP/web signatures.

Phase 3: Check Suricata alerts

In OPNsense:

1. Go to Services > Intrusion Detection > Alerts.
2. Sort by newest first.
3. Filter for source `192.168.60.10` if filter box is available.

What to look for:

1. Signature ID (SID)
2. Message text
3. Source IP = Kali
4. Destination IP = Ubuntu
5. Interface = LAN or OPT1 depending on where Suricata observed it

If you see alerts, your IDS baseline is working.

Phase 4: Only after alerts work, test IPS/drop mode

1. Return to Services > Intrusion Detection > Administration.
2. Enable IPS / inline mode.
3. Apply changes.
4. Re-run only one or two earlier tests first, such as:

```bash
nikto -h http://192.168.50.10
nmap -sS -Pn -p 1-200 192.168.50.10
```

Now check Alerts again.

Expected in IPS mode:

1. Some events may now show drop/reject instead of alert-only.
2. Some requests may fail from Kali that previously succeeded.

If you get no alerts at all, troubleshoot in this order:

1. Confirm Suricata service is running.
2. Confirm monitored interfaces include the interface where traffic actually passes.
3. Confirm HOME_NET contains both subnets.
4. Confirm ET Open rules were downloaded.
5. Confirm Kali traffic is actually crossing OPNsense and not bypassing via wrong NIC.
6. Confirm Ubuntu service is reachable first before expecting web signatures.

Minimum success condition for this section:

1. One scan/probe command from Kali generates at least one Suricata alert tied to `192.168.60.10 -> 192.168.50.10`.

---

## 7) DNS Control and Blocklists

### 7.1 Unbound Setup

Do this only after basic firewall rules and Suricata testing are working.

Step 1: Enable Unbound itself

1. Go to Services > Unbound DNS > General.
2. Check Enable Unbound.
3. In Network Interfaces, select:
   - LAN
   - OPT1
   - Localhost if available
4. Save.
5. Click Apply.

Step 2: Verify the firewall can resolve DNS before forcing clients to use it

1. Go to System > Diagnostics > DNS Lookup.
2. Query `example.com`.

Expected:

1. The firewall returns an IP address.
2. If it fails here, stop and fix WAN/DNS first.

Step 3: Allow clients to query only the firewall for DNS

Create alias first if missing:

1. DNS_PORT = 53

Create these explicit rules above your broader block rules.

On OPT1:

1. Pass
   - Source: KALI_HOST
   - Destination: OPT1 address
   - Protocol: TCP/UDP
   - Destination port: DNS_PORT
   - Description: Kali DNS to firewall
   - Log: enabled

On LAN:

1. Pass
   - Source: UBUNTU_HOST
   - Destination: LAN address
   - Protocol: TCP/UDP
   - Destination port: DNS_PORT
   - Description: Ubuntu DNS to firewall
   - Log: enabled

Step 4: Block direct DNS to anything else

On OPT1:

1. Block
   - Source: KALI_HOST
   - Destination: any
   - Protocol: TCP/UDP
   - Destination port: 53
   - Description: Block Kali external DNS
   - Log: enabled

On LAN:

1. Block
   - Source: UBUNTU_HOST
   - Destination: any
   - Protocol: TCP/UDP
   - Destination port: 53
   - Description: Block Ubuntu external DNS
   - Log: enabled

Validation:

From Kali:

```bash
dig @192.168.60.1 example.com
dig @1.1.1.1 example.com
```

Expected:

1. Query to 192.168.60.1 succeeds.
2. Query to 1.1.1.1 fails because it is blocked.

Why: DNS egress control is foundational for NGFW observability because you force all lab name resolution through one control point.

### 7.2 Blocklist Strategy

Use blocklists only after Unbound resolution works normally.

Safe first-pass approach:

1. Enable only one conservative feed first.
2. Test DNS resolution again from Ubuntu.
3. Test package updates if you rely on them.
4. If nothing breaks, add one more feed later.

Avoid this on the first pass:

1. enabling many feeds together,
2. changing Suricata feeds and DNS blocklists at the same time,
3. assuming a DNS failure is a Suricata problem.

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

Decision rule:

1. If Ubuntu has 8 GB RAM and remains responsive, try Wazuh first.
2. If the VM becomes slow or indexing starts to lag badly, fall back to a lighter log + dashboard stack.

Minimum requirement for project progress:

1. Logs must arrive on Ubuntu.
2. You must be able to search them.
3. You must be able to display them in at least one dashboard view.

---

## 9) OPNsense Log Forwarding to Ubuntu

### 9.1 Receiver on Ubuntu

Configure rsyslog on Ubuntu before touching OPNsense remote logging.

Create a dedicated rsyslog config file, for example `/etc/rsyslog.d/10-opnsense.conf`, with:

```conf
module(load="imudp")
input(type="imudp" port="514")

module(load="imtcp")
input(type="imtcp" port="5514")
```

Then run:

```bash
sudo systemctl restart rsyslog
sudo systemctl status rsyslog --no-pager
```

If `ufw` is active:

```bash
sudo ufw allow 514/udp
sudo ufw allow 5514/tcp
```

Quick check:

```bash
sudo ss -lunpt | grep -E '514|5514'
```

Expected: listener sockets active.

Optional but useful:

1. Create a dedicated file output later for OPNsense logs.
2. That gives you raw evidence even if the SIEM parser is not ready yet.

### 9.2 OPNsense Remote Syslog

1. System > Settings > Logging / Targets.
2. Add remote target = Ubuntu IP.
3. Enable facility categories:
   - firewall
   - system
   - IDS/Suricata

Practical order:

1. Start with only firewall logs.
2. Validate they arrive.
3. Then enable system logs.
4. Then enable IDS/Suricata logs.

Start with UDP 514 first because it is easiest to validate.

### 9.3 Validation

On Ubuntu:

```bash
sudo tcpdump -ni any port 514 or port 5514
```

Expected: packets arriving from OPNsense.

Then verify SIEM index receives parsed events.

If the SIEM is not ready yet, validate raw receipt instead:

```bash
sudo journalctl -u rsyslog -n 50 --no-pager
sudo tail -n 50 /var/log/syslog
```

Minimum success condition:

1. Ubuntu sees the raw firewall log stream.

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

Build order recommendation:

1. Make the control API work from `curl` first.
2. Then connect one dashboard button to one scenario.
3. Only then add more buttons and metadata widgets.

Minimum viable control panel:

1. one scenario selector,
2. one launch button,
3. one last-run status field.

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

Build order recommendation:

1. Start with raw event table.
2. Add alert count by severity.
3. Add top source/top destination panels.
4. Add ML charts only after model outputs are indexed.

Minimum viable telemetry panel:

1. live event list,
2. alert count time series,
3. top sources.

---

## 11) Safe Internet Exposure at Zero Cost

### 11.1 Tunnel Choice

Use one:

1. Cloudflare Tunnel (free tier)
2. Ngrok free tier

Decision rule:

1. Use Cloudflare Tunnel if you already have the account and want a more stable hosted path.
2. Use ngrok if you want the quickest temporary demo path.

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

Minimum safe publication rule:

1. Do not publish anything before local private access works.
2. Publish only the dashboard and the control API.
3. Never publish Kali, raw syslog, or internal indexer ports.

---

## Day 3: AI Models + TRex Relearning + Demo

## 12) ML Data Engineering Pipeline

### 12.1 Source Data

Primary sources:

1. Suricata EVE/alerts.
2. OPNsense firewall logs.
3. Scenario run metadata (run_id, scenario, expected class).

Add run_id to generated traffic events when possible so labels are easy.

Practical data handling rule:

1. Keep raw logs unchanged in one folder.
2. Write parsed features into a separate CSV or Parquet file.
3. Do not train directly on mixed raw logs without normalization.

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

If you want the simplest possible first feature set, start with:

1. src_port
2. dst_port
3. proto
4. packets
5. bytes
6. flow_duration_ms
7. alert_severity
8. hour_of_day

### 12.3 Preprocessing Steps

1. Impute missing values (median for numeric, unknown for categorical).
2. Encode categorical values (one-hot or ordinal where stable).
3. Scale numeric features for anomaly model.
4. Keep train/test split by time windows to reduce leakage.

Why: random splitting mixed with near-identical flows can overstate model quality.

Practical training workflow:

1. Save one mostly normal baseline dataset.
2. Save one scenario-labeled mixed dataset.
3. Train Isolation Forest on the baseline.
4. Train Random Forest on the labeled set.

### 12.4 Isolation Forest Workflow

1. Train primarily on benign baseline period.
2. Start contamination in 0.02 to 0.08 range.
3. Publish:
   - anomaly_score (continuous)
   - anomaly_flag (binary)

Tune contamination based on false positive rate in your dashboard.

Simple first choice:

1. Start with contamination = 0.05.
2. If normal traffic gets flagged too much, lower it.
3. If obvious bad traffic is missed, raise it slightly and retest.

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

Practical labeling advice:

1. Every scenario should have exactly one run_id and one label.
2. Start with 3 to 5 labels only.
3. Do not create many fine-grained labels until the pipeline is stable.

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

Recommended learning order:

1. Learn how to launch one basic stateless TRex profile.
2. Confirm OPNsense counters rise.
3. Confirm logs and alerts rise.
4. Only then increase rate or concurrency.

If VirtualBox limits throughput:

1. lower PPS.
2. shorten profile duration.
3. reduce concurrent scenario count.

Minimum TRex success condition:

1. One named run appears in counters, logs, and dashboard timelines.
2. You do not need extreme throughput for the project to be valid.

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

Cheap discriminating check:

1. If `tcpdump` sees packets on Ubuntu, the problem is no longer OPNsense.
2. Then focus on rsyslog or the SIEM parser.

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

Cheap discriminating check:

1. If firewall counters rise but Suricata stays silent, check rules, HOME_NET, and the traffic content.
2. If counters do not rise, the issue is before the firewall path.

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
