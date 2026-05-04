# TRex 3-Level Setup and Packet Traffic Guide

Navigation: [Kali Checklist](Kali_Checklist.md) | [Ubuntu Checklist](Ubuntu_Checklist.md) | [OPNsense Tests](OPNsense_Point_By_Point_Tests.md)

---

This guide standardizes TRex setup and packet generation with 3 traffic levels for your lab.

Lab assumptions:

1. Debian host runs Podman containers and the control API.
2. Kali traffic source network is `192.168.60.0/24`.
3. Ubuntu target is usually `192.168.50.10`.
4. OPNsense routes and inspects traffic between red and blue networks.

---

## 1. Where to Keep TRex Components

Keep the source-of-truth files in the workspace and copy to runtime paths on Debian.

Source-of-truth in repo:

1. `kali-scenarios/trex-profiles/level1_baseline.py`
2. `kali-scenarios/trex-profiles/level2_pressure.py`
3. `kali-scenarios/trex-profiles/level3_surge.py`
4. `kali-scenarios/trex-profiles/run_trex_3_levels.sh`

Runtime on Debian:

1. TRex install: `/opt/trex/v3.*`
2. Profile runtime directory: `/opt/trex/profiles`
3. Runner script location: `/opt/trex/profiles/run_trex_3_levels.sh`

Copy command on Debian:

```bash
sudo mkdir -p /opt/trex/profiles
sudo cp ~/lab/kali-scenarios/trex-profiles/*.py /opt/trex/profiles/
sudo cp ~/lab/kali-scenarios/trex-profiles/run_trex_3_levels.sh /opt/trex/profiles/
sudo chmod +x /opt/trex/profiles/run_trex_3_levels.sh
```

---

## 2. Why Debian Is Recommended Over Kali Container

TRex needs raw packet capabilities and sometimes DPDK-style NIC control.

Debian host advantages:

1. Better socket and NIC access.
2. Easier `sudo` and capability handling.
3. Fewer container network abstraction issues.

Kali container caveats:

1. Raw sockets can be blocked or limited by container network mode.
2. You may need `--privileged`, `--cap-add=NET_ADMIN`, and `--cap-add=NET_RAW`.
3. DPDK and hugepage workflows are typically harder in nested/containerized lab setups.

If you must run from Kali container, start with software mode and expect lower packet rates.

---

## 3. Install TRex on Debian

Run on Debian host:

```bash
cd /opt
sudo mkdir -p trex
cd trex
sudo wget --no-check-certificate https://trex-tgn.cisco.com/trex/release/latest
sudo tar -xzf latest
ls -la /opt/trex/
```

Find interfaces:

```bash
sudo /opt/trex/v3.*/dpdk_setup_ports.py --show
```

In VirtualBox-style labs, software mode is usually the safest start.

---

## 4. Three Traffic Levels

The included STL profiles are tuned for progressive ramp-up.

Level 1: Baseline Validation

1. Goal: sanity-check routing, logs, and IDS visibility.
2. Mix: low SYN + low UDP + low ICMP.
3. Typical run: 30 seconds.

Level 2: Pressure Test

1. Goal: moderate policy and Suricata pressure.
2. Mix: higher SYN + higher UDP + HTTP probe payload stream.
3. Typical run: 30 seconds.

Level 3: Surge Burst

1. Goal: short high-rate burst stress.
2. Mix: single-burst SYN + UDP + ICMP.
3. Typical run: 10 to 20 seconds.
4. Caution: watch VM CPU and packet drops.

---

## 5. Run the 3 Levels Sequentially

Run from Debian host:

```bash
cd /opt/trex/profiles
sudo ./run_trex_3_levels.sh
```

Optional custom source and destination:

```bash
cd /opt/trex/profiles
sudo SRC_IP=192.168.60.20 DST_IP=192.168.50.10 ./run_trex_3_levels.sh
```

If software mode causes issues in your TRex build, disable it:

```bash
cd /opt/trex/profiles
sudo USE_SOFTWARE_MODE=false ./run_trex_3_levels.sh
```

---

## 6. Manual Per-Level Commands

Use these if you want manual control:

```bash
cd /opt/trex/v3.*
sudo ./t-rex-64 -f /opt/trex/profiles/level1_baseline.py -d 30 -m 1 --no-watchdog --software -t src=192.168.60.10,dst=192.168.50.10
sudo ./t-rex-64 -f /opt/trex/profiles/level2_pressure.py -d 30 -m 1 --no-watchdog --software -t src=192.168.60.10,dst=192.168.50.10
sudo ./t-rex-64 -f /opt/trex/profiles/level3_surge.py -d 15 -m 1 --no-watchdog --software -t src=192.168.60.10,dst=192.168.50.10
```

---

## 7. Validation Checklist After Each Level

1. OPNsense live firewall logs show traffic from the current Kali source IP.
2. OPNsense Suricata alerts increase when Level 2 and Level 3 run.
3. Debian log receiver/Grafana-Loki path receives new entries.
4. CPU on OPNsense and Debian remains stable enough for lab continuity.

---

## 8. Troubleshooting Sockets in Kali Container

If you insist on running TRex from Kali container:

1. Use a container with NET_ADMIN and NET_RAW.
2. Prefer software mode first.
3. Validate raw socket capability before running TRex.

Example checks inside Kali container:

```bash
python3 - << 'PYEOF'
import socket
s = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_ICMP)
print('raw socket ok')
s.close()
PYEOF
```

If this fails, stay on Debian-host TRex for reliable packet generation.

---

## 9. Recommended Practice for Your Lab

1. Keep profile files versioned in `kali-scenarios/trex-profiles/`.
2. Run TRex on Debian host using software mode first.
3. Use Level 1 before every lab session as a quick health check.
4. Run Level 2 for IDS/ML data collection.
5. Run Level 3 only in short windows with active monitoring.
