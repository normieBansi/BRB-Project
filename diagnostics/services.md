# Services

[Remote Logging]
- Transport: UDP (4)
- Application: configd(configd.py), filter(filterlog), kernel(kernel), resolver(unbound), suricata(suricata)
- Facilities: Nothing selected
- Hostname: 192.168.50.10
- Port: 514
- RFC5424: enabled
- Description: Ubuntu-Lab

---

[Services: Intrusion Detection: Policy]

[Rule details]
- Enabled
- Priority: 0
- Rulesets: botcc.portgrouped.rules, botcc.rules, ciarmy.rules, compromised.rules, drop.rules, dshield.rules, emerging-adware_pup.rules, emerging-attack_response.rules, emerging-coinminer.rules, emerging-dos.rules, emerging-exploit.rules, emerging-exploit_kit.rules, emerging-ftp.rules, emerging-malware.rules, emerging-mobile_malware.rules, emerging-phishing.rules, emerging-scan.rules, emerging-shellcode.rules, emerging-sql.rules, emerging-telnet.rules, emerging-tftp.rules, emerging-worm.rules, threatview_CS_c2.rules, tor.rules
- Actions: Disabled, Alert, Drop
- Rules: Nothing selected (against all options)
- New action: Default
- Description: ET Open baseline alert policy


Note: I did install all ET open rules, and had only enabled these selected few as other might have been noisy. 
Here's the full list of ET open rules that are installed:
ET open/emerging-pop3, ET open/emerging-rpc, ET open/emerging-scada, ET open/emerging-scanET, open/emerging-shellcode, ET open/emerging-smtp, ET open/emerging-snmp, ET open/emerging-sql, ET open/emerging-telnet, ET open/emerging-tftp, ET open/emerging-user_agents, ET open/emerging-voip, ET open/emerging-web_client, ET open/emerging-web_server, ET open/emerging-web_specific_apps, ET open/emerging-worm, ET open/threatview_CS_c2, ET open/tor

---

[System: Diagnostics: Services]
These are all enabled and are running from the start of the firewall
| Name		|	Description		|
|---------------|-------------------------------|
| configd 	| System Configuration Daemon	|
| cron		| Cron				|
| dnsmasq	| Dnsmasq DNS/DHCP		|
| hostwatch 	| Host discovery service 	|
| login		| Users and Groups		|
| ntpd		| Network Time Daemon		|
| openssh	| Secure Shell Daemon		|
| pf		| Packet Filter			|
| routing	| System routing		|
| suricata	| Intrusion Detection		|
| sysctl	| System tunables		|
| syslog-ng	| Syslog-ng Daemon		|
| unbound	| Unbound DNS			|
| webgui 	| Web GUI			|
