# OPNsense Click-by-Click Checklist

**Navigation:** [Kali Checklist](Kali_Checklist.md) | [Ubuntu Checklist](Ubuntu_Checklist.md) | [Lab Guide](NGFW_3Day_Lab_Guide.md)

---

This document is a direct execution checklist for the OPNsense part of the project. It is intentionally procedural. Follow it in order.

Lab context for this checklist:

1. OPNsense runs in its own VM with 2 vCPU, 2 GB RAM, and 10 GB storage.
2. Debian runs in a separate VM with 4 vCPU, 4 GB RAM, and 40 GB storage.
3. Debian hosts the Podman containers for Kali and Ubuntu.
4. Kali lives on 192.168.60.0/24 behind OPT1.
5. Ubuntu lives on 192.168.50.0/24 behind LAN.
6. Keep OPNsense work lightweight and do heavier logging, dashboard, ML, and traffic generation work on Debian.

---

## Day 1 - Base OPNsense Policy and IDS Baseline

## 1. Before Logging In

1. Confirm OPNsense interfaces are assigned correctly:
   - WAN = internet-facing adapter
   - LAN = 192.168.50.1/24
   - OPT1 = 192.168.60.1/24
2. Confirm Ubuntu is in 192.168.50.0/24 and Kali is in 192.168.60.0/24.
3. Confirm each VM uses OPNsense as default gateway.
4. Take a snapshot before changes.

---

## 2. Base System Setup

### 2.1 Update Firmware

1. Log in to OPNsense web UI.
2. Open System > Firmware > Updates.
3. Click Check for updates.
4. Install updates.
5. Reboot if prompted.

### 2.2 Time and Basic Settings

1. Open System > Settings > General.
2. Set correct timezone.
3. Verify DNS servers if WAN DNS is required.

Save.

### 2.3 Admin Access Hardening

1. Open System > Access > Administration.
2. Keep GUI accessible only on trusted interface.
3. If SSH is enabled, prefer key auth.

Save.

---

## 3. Create All Required Aliases First

Open Firewall > Aliases.

Create these aliases one by one:

1. KALI_HOST = 192.168.60.10
2. UBUNTU_HOST = 192.168.50.10
3. LAB_NET_RED = 192.168.60.0/24
4. LAB_NET_BLUE = 192.168.50.0/24
5. FIREWALL_LAN_IP = 192.168.50.1
6. FIREWALL_OPT1_IP = 192.168.60.1
7. TEST_TARGET_PORTS = 22,80,443,5000,8080
8. OPSENSE_INFRA_PORTS = 53,123,443,514,5514
9. DNS_PORT = 53

After each alias:

Save.

Apply changes if prompted.

---

## 4. OPT1 Rules (Kali Side)

Open Firewall > Rules > OPT1.

Create these rules in this exact order.

### 4.1 Allow Kali to Ubuntu Test Services

1. Click Add.
2. Action = Pass
3. Interface = OPT1
4. Protocol = TCP
5. Source = KALI_HOST
6. Destination = UBUNTU_HOST
7. Destination port range = TEST_TARGET_PORTS
8. Log = enabled
9. Description = Allow Kali to Ubuntu test services
10. Save

### 4.2 Allow Kali DNS to Firewall

1. Click Add.
2. Action = Pass
3. Interface = OPT1
4. Protocol = TCP/UDP
5. Source = KALI_HOST
6. Destination = OPT1 address
7. Destination port range = DNS_PORT
8. Log = enabled
9. Description = Allow Kali DNS to firewall
10. Save

### 4.3 Block Kali External DNS

1. Click Add.
2. Action = Block
3. Interface = OPT1
4. Protocol = TCP/UDP
5. Source = KALI_HOST
6. Destination = any
7. Destination port range = 53
8. Log = enabled
9. Description = Block Kali external DNS
10. Save

### 4.4 Block Kali to WAN/Other Unintended Egress

1. Click Add.
2. Action = Block
3. Interface = OPT1
4. Protocol = any
5. Source = KALI_HOST
6. Destination = any
7. Log = enabled
8. Description = Block Kali unintended outbound
9. Save

### 4.5 Apply Rule Changes

1. Click Apply Changes.
2. Confirm rules appear in intended top-down order.

---

## 5. LAN Rules (Ubuntu Side)

Open Firewall > Rules > LAN.

Create these rules in this exact order.

### 5.1 Allow Ubuntu to Firewall Services

1. Click Add.
2. Action = Pass
3. Interface = LAN
4. Protocol = TCP/UDP
5. Source = UBUNTU_HOST
6. Destination = FIREWALL_LAN_IP
7. Destination port range = OPSENSE_INFRA_PORTS
8. Log = enabled
9. Description = Allow Ubuntu to firewall services
10. Save

### 5.2 Allow Ubuntu DNS to Firewall

1. Click Add.
2. Action = Pass
3. Interface = LAN
4. Protocol = TCP/UDP
5. Source = UBUNTU_HOST
6. Destination = LAN address
7. Destination port range = DNS_PORT
8. Log = enabled
9. Description = Allow Ubuntu DNS to firewall
10. Save

### 5.3 Allow Temporary Ubuntu Outbound for Updates

1. Click Add.
2. Action = Pass
3. Interface = LAN
4. Protocol = TCP/UDP
5. Source = UBUNTU_HOST
6. Destination = any
7. Log = enabled
8. Description = Temporary Ubuntu outbound
9. Save

### 5.4 Block Ubuntu External DNS

1. Click Add.
2. Action = Block
3. Interface = LAN
4. Protocol = TCP/UDP
5. Source = UBUNTU_HOST
6. Destination = any
7. Destination port range = 53
8. Log = enabled
9. Description = Block Ubuntu external DNS
10. Save

### 5.5 Optional Block Ubuntu to Red Network

1. Click Add.
2. Action = Block
3. Interface = LAN
4. Protocol = any
5. Source = UBUNTU_HOST
6. Destination = LAB_NET_RED
7. Log = enabled
8. Description = Block Ubuntu to Kali network
9. Save

### 5.6 Apply Rule Changes

1. Click Apply Changes.
2. Confirm rules are in expected order.

---

## 6. NAT Check

Open Firewall > NAT > Outbound.

1. Leave mode as Automatic or Hybrid.
2. Do not create broad custom NAT entries yet.
3. Do not create inbound port forwards yet.

---

## 7. Connectivity Validation

### 7.1 From Kali

Run:

```bash
nc -zv 192.168.50.10 22
nc -zv 192.168.50.10 80
nc -zv 192.168.50.10 3306
curl -m 5 https://example.com
```

Expected:

1. Allowed Ubuntu ports connect.
2. Blocked ports fail.
3. Internet access should fail if you blocked Kali egress.

### 7.2 From Ubuntu

Run:

```bash
ping -c 2 192.168.50.1
dig @192.168.50.1 example.com
```

Expected:

1. Ubuntu reaches firewall.
2. DNS through firewall works after Unbound is enabled.

### 7.3 In OPNsense Logs

1. Open Firewall > Log Files > Live View.
2. Filter by source 192.168.60.10.
3. Confirm pass and block entries appear.

---

## 8. Suricata Setup

### 8.1 Enable Service

1. Open Services > Intrusion Detection > Administration.
2. Check Enable.
3. Select interfaces:
   - LAN
   - OPT1

Save.

### 8.2 Download Rules

1. Open Services > Intrusion Detection > Download.
2. Enable ET Open only for the first pass.
3. Leave abuse.ch disabled for now.
4. Leave OPNsense-App-detect disabled for now.
5. Click Download or Update Rules.
6. Wait for completion.

### 8.3 Set HOME_NET

1. Return to Services > Intrusion Detection > Administration.
2. Find HOME_NET or Home Networks field.
3. Enter:

```text
192.168.50.0/24,192.168.60.0/24
```

Save.

### 8.4 Policy Setup

1. Open Services > Intrusion Detection > Policy.
2. Create a new policy entry if required.
3. Use ET Open as source.
4. Set action to Alert first.

Save.

### 8.5 Start in IDS Mode

1. Return to Services > Intrusion Detection > Administration.
2. Ensure IPS/inline drop mode is still off.
3. Start service.

---

## 9. Suricata Validation

### 9.1 Prepare Ubuntu Web Target

On Ubuntu:

```bash
sudo apt update
sudo apt install -y apache2 curl
sudo service apache2 start
curl http://127.0.0.1
```

### 9.2 Confirm Reachability from Kali

```bash
curl -I http://192.168.50.10
nc -zv 192.168.50.10 80
```

### 9.3 Generate Alert Traffic from Kali

```bash
sudo apt update
sudo apt install -y nmap curl nikto
nmap -sS -Pn -p 1-1000 192.168.50.10
nmap -sV -Pn 192.168.50.10
nikto -h http://192.168.50.10
curl "http://192.168.50.10/?id=1'"
curl "http://192.168.50.10/../../../../etc/passwd"
curl -A "sqlmap/1.0" "http://192.168.50.10/"
```

### 9.4 Check Alerts

1. Open Services > Intrusion Detection > Alerts.
2. Sort by newest first.
3. Filter for source 192.168.60.10 if possible.
4. Look for SID, message, source, destination.

### 9.5 Enable IPS Only After IDS Works

1. Return to Services > Intrusion Detection > Administration.
2. Enable IPS / inline mode.
3. Apply.
4. Re-run one or two earlier tests.
5. Check whether events are now dropped or rejected.

---

## 10. Unbound DNS

### 10.1 Enable Unbound

1. Open Services > Unbound DNS > General.
2. Enable Unbound.
3. Select interfaces:
   - LAN
   - OPT1
   - Localhost if available
4. Save and Apply.

### 10.2 Validate Firewall DNS

1. Open Interfaces > Diagnostics > DNS Lookup.
2. Query `example.com`.
3. Confirm resolution succeeds.

### 10.3 Validate from Clients

From Kali:

```bash
dig @192.168.60.1 example.com
dig @1.1.1.1 example.com
```

Expected:

1. Firewall DNS works.
2. External DNS is blocked.

---

## 11. Remote Logging to Ubuntu

### 11.1 Configure Target

1. Open System > Settings > Logging / Targets.
2. Add new target.
3. Enter Ubuntu IP.
4. Start with UDP 514.
5. Enable categories:
   - firewall only first
6. Save and Apply.

### 11.2 Validate

On Ubuntu:

```bash
sudo tcpdump -ni any port 514
```

Expected: packets from OPNsense arrive.

### 11.3 Expand Log Categories

After validation:

1. Add system logs.
2. Add IDS/Suricata logs.
3. Validate again.

---

## Day 2 - OPNsense Support for Logging, Dashboard, and Controlled Access

## 12. Day 2 Preconditions

Only continue when these are true:

1. Day 1 firewall rules are working.
2. Suricata is producing alerts in IDS mode.
3. Debian is reachable at the Ubuntu-side IP you plan to use for log collection and dashboards.
4. Debian has rsyslog or another listener ready before you point OPNsense logging at it.

---

## 13. Day 2 Logging and Management Steps

### 13.1 Confirm OPNsense Can Reach Debian Services

1. Open Interfaces > Diagnostics > Ping if available, or use System > Diagnostics > Ping.
2. Ping the Debian-side service IP on the LAN segment.
3. If Debian is represented by the Ubuntu container IP for logging, ping 192.168.50.10.
4. If ping fails, stop and fix routing before changing logging settings.

### 13.2 Configure Remote Logging in Stages

1. Open System > Settings > Logging / Targets.
2. Edit the existing remote target or add a new one.
3. Target host = Debian or Ubuntu-side listener IP.
4. Start with transport = UDP.
5. Port = 514.
6. Select only firewall logs first.
7. Save and Apply.
8. Wait 10 to 20 seconds.
9. Generate a test firewall event from Kali.
10. Confirm the packets arrive on Debian before enabling more categories.

### 13.3 Add Suricata Logs After Firewall Logs Work

1. Stay in System > Settings > Logging / Targets.
2. Edit the same target.
3. Add Intrusion Detection or Suricata category.
4. Save and Apply.
5. Re-run one Suricata-triggering test from Kali.
6. Confirm Debian receives both firewall and IDS-related logs.

### 13.4 Review Local OPNsense Logging Health

1. Open System > Log Files > General.
2. Check for repeated syslog forwarding errors.
3. Open Services > Intrusion Detection > Administration.
4. Confirm service is still running after enabling remote logging.
5. If the firewall feels slow, avoid enabling unnecessary feeds on OPNsense and keep heavy analysis on Debian.

### 13.5 Create a Restricted Automation User Only If Needed

Do this only if you later automate OPNsense actions.

1. Open System > Access > Users.
2. Click Add.
3. Username = dedicated automation name.
4. Set a strong password.
5. Grant only the minimum permissions required.
6. Do not reuse the main admin account for scripts.
7. Save.

---

## 14. Day 2 Optional Publishing Support

### 14.1 Keep Exposure Minimal

1. Do not port-forward Kali.
2. Do not port-forward raw syslog, indexer, or database ports.
3. If public access is needed later, expose only the reverse proxy or dashboard/API entry point.

### 14.2 If You Must Add a Temporary Port Forward Later

1. Open Firewall > NAT > Port Forward.
2. Add only the exact destination host and exact destination port needed.
3. Restrict source addresses if possible.
4. Add a clear description.
5. Save and Apply.
6. Test from a controlled client only.
7. Remove the rule when it is no longer required.

---

## Day 3 - OPNsense Final Validation, IPS Staging, and Evidence Capture

## 15. Day 3 IPS and Final Hardening Steps

### 15.1 Reconfirm Resource-Safe Settings

Because OPNsense only has 2 GB RAM and 2 cores:

1. Keep ET Open as the main Suricata source.
2. Do not enable every available ruleset family.
3. Avoid turning on extra app-detect feeds unless you have a specific test for them.
4. Watch dashboard responsiveness and OPNsense web UI responsiveness after each change.

### 15.2 Move from IDS to IPS Carefully

1. Open Services > Intrusion Detection > Administration.
2. Confirm IDS mode is working first.
3. Enable IPS or inline mode.
4. Save and Apply.
5. Re-run only one or two known-trigger tests first.
6. Check Alerts again.
7. Check Firewall > Log Files > Live View for blocked or dropped traffic.
8. If normal lab traffic breaks too broadly, disable IPS and reduce enabled categories.

### 15.3 Final OPNsense Rule Review

1. Open Firewall > Rules > OPT1.
2. Confirm only the intended Kali-to-Ubuntu paths are passed.
3. Open Firewall > Rules > LAN.
4. Confirm Ubuntu-side allowances are still narrow.
5. Open Firewall > NAT > Outbound.
6. Confirm no unnecessary broad custom NAT rules were added during troubleshooting.

### 15.4 Final DNS Review

1. Open Services > Unbound DNS > General.
2. Confirm Unbound is enabled only on required interfaces.
3. Confirm client DNS rules still force Kali and Ubuntu to use the firewall.
4. Re-test direct DNS to an outside resolver to verify it is still blocked.

---

## 16. Optional Internet Publishing Support

Only do this after local dashboard/API works.

### 16.1 NAT/Exposure Rule

1. Do not create direct forwards to Kali.
2. If you must expose something through OPNsense later, expose only reverse proxy or controlled dashboard/API endpoints.
3. Keep internal log/indexer ports private.

### 16.2 API Access for Automation

If you plan to automate OPNsense later:

1. Open System > Access > Users.
2. Create a dedicated automation user if needed.
3. Grant only minimum permissions.
4. Do not use the main admin account for scripts.

---

## 17. Backup and Evidence Collection

### 17.1 Export Configuration

1. Open System > Configuration > Backups.
2. Download a config backup after each stable milestone.

### 17.2 Capture Evidence

Collect these:

1. Screenshot of aliases
2. Screenshot of OPT1 rules
3. Screenshot of LAN rules
4. Screenshot of Suricata settings
5. Screenshot of alerts page
6. Screenshot of logging target
7. Screenshot of remote log packets arriving on Debian
8. Screenshot of final IPS mode setting if enabled

---

## 18. Minimum OPNsense Success Checklist

You are done with the OPNsense side when all are true:

1. Kali can reach only intended Ubuntu ports.
2. Kali cannot reach unintended external destinations.
3. Ubuntu can use firewall DNS.
4. External DNS from clients is blocked.
5. ET Open rules are downloaded.
6. Suricata sees alerts for Kali-to-Ubuntu test traffic.
7. Ubuntu receives OPNsense logs.
8. Debian-side dashboard/log receiver sees forwarded OPNsense logs.
9. IPS mode has been tested safely or deliberately left in IDS with reason noted.
10. Configuration backup is exported.

---

## 19. If Something Fails

Use this order:

1. Check interface/IP/gateway.
2. Check aliases.
3. Check rule order.
4. Check firewall live logs.
5. Check Suricata service and HOME_NET.
6. Check Ubuntu syslog listener.
7. Re-test one change at a time.
End of checklist.
