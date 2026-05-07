# OPNsense Point-by-Point Tests

This document is the separate validation file for the full project. It is intentionally explicit. Run the tests in order and do not skip expected-result checks.

Lab assumptions used here:

1. OPNsense VM = 2 vCPU, 2 GB RAM, 10 GB storage.
2. Debian VM = 4 vCPU, 4 GB RAM, 40 GB storage.
3. Debian hosts Podman containers for Kali and Ubuntu.
4. Kali default IP = 192.168.60.10, but it may be reassigned by the dashboard inside `192.168.60.0/24`.
5. Ubuntu IP = 192.168.50.10.
6. OPNsense LAN IP = 192.168.50.1.
7. OPNsense OPT1 IP = 192.168.60.1.

---

## 1. Test Rules Before Starting

1. Change only one thing at a time.
2. After each failed test, check OPNsense logs before editing rules.
3. Record pass or fail for each test.
4. Save screenshots for any successful milestone.

---

## 2. Pre-Checks

### 2.1 Verify IP Addresses and Gateways

On Kali:

```bash
ip a
ip route
```

Expected:

1. Kali has 192.168.60.10 or the expected OPT1-side address.
2. Default gateway is 192.168.60.1.

On Ubuntu:

```bash
ip a
ip route
```

Expected:

1. Ubuntu has 192.168.50.10 or the expected LAN-side address.
2. Default gateway is 192.168.50.1.

### 2.2 Verify Basic Reachability to Firewall Interfaces

From Kali:

```bash
ping -c 2 192.168.60.1
```

From Ubuntu:

```bash
ping -c 2 192.168.50.1
```

Expected:

1. Each host reaches its own OPNsense interface.
2. If this fails, stop and fix network attachment first.

---

## 3. Day 1 Firewall Policy Tests

### 3.1 Test Allowed Kali to Ubuntu Ports

From Kali:

```bash
nc -zv 192.168.50.10 22
nc -zv 192.168.50.10 80
nc -zv 192.168.50.10 443
nc -zv 192.168.50.10 5000
nc -zv 192.168.50.10 8080
```

Expected:

1. Only ports with real listening services and matching firewall allow rules succeed.
2. A refused connection can mean the firewall allowed it but no service is listening.
3. A timeout usually suggests filtering or routing trouble.

### 3.2 Test Blocked Kali to Ubuntu Ports

From Kali:

```bash
nc -zv 192.168.50.10 21
nc -zv 192.168.50.10 25
nc -zv 192.168.50.10 3306
```

Expected:

1. These should fail unless you explicitly allowed them.
2. Confirm block entries in OPNsense live logs.

### 3.3 Test Kali Egress Restriction

From Kali:

```bash
curl -m 5 https://example.com
ping -c 2 1.1.1.1
```

Expected:

1. These should fail if unintended outbound access is blocked.
2. OPNsense live logs should show the block.

### 3.4 Test Ubuntu to Firewall Infrastructure Access

From Ubuntu:

```bash
ping -c 2 192.168.50.1
curl -k -I https://192.168.50.1
```

Expected:

1. Ping should work.
2. HTTPS to the firewall may return a login page or certificate warning response.

### 3.5 Test Ubuntu Block to Red Network If Rule Was Added

From Ubuntu:

```bash
ping -c 2 <current-kali-ip>
nc -zv <current-kali-ip> 22
```

Expected:

1. New outbound sessions from Ubuntu to Kali should fail if you added the block rule.
2. Reply traffic to established sessions is different and may still work when state exists.

### 3.6 OPNsense Live Log Review

In OPNsense:

1. Open Firewall > Log Files > Live View.
2. Filter by the current Kali source IP.
3. Re-run one allowed test and one blocked test.
4. Confirm one pass entry and one block entry appear.

---

## 4. Day 1 DNS Control Tests

### 4.1 Test Firewall DNS from Kali

```bash
dig @192.168.60.1 example.com
```

Expected:

1. Query succeeds.
2. Response comes from the firewall IP.

### 4.2 Test Direct External DNS Block from Kali

```bash
dig @1.1.1.1 example.com
dig @8.8.8.8 example.com
```

Expected:

1. Queries fail or time out.
2. OPNsense logs show a block on port 53.

### 4.3 Test Firewall DNS from Ubuntu

```bash
dig @192.168.50.1 example.com
```

Expected:

1. Query succeeds.

### 4.4 Test Direct External DNS Block from Ubuntu

```bash
dig @1.1.1.1 example.com
```

Expected:

1. Query fails or times out.

---

## 5. Day 1 Suricata IDS Tests

### 5.1 Confirm Ubuntu Has a Simple Web Target

On Ubuntu:

```bash
sudo apt update
sudo apt install -y apache2 curl
sudo systemctl enable --now apache2
curl http://127.0.0.1
curl -I http://127.0.0.1/dvwa/login.php
```

Expected:

1. Apache is active.
2. Local curl returns DVWA/login response.

### 5.2 Confirm Kali Can Reach the Web Target

From Kali:

```bash
curl -I http://192.168.50.10/dvwa/login.php
nc -zv 192.168.50.10 80
```

Expected:

1. HTTP headers are returned.
2. TCP port 80 connects.

### 5.3 Generate Scan Traffic

From Kali:

```bash
sudo apt update
sudo apt install -y nmap nikto curl
nmap -sS -Pn -p 1-1000 192.168.50.10
nmap -sV -Pn 192.168.50.10
nikto -h http://192.168.50.10/dvwa
curl "http://192.168.50.10/dvwa/vulnerabilities/sqli/?id=1'&Submit=Submit"
curl "http://192.168.50.10/dvwa/vulnerabilities/fi/?page=../../../../etc/passwd"
curl -A "sqlmap/1.0" "http://192.168.50.10/dvwa/login.php"
```

Expected:

1. At least one of these should create Suricata alerts.
2. Not every command must trigger an alert.

### 5.4 Check Suricata Alerts

In OPNsense:

1. Open Services > Intrusion Detection > Alerts.
2. Sort newest first.
3. Filter by the currently assigned Kali source IP if possible.
4. Check for SID, message, source, destination, and action.

Expected:

1. You see traffic from Kali to Ubuntu reflected in alerts.

### 5.5 IPS Staging Test

Only after IDS alerts work:

1. Enable IPS or inline mode in Services > Intrusion Detection > Administration.
2. Re-run only one or two earlier tests.
3. Check whether some traffic is now dropped.

Expected:

1. Some suspicious requests may now fail.
2. Alerts should still be visible.

---

## 6. Day 2 API Control and REST Integration Tests

These tests verify OPNsense REST alias integration with Debian API controls before broader logging validation.

### 6.0 Verify Alias Types Before Running Any Hook Tests

In OPNsense > Firewall > Aliases, confirm:

1. `KALI_HOST` is Type `Host(s)`.
2. `AUTO_BAN_IPS` is Type `Host(s)`.

Why: This lab now uses Host(s) aliases to avoid External/table alias state edge cases that can amplify default-deny/state-violation noise. The Control API uses alias add/delete and has a fallback sync strategy for KALI_HOST changes.

### 6.1 Run the One-Shot Debian Smoke Test First

On Debian:

```bash
cd ~/lab/control-api/scripts
API_TOKEN="$TOKEN" ./debian_smoke_test.sh --api-base http://127.0.0.1:5000
```

Expected:

1. Script prints a pass or warn summary for launch/control and hook wiring.
2. Script exits non-zero only on hard failures.

### 6.2 Verify API Hook Status

On Debian:

```bash
curl http://127.0.0.1:5000/config \
  -H "X-API-Token: $TOKEN"
```

Expected:

1. `firewall_hook_enabled` is `true`.
2. `firewall_unban_hook_enabled` is `true`.
3. `firewall_integration_mode` is `opnsense-rest`.
4. `opnsense_api_enabled` is `true`.

### 6.3 Run Firewall Hook Self-Test

On Debian:

```bash
curl -X POST http://127.0.0.1:5000/firewall/hook-test \
  -H "X-API-Token: $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"ip":"192.168.60.222","reason":"point_test_hook"}'
```

Expected:

1. Response status is `ok`.
2. OPNsense table for `AUTO_BAN_IPS` changes and then reverts.
3. Response `ban.mode` and `unban.mode` show `opnsense-rest`.

### 6.4 Reassign Kali IP from API and Validate Alias Sync

On Debian:

```bash
curl -X POST http://127.0.0.1:5000/kali/network \
  -H "X-API-Token: $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"ip":"192.168.60.20"}'
```

Expected:

1. API returns the new Kali IP assignment.
2. OPNsense `KALI_HOST` table reflects the same new address.

### 6.5 Re-Run One Allowed and One Blocked Traffic Test

After reassignment, run one pass case and one block case again from Kali.

Expected:

1. Rule behavior is unchanged.
2. Logs now show the new source IP.

---

## 7. Day 2 Remote Logging Tests

### 7.1 Confirm Debian Listener Is Active

On Debian:

```bash
sudo ss -lunpt | grep -E '514|5514'
```

Expected:

1. UDP 514 or TCP 5514 is listening, depending on your setup.

### 7.2 Confirm OPNsense Firewall Logs Reach Debian

On Debian:

```bash
sudo tcpdump -ni any port 514 or port 5514
```

While tcpdump is running, generate one blocked Kali test.

Expected:

1. Packets arrive from the OPNsense IP.

### 7.3 Confirm Logs Are Written or Parsed

On Debian:

```bash
sudo journalctl -u rsyslog -n 50 --no-pager
sudo tail -n 50 /var/log/syslog
```

Expected:

1. You can see recent OPNsense-originated records or forwarding activity.

### 7.4 Confirm Suricata Logs Also Reach Debian

1. Keep log capture running on Debian.
2. Re-run one Suricata-triggering test from Kali.
3. Confirm additional IDS-related traffic appears.

Expected:

1. Firewall traffic and IDS-related traffic both arrive after categories are enabled.

---

## 8. Day 2 Optional Exposure Tests

Run only if you deliberately created a controlled exposure path.

### 8.1 Port Forward Sanity Check

In OPNsense:

1. Open Firewall > NAT > Port Forward.
2. Confirm there is no rule exposing Kali.
3. Confirm raw log or indexer ports are not exposed.

Expected:

1. Only the exact approved endpoint is present, or no public exposure exists yet.

---

## 9. Day 3 Final OPNsense Review Tests

### 9.1 Rule Table Review

In OPNsense:

1. Review OPT1 rules top to bottom.
2. Review LAN rules top to bottom.
3. Confirm temporary broad allow rules are removed if no longer needed.

Expected:

1. Policy is still least-privilege.

### 9.2 NAT Review

In OPNsense:

1. Open Firewall > NAT > Outbound.
2. Confirm no troubleshooting NAT rules remain that open broad egress.

Expected:

1. Outbound mode is still Automatic or Hybrid unless you intentionally changed it.

### 9.3 Final DNS Enforcement Test

From Kali:

```bash
dig @192.168.60.1 example.com
dig @1.1.1.1 example.com
```

From Ubuntu:

```bash
dig @192.168.50.1 example.com
dig @8.8.8.8 example.com
```

Expected:

1. Firewall DNS succeeds.
2. Direct external DNS remains blocked.

### 9.4 Export Backup Test

In OPNsense:

1. Open System > Configuration > Backups.
2. Download a backup.
3. Confirm the file downloads successfully.

Expected:

1. You have a usable backup before final demo changes.

---

## 10. Final Pass Criteria

Consider OPNsense validated only when all are true:

1. Interface and gateway checks pass.
2. Allowed Kali-to-Ubuntu services work.
3. Blocked ports are actually blocked.
4. Kali unintended outbound traffic is blocked.
5. Firewall DNS works for clients.
6. External DNS is blocked for clients.
7. Suricata generates alerts on test traffic.
8. Debian receives OPNsense logs.
9. IPS has been safely tested or deliberately left off with justification.
10. Backup export succeeds.
11. Hook self-test can ban and unban on OPNsense without manual edits.
12. Kali IP reassignment from API is reflected in `KALI_HOST` and in OPNsense logs.
