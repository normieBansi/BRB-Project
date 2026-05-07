# OPNsense Click-by-Click Checklist

**Navigation:** [Kali Checklist](Kali_Checklist.md) | [Ubuntu Checklist](Ubuntu_Checklist.md) | [Theory Guide](NGFW_Theory_to_Action_Guide.md)

**Theory Quick Index (Most Used):**

1. [Separation of Duties and Blast Radius](NGFW_Theory_to_Action_Guide.md#2-theory-separation-of-duties-and-blast-radius)
2. [Least Privilege Segmentation (L3/L4)](NGFW_Theory_to_Action_Guide.md#3-theory-least-privilege-segmentation-l3l4)
3. [DNS as a Security Control Plane](NGFW_Theory_to_Action_Guide.md#4-theory-dns-as-a-security-control-plane)
4. [Detection Pipeline (IDS then IPS)](NGFW_Theory_to_Action_Guide.md#5-theory-detection-pipeline-ids-then-ips)
5. [Containment and Incident Response Loop](NGFW_Theory_to_Action_Guide.md#7-theory-containment-and-incident-response-loop)
6. [Minimal Exposure for External Access](NGFW_Theory_to_Action_Guide.md#11-theory-minimal-exposure-for-external-access)

---

This checklist is written for exact reproduction. Follow every step in order.

Execution tags used in this file:

1. `[opnsense-ui]` means run in the OPNsense web UI.
2. `[opnsense-shell]` means run in OPNsense console option 8 shell.
3. `[debian]` means run on Debian host terminal.
4. `[kali]` means run inside Kali container shell.
5. `[ubuntu]` means run inside Ubuntu container shell.

Lab constants used by this checklist:

1. OPNsense LAN IP: `192.168.50.1`
2. OPNsense OPT1 IP: `192.168.60.1`
3. Ubuntu target IP: `192.168.50.10`
4. Kali source network: `192.168.60.0/24`
5. Ubuntu network: `192.168.50.0/24`

Do not continue if your live values differ from the constants above. Fix topology first.

---

## Day 1 - Base OPNsense Policy and IDS Baseline

## 1. Before Logging In

Goal: prove the topology is correct before touching firewall policy.

- `[debian]` Confirm container IPs and gateways.

```bash
sudo podman exec kali-lab ip -4 addr show eth0
sudo podman exec kali-lab ip route
sudo podman exec ubuntu-lab ip -4 addr show eth0
sudo podman exec ubuntu-lab ip route
```

Expected:

1. Kali has `192.168.60.x` and default route via `192.168.60.1`.
2. Ubuntu has `192.168.50.10` and default route via `192.168.50.1`.

- `[kali]` Verify gateway reachability.

```bash
ping -c 2 192.168.60.1
```

- `[ubuntu]` Verify gateway reachability.

```bash
ping -c 2 192.168.50.1
```

Expected:

1. Both pings succeed.
2. If either fails, stop and fix VM/container network mapping before continuing.

---

## 2. Base System Setup

### 2.1 Update Firmware

1. `[opnsense-ui]` Open **System > Firmware > Updates**.
2. Click **Check for updates**.
3. Install all available updates.
4. Reboot if prompted.

Expected: firewall returns to login page with no pending critical updates.

### 2.2 Time and Basic Settings

1. `[opnsense-ui]` Open **System > Settings > General**.
2. Set timezone correctly.
3. Keep DNS resolver values consistent with your WAN setup.
4. Save and Apply.

Expected: current time shown in UI is correct.

### 2.3 Admin Access Hardening

1. `[opnsense-ui]` Open **System > Access > Administration**.
2. Keep GUI access limited to trusted interfaces only.
3. If SSH is enabled, prefer key auth and disable password auth where practical.
4. Save and Apply.

Expected: management remains reachable from trusted path, not broad WAN exposure.

---

## 3. Create All Required Aliases First

Goal: create deterministic alias objects before adding any rules.

If you already added your own rules/objects, do not delete them. Keep your custom entries, then add or correct the aliases below and place the rule set from section 4 above broad catch-all blocks.

- `[opnsense-ui]` Open **Firewall > Aliases**.
- Create each alias exactly as listed:

- `KALI_HOST`: Type `Host(s)`, Content `192.168.60.10`
- `AUTO_BAN_IPS`: Type `Host(s)`, Content `192.168.60.254`
- `UBUNTU_HOST`: Type `Host(s)`, Content `192.168.50.10`
- `LAB_NET_RED`: Type `Network(s)`, Content `192.168.60.0/24`
- `LAB_NET_BLUE`: Type `Network(s)`, Content `192.168.50.0/24`
- `FIREWALL_LAN_IP`: Type `Host(s)`, Content `192.168.50.1`
- `FIREWALL_OPT1_IP`: Type `Host(s)`, Content `192.168.60.1`
- `ICMP_ALLOWED_TARGETS`: Type `Host(s)`, Content `192.168.50.10,192.168.60.1`
- `TEST_TARGET_PORTS`: Type `Port(s)`, Content `22,53,80,443,5000,8080`
- `OPSENSE_INFRA_PORTS`: Type `Port(s)`, Content `53,123,443,514,5514`
- `DNS_PORT`: Type `Port(s)`, Content `53`

Critical checks:

1. `KALI_HOST` and `AUTO_BAN_IPS` must be `Host(s)`, not `External (advanced)`.
2. If wrong type was created, delete and recreate with correct type.
3. Keep alias names unchanged (`KALI_HOST`, `AUTO_BAN_IPS`) so Control API sync and ban/unban hooks continue to work.

Expected: alias list contains exactly the 11 entries above with correct types.

---

## 4. OPT1 Rules (Kali Side)

Goal: enforce least privilege from attacker network to target network.

Open **Firewall > Rules > OPT1** and create rules in this exact order.

### 4.1 Block Dynamically Banned Attackers First

1. Action: `Block`
2. Interface: `OPT1`
3. Protocol: `any`
4. Source: `AUTO_BAN_IPS`
5. Destination: `any`
6. Log: enabled
7. Description: `Block dynamically banned attacker IPs`

### 4.2 Allow Kali to Ubuntu Test Services

1. Action: `Pass`
2. Interface: `OPT1`
3. Protocol: `TCP/UDP`
4. Source: `KALI_HOST`
5. Destination: `UBUNTU_HOST`
6. Destination port: `TEST_TARGET_PORTS`
7. Log: enabled
8. Description: `Allow Kali to Ubuntu test services`

### 4.3 Allow Kali ICMP to Lab Targets

1. Action: `Pass`
2. Interface: `OPT1`
3. Protocol: `ICMP`
4. Source: `KALI_HOST`
5. Destination: `ICMP_ALLOWED_TARGETS`
6. Log: enabled
7. Description: `Allow Kali ICMP to gateway and Ubuntu`

### 4.4 Allow Kali DNS to Firewall

1. Action: `Pass`
2. Interface: `OPT1`
3. Protocol: `TCP/UDP`
4. Source: `KALI_HOST`
5. Destination: `FIREWALL_OPT1_IP`
6. Destination port: `DNS_PORT`
7. Log: enabled
8. Description: `Allow Kali DNS to firewall`

### 4.5 Block Kali External DNS

1. Action: `Block`
2. Interface: `OPT1`
3. Protocol: `TCP/UDP`
4. Source: `KALI_HOST`
5. Destination: `any`
6. Destination port: `53`
7. Log: enabled
8. Description: `Block Kali external DNS`

### 4.6 Block Kali to WAN/Other Unintended Egress

1. Action: `Block`
2. Interface: `OPT1`
3. Protocol: `any`
4. Source: `KALI_HOST`
5. Destination: `any`
6. Log: enabled
7. Description: `Block Kali unintended outbound`

### 4.7 Apply Rule Changes

1. Click **Apply Changes**.
2. Verify top-down order is exactly sections 4.1 through 4.6.

Expected: block-ban rule is first, explicit allow second, DNS controls next, broad block last.

---

## 5. LAN Rules (Ubuntu Side)

Goal: keep Ubuntu functional for lab services without making it a pivot host.

Open **Firewall > Rules > LAN** and create rules in this exact order.

### 5.1 Allow Ubuntu to Firewall Services

1. Action: `Pass`
2. Interface: `LAN`
3. Protocol: `TCP/UDP`
4. Source: `UBUNTU_HOST`
5. Destination: `FIREWALL_LAN_IP`
6. Destination port: `OPSENSE_INFRA_PORTS`
7. Log: enabled
8. Description: `Allow Ubuntu to firewall services`

### 5.2 Allow Ubuntu DNS to Firewall

1. Action: `Pass`
2. Interface: `LAN`
3. Protocol: `TCP/UDP`
4. Source: `UBUNTU_HOST`
5. Destination: `FIREWALL_LAN_IP`
6. Destination port: `DNS_PORT`
7. Log: enabled
8. Description: `Allow Ubuntu DNS to firewall`

### 5.3 Allow Temporary Ubuntu Outbound for Updates

1. Action: `Pass`
2. Interface: `LAN`
3. Protocol: `TCP/UDP`
4. Source: `UBUNTU_HOST`
5. Destination: `any`
6. Log: enabled
7. Description: `Temporary Ubuntu outbound for setup`

### 5.4 Block Ubuntu External DNS

1. Action: `Block`
2. Interface: `LAN`
3. Protocol: `TCP/UDP`
4. Source: `UBUNTU_HOST`
5. Destination: `any`
6. Destination port: `53`
7. Log: enabled
8. Description: `Block Ubuntu external DNS`

### 5.5 Optional Block Ubuntu to Red Network

1. Action: `Block`
2. Interface: `LAN`
3. Protocol: `any`
4. Source: `UBUNTU_HOST`
5. Destination: `LAB_NET_RED`
6. Log: enabled
7. Description: `Block Ubuntu to red network`

### 5.6 Apply Rule Changes

1. Click **Apply Changes**.
2. Verify order matches 5.1 to 5.5.

Expected: policy remains explicit and deterministic.

---

## 6. NAT Check

1. `[opnsense-ui]` Open **Firewall > NAT > Outbound**.
2. Keep mode `Automatic` or `Hybrid`.
3. Do not add broad custom outbound NAT rules.

Expected: no overly broad manual NAT exceptions.

---

## 7. Connectivity Validation

### 7.1 From Kali

```bash
ping -c 2 192.168.60.1
ping -c 2 192.168.50.10
nc -zv 192.168.50.10 80
nc -zv 192.168.50.10 22
nc -zv 192.168.50.10 3306
hping3 --udp -p 53 -c 3 192.168.50.10
curl -m 5 http://192.168.50.10
curl -m 5 https://example.com
```

Expected:

1. ICMP to OPT1 gateway and Ubuntu succeeds.
2. Allowed ports (22/53/80/443/5000/8080 when open on Ubuntu) can connect.
3. UDP/53 test packets to Ubuntu pass through OPT1 rule set.
4. Non-allowed ports fail or timeout.
5. External egress test is blocked by policy.

### 7.2 From Ubuntu

```bash
ping -c 2 192.168.50.1
dig @192.168.50.1 example.com
```

Expected: firewall reachability and resolver response succeed.

### 7.3 In OPNsense Logs

1. `[opnsense-ui]` Open **Firewall > Log Files > Live View**.
2. Filter by current Kali source IP.
3. Confirm both pass and block entries exist for tests above.

---

## 8. Suricata Setup

### 8.1 Enable Service

1. `[opnsense-ui]` Open **Services > Intrusion Detection > Administration**.
2. Enable IDS.
3. Select interface `LAN` only.
4. Save and Apply.

### 8.2 Download Rules

1. Open **Services > Intrusion Detection > Download**.
2. Enable ET Open.
3. Download/Update rules.

Expected: ET Open rules download without error.

### 8.3 Set HOME_NET

1. Back in **Administration**, set HOME_NET to:

```text
192.168.50.0/24,
```

- do not include `192.168.60.0/24` in **HOME_NET**, as it would not trigger rules for external threats

1. Save and Apply.

### 8.4 Policy Setup

1. Open **Services > Intrusion Detection > Policy**.
2. Start with alert-focused policy (not drop-all).
3. Enable high-value categories first: exploit/scan/web/malware.

### 8.5 Start in IDS Mode

1. Confirm IDS mode is active (alerts only).
2. Keep IPS disabled for baseline lab stability (virtualized netmap issues are common).

---

## 9. Suricata Validation

### 9.1 Prepare Ubuntu DVWA Target

1. `[ubuntu]` Ensure Apache + DVWA are running:

```bash
sudo systemctl enable --now apache2
curl -I http://127.0.0.1/dvwa/login.php
```

### 9.2 Confirm Reachability from Kali

```bash
curl -I http://192.168.50.10/dvwa/login.php
nc -zv 192.168.50.10 80
```

### 9.3 Generate Alert Traffic from Kali

```bash
nmap -sS -Pn -p 1-1000 192.168.50.10
nmap -sV -Pn 192.168.50.10
nikto -h http://192.168.50.10/dvwa
curl "http://192.168.50.10/dvwa/vulnerabilities/sqli/?id=1'&Submit=Submit"
curl "http://192.168.50.10/dvwa/vulnerabilities/fi/?page=../../../../etc/passwd"
curl -A "sqlmap/1.0" "http://192.168.50.10/dvwa/login.php"
```

### 9.4 Check Alerts

1. `[opnsense-ui]` Open **Services > Intrusion Detection > Alerts**.
2. Sort newest first.
3. Filter by current Kali IP.

Expected: you see events referencing Kali source and Ubuntu destination.

### 9.5 Optional IPS Stage (Only If Stable)

1. Enable IPS/inline mode only if your VM remains stable.
2. Re-run one short scan and one nikto run.
3. Confirm alerts now include drop/reject where expected.

If normal traffic breaks unexpectedly, revert to IDS mode and tune policy before retry.

---

## 10. Unbound DNS

### 10.1 Enable Unbound

1. `[opnsense-ui]` Open **Services > Unbound DNS > General**.
2. Enable Unbound.
3. Select interfaces: LAN and OPT1.
4. Save and Apply.

### 10.2 Validate Firewall DNS

1. `[opnsense-ui]` Open **System > Diagnostics > DNS Lookup**.
2. Query `example.com`.

Expected: resolver returns records.

### 10.3 Validate from Clients

`[kali]`:

```bash
dig @192.168.60.1 example.com
dig @1.1.1.1 example.com
```

`[ubuntu]`:

```bash
dig @192.168.50.1 example.com
dig @8.8.8.8 example.com
```

Expected:

1. Queries to firewall IP succeed.
2. Direct external DNS queries are blocked.

---

## 11. Remote Logging to Ubuntu

### 11.1 Configure Target

1. `[opnsense-ui]` Open **System > Settings > Logging / Targets**.
2. Add target host `192.168.50.10`, port `514`, transport `UDP`.
3. Start with application `filter` only.
4. Save and Apply.

### 11.2 Validate

`[debian]`:

```bash
sudo tcpdump -ni any udp port 514
```

Expected: packets from OPNsense arrive while generating traffic.

### 11.3 Expand Log Categories

1. Add `suricata` only after `filter` flow is confirmed stable.
2. Avoid enabling noisy categories all at once.

---

## Day 2 - OPNsense Support for Logging, Dashboard, and Controlled Access

## 12. Day 2 Preconditions

Proceed only if all are true:

1. OPNsense rules from sections 4 and 5 are active.
2. Suricata alerts are visible.
3. Unbound DNS enforcement is working.
4. Debian receives at least firewall filter logs.

---

## 13. Day 2 Logging and Management Steps

### 13.1 Confirm OPNsense Can Reach Debian Services

`[opnsense-shell]`:

```sh
ping -c 2 192.168.50.10
```

### 13.2 Configure Remote Logging in Stages

1. Keep only `filter` enabled first.
2. Generate traffic and confirm receipt on Debian.
3. Then add `suricata`.

### 13.3 Add Suricata Logs After Firewall Logs Work

1. Add `suricata` to the same target.
2. Save and Apply.

Expected: suricata events arrive in Debian logs after trigger traffic.

### 13.4 Review Local OPNsense Logging Health

`[opnsense-shell]`:

```sh
clog -f /var/log/filter/latest.log
```

Expected: local logging is active and responsive.

### 13.5 Configure OPNsense REST API for Debian Control API

1. `[opnsense-ui]` Open **System > Access > Users**.
2. Create user `opn_api` (or equivalent dedicated API user).
3. Edit user and generate API key + secret.
4. Save credentials to Debian secure file (do not paste into checklist files).

`[debian]` secure file preparation example:

```bash
mkdir -p ~/lab/secrets
chmod 700 ~/lab/secrets
cat > ~/lab/secrets/opnsense_api.env << 'EOF'
OPNSENSE_API_BASE_URL='https://192.168.50.1'
OPNSENSE_API_KEY='replace_with_key'
OPNSENSE_API_SECRET='replace_with_secret'
OPNSENSE_API_VERIFY_TLS='false'
OPNSENSE_API_TIMEOUT_SECONDS='4'
OPNSENSE_BAN_ALIAS_TABLE='AUTO_BAN_IPS'
OPNSENSE_KALI_ALIAS_TABLE='KALI_HOST'
EOF
chmod 600 ~/lab/secrets/opnsense_api.env
```

Expected: credentials stored in one private file only.

### 13.6 Validate Dashboard Hook Integration End-to-End

`[debian]` validate raw alias API calls:

```bash
set -a
source ~/lab/secrets/opnsense_api.env
set +a

curl -sk --user "$OPNSENSE_API_KEY:$OPNSENSE_API_SECRET" \
  -H "Content-Type: application/json" \
  -X POST \
  -d '{"address":"192.168.60.222"}' \
  "$OPNSENSE_API_BASE_URL/api/firewall/alias_util/add/AUTO_BAN_IPS"

curl -sk --user "$OPNSENSE_API_KEY:$OPNSENSE_API_SECRET" \
  -H "Content-Type: application/json" \
  -X POST \
  -d '{"address":"192.168.60.222"}' \
  "$OPNSENSE_API_BASE_URL/api/firewall/alias_util/delete/AUTO_BAN_IPS"
```

Expected: both return success JSON.

Then validate control API integration:

```bash
curl -X POST http://127.0.0.1:5000/firewall/hook-test \
  -H "X-API-Token: $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"ip":"192.168.60.222","reason":"opnsense_hook_test"}'

curl -X POST http://127.0.0.1:5000/kali/network \
  -H "X-API-Token: $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"ip":"192.168.60.20"}'
```

Expected:

1. Hook test returns `status: ok`.
2. Kali reassign returns updated `ip` and sync mode.

### 13.7 If OPNsense Automation Feels Laggy (Exact Triage)

`[debian]` check REST round-trip:

```bash
for i in 1 2 3 4 5; do
  /usr/bin/time -f "api_roundtrip=%E" \
    curl -sk --max-time 4 \
    --user "$OPNSENSE_API_KEY:$OPNSENSE_API_SECRET" \
    "$OPNSENSE_API_BASE_URL/api/firewall/alias_util/list/AUTO_BAN_IPS" >/dev/null
done
```

Interpretation:

1. Usually below 1 second in this lab is healthy.
2. Repeated above 2 seconds indicates host contention.

`[opnsense-shell]` quick health snapshot:

```sh
top -aSH -b -n 1 | head -n 35
swapinfo -h
iostat -x 1 3
pfctl -si | egrep -i 'state|memory|current entries'
```

If unstable, reduce Suricata/rule/logging load before blaming API wiring.

### 13.8 Keep or Drop Automated Ban/Unban

Recommendation for this lab: keep it enabled with bounded timeouts.

1. `OPNSENSE_API_TIMEOUT_SECONDS=4`
2. `PODMAN_COMMAND_TIMEOUT_SECONDS=8`

Use manual-only mode temporarily only during intentional high-load stress windows.

---

## 14. Day 2 Optional Publishing Support

### 14.1 Keep Exposure Minimal

Expose only dashboard/API path when needed. Do not expose raw logging, indexer, or container internals.

### 14.2 If You Must Add a Temporary Port Forward Later

1. Create narrow rule for one service only.
2. Set source restriction when possible.
3. Remove rule immediately after demonstration.

---

## Day 3 - OPNsense Final Validation, Optional IPS Staging, and Evidence Capture

## 15. Day 3 IDS Finalization and Optional IPS Hardening

### 15.1 Reconfirm Resource-Safe Settings

1. Keep ET Open as primary ruleset.
2. Avoid enabling all categories blindly.
3. Keep logging categories minimal unless needed for specific evidence.

### 15.2 Move from IDS to IPS Carefully

1. Keep IDS as default. Enable IPS only if no netmap/iflib instability appears.
2. Re-run one short scan/probe sequence.
3. Confirm detection without breaking core allowed flows.

### 15.3 Final OPNsense Rule Review

1. OPT1 block-ban rule remains top-most.
2. LAN/OPT1 rules still match intended order.
3. No accidental broad allow above specific block rules.

### 15.4 Final DNS Review

1. Client DNS to firewall succeeds.
2. Direct external DNS remains blocked.

---

## 16. Optional Internet Publishing Support

### 16.1 NAT/Exposure Rule

Only keep this if required by your final demo. Remove afterwards.

### 16.2 API Access for Automation

Do not expose OPNsense API endpoints publicly.

---

## 17. Backup and Evidence Collection

### 17.1 Export Configuration

1. `[opnsense-ui]` Open **System > Configuration > Backups**.
2. Export encrypted backup.

### 17.2 Capture Evidence

Capture and archive:

1. Rule screenshots with ordering visible.
2. Suricata alert screenshots with source/destination.
3. DNS control test outputs.
4. Remote logging packet capture proof.
5. Hook-test and Kali reassign API outputs from Debian.

---

## 18. Minimum OPNsense Success Checklist

Consider OPNsense complete only when all are true:

1. Aliases are created with correct types, including Host(s) aliases for `KALI_HOST` and `AUTO_BAN_IPS`.
2. OPT1 and LAN rule order matches this checklist.
3. Kali reaches only intended Ubuntu services.
4. External DNS bypass from clients is blocked.
5. Suricata alerts fire in IDS mode on LAN; IPS is optional.
6. OPNsense forwards logs to Debian and Debian receives them.
7. REST alias updates succeed with generated API credentials.
8. Control API hook test can ban and unban without manual pf edits.
9. Kali IP reassign sync updates `KALI_HOST` via REST API.
10. Config backup exported successfully.

---

## 19. If Something Fails

Use this exact triage order:

1. Confirm topology/IP/gateway first.
2. Confirm alias types and rule order second.
3. Confirm service-level function (DVWA/Apache, Unbound, Suricata) third.
4. Confirm logging path fourth.
5. Confirm REST credentials and alias util endpoints last.

Do not change multiple systems at once during troubleshooting. Change one layer, retest, then continue.
