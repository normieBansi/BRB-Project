from __future__ import annotations

import ipaddress
import json
import os
import re
import shlex
import signal
import subprocess
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Lock
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def utcnow_iso() -> str:
    return utcnow().isoformat()


def parse_csv_env(name: str, default: list[str]) -> list[str]:
    raw_value = os.environ.get(name, "")
    if not raw_value.strip():
        return default
    return [item.strip() for item in raw_value.split(",") if item.strip()]


API_TOKEN = os.environ.get("API_TOKEN")
if not API_TOKEN:
    raise RuntimeError("API_TOKEN environment variable must be set before starting the control API")

WORK_DIR = Path(os.environ.get("CONTROL_API_WORK_DIR", Path.cwd())).resolve()
STATE_DIR = Path(os.environ.get("CONTROL_API_STATE_DIR", WORK_DIR / "state")).resolve()
RUN_LOG_PATH = Path(os.environ.get("RUN_LOG_PATH", STATE_DIR / "runs.json")).resolve()
BAN_LOG_PATH = Path(os.environ.get("BAN_LOG_PATH", STATE_DIR / "bans.json")).resolve()
KALI_NETWORK_PATH = Path(os.environ.get("KALI_NETWORK_PATH", STATE_DIR / "kali_network.json")).resolve()
LOG_PATH = Path(os.environ.get("OPNSENSE_LOG_PATH", "~/logs/opnsense.log")).expanduser().resolve()
ML_RESULTS_PATH = Path(os.environ.get("ML_RESULTS_PATH", "~/lab/ml/latest_results.json")).expanduser().resolve()
ML_PREDICTIONS_PATH = Path(os.environ.get("ML_PREDICTIONS_PATH", "~/lab/ml/predictions.json")).expanduser().resolve()

KALI_CONTAINER = os.environ.get("KALI_CONTAINER", "kali-lab")
KALI_SCENARIOS_DIR = os.environ.get("KALI_SCENARIOS_DIR", "/opt/lab/scenarios")
TARGET_DEFAULT = os.environ.get("TARGET_DEFAULT", "192.168.50.10")
SSH_USER = os.environ.get("SSH_USER", "root")
MAX_CONCURRENT_RUNS = max(1, int(os.environ.get("MAX_CONCURRENT_RUNS", "3")))
KALI_ALLOWED_SUBNET = ipaddress.ip_network(os.environ.get("KALI_ALLOWED_SUBNET", "192.168.60.0/24"), strict=False)
KALI_INTERFACE = os.environ.get("KALI_INTERFACE", "eth0")
KALI_GATEWAY_IP = os.environ.get("KALI_GATEWAY_IP", "192.168.60.1")
KALI_CURRENT_IP = os.environ.get("KALI_CURRENT_IP", "192.168.60.10")
# KALI_IP_ASSIGN_CMD not defined
KALI_IP_ASSIGN_CMD = os.environ.get("KALI_IP_ASSIGN_CMD", "")
KALI_RESERVED_IPS = {
    item.strip()
    for item in os.environ.get("KALI_RESERVED_IPS", "192.168.60.1,192.168.60.2").split(",")
    if item.strip()
}

# Firewall banning mechanism is missing 
BAN_DURATION_CHOICES = [60, 300, 600, 1440]
FIREWALL_BAN_CMD = os.environ.get("FIREWALL_BAN_CMD", "")
FIREWALL_UNBAN_CMD = os.environ.get("FIREWALL_UNBAN_CMD", "")

STATE_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="NGFW Control API", version="2.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=parse_csv_env("CORS_ALLOWED_ORIGINS", ["http://localhost", "http://127.0.0.1"]),
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-API-Token"],
)

state_lock = Lock()
process_registry: dict[str, subprocess.Popen[Any]] = {}

SCENARIOS: dict[str, dict[str, str]] = {
    "tcp_syn_burst": {
        "script": "tcp_syn_burst.sh",
        "description": "Short SYN burst against the selected target.",
        "category": "transport",
    },
    "web_scan": {
        "script": "web_scan.sh",
        "description": "Nikto plus suspicious HTTP probes against the selected target.",
        "category": "application",
    },
    "ssh_bruteforce_sim": {
        "script": "ssh_bruteforce_sim.sh",
        "description": "SSH login loop using the configured SSH user.",
        "category": "application",
    },
    "sql_injection_sim": {
        "script": "sql_injection_sim.sh",
        "description": "SQL injection payloads and sqlmap probe.",
        "category": "application",
    },
    "udp_flood": {
        "script": "udp_flood.sh",
        "description": "Short UDP burst to a configurable port.",
        "category": "transport",
    },
    "icmp_flood": {
        "script": "icmp_flood.sh",
        "description": "ICMP burst for L3 visibility and rate-limit testing.",
        "category": "network",
    },
    "fin_scan": {
        "script": "fin_scan.sh",
        "description": "FIN scan against the selected target.",
        "category": "transport",
    },
    "slow_http": {
        "script": "slow_http.sh",
        "description": "Slow HTTP style connection exhaustion using low volume.",
        "category": "application",
    },
}


def load_json_list(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    return data if isinstance(data, list) else []


def load_json_dict(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


run_log: list[dict[str, Any]] = load_json_list(RUN_LOG_PATH)
ban_log: list[dict[str, Any]] = load_json_list(BAN_LOG_PATH)
kali_network_state: dict[str, Any] = load_json_dict(KALI_NETWORK_PATH) or {
    "ip": KALI_CURRENT_IP,
    "interface": KALI_INTERFACE,
    "gateway": KALI_GATEWAY_IP,
    "subnet": str(KALI_ALLOWED_SUBNET),
    "reserved_ips": sorted(KALI_RESERVED_IPS),
    "updated_at": utcnow_iso(),
    "mode": "default",
    "notes": "Adjust OPNsense aliases if they rely on a fixed Kali source IP.",
}


def save_state(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text(json.dumps(rows, indent=2), encoding="utf-8")


def save_dict_state(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def require_auth(token: str) -> None:
    if token != API_TOKEN:
        raise HTTPException(status_code=401, detail="Unauthorized")


def find_run(run_id: str) -> dict[str, Any]:
    for item in run_log:
        if item["run_id"] == run_id:
            return item
    raise HTTPException(status_code=404, detail="Run not found")


def find_ban(ip_address: str) -> dict[str, Any] | None:
    for item in ban_log:
        if item["ip"] == ip_address and item["status"] == "active":
            return item
    return None


def is_active_run(entry: dict[str, Any]) -> bool:
    return entry.get("status") not in {"stopped", "completed", "failed"}


def active_run_count() -> int:
    return sum(1 for item in run_log if is_active_run(item))


def signal_process_group(pid: int, sig: int) -> None:
    getpgid = getattr(os, "getpgid", None)
    killpg = getattr(os, "killpg", None)
    if callable(getpgid) and callable(killpg):
        try:
            killpg(getpgid(pid), sig)
        except (ProcessLookupError, PermissionError):
            pass
        return
    try:
        os.kill(pid, sig)
    except (ProcessLookupError, PermissionError):
        pass


def process_exists(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def refresh_run_states() -> None:
    changed = False
    for entry in run_log:
        if not is_active_run(entry):
            continue
        run_id = entry["run_id"]
        process_handle = process_registry.get(run_id)
        if process_handle is not None:
            return_code = process_handle.poll()
            if return_code is None:
                if entry.get("status") != "paused":
                    entry["status"] = "running"
                    changed = True
                continue
            entry["status"] = "completed" if return_code == 0 else "failed"
            entry["finished_at"] = utcnow_iso()
            entry["return_code"] = return_code
            process_registry.pop(run_id, None)
            changed = True
            continue
        pid = entry.get("pid")
        if isinstance(pid, int) and process_exists(pid):
            if entry.get("status") != "paused":
                entry["status"] = "running"
                changed = True
            continue
        entry["status"] = "completed"
        entry.setdefault("finished_at", utcnow_iso())
        process_registry.pop(run_id, None)
        changed = True
    if changed:
        save_state(RUN_LOG_PATH, run_log)


def terminate_process_group(pid: int) -> None:
    signal_process_group(pid, signal.SIGTERM)


def validate_ipv4(ip_value: str) -> str:
    try:
        return str(ipaddress.ip_address(ip_value))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid IPv4 address: {ip_value}") from exc


def validate_kali_ip(ip_value: str) -> str:
    normalized = validate_ipv4(ip_value)
    address = ipaddress.ip_address(normalized)
    if address not in KALI_ALLOWED_SUBNET:
        raise HTTPException(status_code=400, detail=f"Kali IP must be inside {KALI_ALLOWED_SUBNET}")
    if normalized in KALI_RESERVED_IPS:
        raise HTTPException(status_code=400, detail=f"Kali IP {normalized} is reserved")
    if address == KALI_ALLOWED_SUBNET.network_address or address == KALI_ALLOWED_SUBNET.broadcast_address:
        raise HTTPException(status_code=400, detail="Network and broadcast addresses cannot be assigned")
    return normalized


def run_shell_hook(command: str, payload: dict[str, Any]) -> dict[str, str]:
    if not command.strip():
        return {"mode": "record-only", "stdout": "", "stderr": ""}
    env = os.environ.copy()
    for key, value in payload.items():
        env[key] = str(value)
    completed = subprocess.run(
        ["/bin/bash", "-lc", command],
        capture_output=True,
        check=False,
        env=env,
        text=True,
    )
    if completed.returncode != 0:
        raise HTTPException(
            status_code=500,
            detail={
                "message": "Firewall hook failed",
                "stdout": completed.stdout[-400:],
                "stderr": completed.stderr[-400:],
            },
        )
    return {
        "mode": "hook",
        "stdout": completed.stdout[-400:],
        "stderr": completed.stderr[-400:],
    }


def assign_kali_ip(ip_address: str) -> dict[str, str]:
    payload = {
        "KALI_IP": ip_address,
        "KALI_INTERFACE": KALI_INTERFACE,
        "KALI_GATEWAY_IP": KALI_GATEWAY_IP,
        "KALI_ALLOWED_SUBNET": str(KALI_ALLOWED_SUBNET),
        "KALI_CONTAINER": KALI_CONTAINER,
    }
    if KALI_IP_ASSIGN_CMD.strip():
        return run_shell_hook(KALI_IP_ASSIGN_CMD, payload)
    prefix_length = KALI_ALLOWED_SUBNET.prefixlen
    shell_snippet = " ; ".join(
        [
            f"ip addr flush dev {shlex.quote(KALI_INTERFACE)}",
            f"ip addr add {shlex.quote(f'{ip_address}/{prefix_length}')} dev {shlex.quote(KALI_INTERFACE)}",
            f"ip link set {shlex.quote(KALI_INTERFACE)} up",
            f"ip route replace default via {shlex.quote(KALI_GATEWAY_IP)}",
        ]
    )
    completed = subprocess.run(
        ["sudo", "podman", "exec", KALI_CONTAINER, "/bin/bash", "-lc", shell_snippet],
        capture_output=True,
        check=False,
        text=True,
    )
    if completed.returncode != 0:
        raise HTTPException(
            status_code=500,
            detail={
                "message": "Kali IP assignment failed",
                "stdout": completed.stdout[-400:],
                "stderr": completed.stderr[-400:],
            },
        )
    return {
        "mode": "podman-exec",
        "stdout": completed.stdout[-400:],
        "stderr": completed.stderr[-400:],
    }


def release_ban(entry: dict[str, Any], reason: str) -> None:
    hook_payload = {
        "BAN_IP": entry["ip"],
        "BAN_ID": entry["ban_id"],
        "BAN_REASON": entry.get("reason", "manual"),
    }
    hook_result = run_shell_hook(FIREWALL_UNBAN_CMD, hook_payload)
    entry["status"] = "released"
    entry["released_at"] = utcnow_iso()
    entry["release_reason"] = reason
    entry["hook_mode"] = hook_result["mode"]


def cleanup_expired_bans() -> None:
    now = utcnow()
    changed = False
    for entry in ban_log:
        if entry["status"] != "active":
            continue
        expires_at = datetime.fromisoformat(entry["expires_at"])
        if expires_at <= now:
            release_ban(entry, "expired")
            changed = True
    if changed:
        save_state(BAN_LOG_PATH, ban_log)


def kali_exec_command(script_name: str, run_id: str, target_ip: str) -> list[str]:
    script_path = f"{KALI_SCENARIOS_DIR}/{script_name}"
    shell_snippet = " ; ".join(
        [
            f"export TARGET_IP={shlex.quote(target_ip)}",
            f"export SSH_USER={shlex.quote(SSH_USER)}",
            f"exec {shlex.quote(script_path)} {shlex.quote(run_id)}",
        ]
    )
    return [
        "sudo",
        "podman",
        "exec",
        KALI_CONTAINER,
        "/bin/bash",
        "-lc",
        shell_snippet,
    ]


def extract_timestamp(line: str) -> str:
    syslog_match = re.match(r"^([A-Z][a-z]{2}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2})", line)
    if not syslog_match:
        return utcnow_iso()
    try:
        parsed = datetime.strptime(f"{datetime.now().year} {syslog_match.group(1)}", "%Y %b %d %H:%M:%S")
        return parsed.replace(tzinfo=timezone.utc).isoformat()
    except ValueError:
        return utcnow_iso()


def parse_event(line: str) -> dict[str, Any]:
    lower_line = line.lower()
    ip_matches = re.findall(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", line)
    src_ip = ip_matches[0] if len(ip_matches) > 0 else "unknown"
    dst_ip = ip_matches[1] if len(ip_matches) > 1 else "unknown"
    port_match = re.search(r"(?:dpt|dst port|port)[=: ]+(\d+)", line, flags=re.IGNORECASE)
    proto_match = re.search(r"\b(TCP|UDP|ICMP)\b", line)
    msg_match = re.search(r'msg[:=]"([^"]+)"', line, flags=re.IGNORECASE)
    signature = msg_match.group(1) if msg_match else line[:120]
    if any(token in lower_line for token in ["drop", "block", "reject", "deny"]):
        action = "block"
    elif "alert" in lower_line:
        action = "alert"
    else:
        action = "pass"
    if any(token in lower_line for token in ["priority:1", "severity 1", "critical"]):
        severity = "high"
    elif any(token in lower_line for token in ["priority:2", "severity 2", "warning"]):
        severity = "medium"
    else:
        severity = "low"
    return {
        "timestamp": extract_timestamp(line),
        "raw": line[:300],
        "src_ip": src_ip,
        "dst_ip": dst_ip,
        "dst_port": int(port_match.group(1)) if port_match else 0,
        "proto": proto_match.group(1) if proto_match else "UNKNOWN",
        "action": action,
        "signature": signature,
        "severity": severity,
    }


def tail_events(limit: int) -> list[dict[str, Any]]:
    if not LOG_PATH.exists():
        return []
    lines = LOG_PATH.read_text(encoding="utf-8", errors="ignore").splitlines()
    rows = [parse_event(line) for line in lines if line.strip()]
    rows.sort(key=lambda item: item["timestamp"], reverse=True)
    return rows[:limit]


def summarize_events(events: list[dict[str, Any]]) -> dict[str, Any]:
    if not events:
        return {
            "total_alerts": 0,
            "blocked": 0,
            "high_sev": 0,
            "medium_sev": 0,
            "low_sev": 0,
            "anomalies": 0,
            "active_flows": 0,
            "over_time": [],
            "top_sources": [],
            "top_ports": [],
        }
    severity_counter = Counter(item["severity"] for item in events)
    source_counter = Counter(item["src_ip"] for item in events if item["src_ip"] != "unknown")
    port_counter = Counter(item["dst_port"] for item in events if item["dst_port"])
    bucket_counter: defaultdict[str, int] = defaultdict(int)
    for item in events:
        dt_value = datetime.fromisoformat(item["timestamp"])
        bucket = dt_value.replace(minute=(dt_value.minute // 5) * 5, second=0, microsecond=0)
        bucket_counter[bucket.strftime("%H:%M")] += 1
    return {
        "total_alerts": len(events),
        "blocked": sum(1 for item in events if item["action"] == "block"),
        "high_sev": severity_counter.get("high", 0),
        "medium_sev": severity_counter.get("medium", 0),
        "low_sev": severity_counter.get("low", 0),
        "anomalies": sum(1 for item in events if "anomaly" in item["raw"].lower()),
        "active_flows": len({(item["src_ip"], item["dst_ip"], item["dst_port"]) for item in events}),
        "over_time": [
            {"label": label, "count": count}
            for label, count in sorted(bucket_counter.items())
        ],
        "top_sources": [
            {"ip": ip_address, "count": count}
            for ip_address, count in source_counter.most_common(5)
        ],
        "top_ports": [
            {"port": port, "count": count}
            for port, count in port_counter.most_common(5)
        ],
    }


class LaunchRequest(BaseModel):
    scenario: str
    target_ip: str = Field(default=TARGET_DEFAULT)
    source_hint: str = Field(default="kali-container")


class StopRequest(BaseModel):
    reason: str = Field(default="dashboard_kill_switch")


class BanRequest(BaseModel):
    ip: str
    duration_minutes: int = Field(default=60)
    reason: str = Field(default="progressive_block")


class UnbanRequest(BaseModel):
    ip: str
    reason: str = Field(default="manual_release")


class KaliIpAssignRequest(BaseModel):
    ip: str
    reason: str = Field(default="dashboard_readdress")


class RunControlRequest(BaseModel):
    reason: str = Field(default="dashboard_control")


def stop_run_entry(entry: dict[str, Any], reason: str) -> dict[str, Any]:
    if not is_active_run(entry):
        return entry
    stop_cmd = ["sudo", "podman", "exec", KALI_CONTAINER, "pkill", "-TERM", "-f", entry["run_id"]]
    subprocess.run(stop_cmd, check=False, capture_output=True, text=True)
    pid = entry.get("pid")
    if isinstance(pid, int):
        terminate_process_group(pid)
    entry["status"] = "stopped"
    entry["stopped_at"] = utcnow_iso()
    entry["stop_reason"] = reason
    process_registry.pop(entry["run_id"], None)
    return entry


def pause_run_entry(entry: dict[str, Any], reason: str) -> dict[str, Any]:
    if not is_active_run(entry):
        raise HTTPException(status_code=409, detail="Run is not active")
    if entry.get("status") == "paused":
        return entry
    run_id = entry["run_id"]
    pause_cmd = ["sudo", "podman", "exec", KALI_CONTAINER, "pkill", "-STOP", "-f", run_id]
    subprocess.run(pause_cmd, check=False, capture_output=True, text=True)
    pid = entry.get("pid")
    if isinstance(pid, int):
        signal_process_group(pid, signal.SIGSTOP)
    entry["status"] = "paused"
    entry["paused_at"] = utcnow_iso()
    entry["pause_reason"] = reason
    return entry


def resume_run_entry(entry: dict[str, Any], reason: str) -> dict[str, Any]:
    if not is_active_run(entry):
        raise HTTPException(status_code=409, detail="Run is not active")
    if entry.get("status") != "paused":
        return entry
    run_id = entry["run_id"]
    resume_cmd = ["sudo", "podman", "exec", KALI_CONTAINER, "pkill", "-CONT", "-f", run_id]
    subprocess.run(resume_cmd, check=False, capture_output=True, text=True)
    pid = entry.get("pid")
    if isinstance(pid, int):
        signal_process_group(pid, signal.SIGCONT)
    entry["status"] = "running"
    entry["resumed_at"] = utcnow_iso()
    entry["resume_reason"] = reason
    return entry


@app.get("/health")
def healthcheck() -> dict[str, Any]:
    cleanup_expired_bans()
    refresh_run_states()
    return {
        "status": "ok",
        "log_path": str(LOG_PATH),
        "runs": len(run_log),
        "active_bans": len([item for item in ban_log if item["status"] == "active"]),
    }


@app.get("/config")
def get_config(x_api_token: str = Header(default="")) -> dict[str, Any]:
    require_auth(x_api_token)
    cleanup_expired_bans()
    refresh_run_states()
    return {
        "scenarios": [
            {
                "id": scenario_id,
                "description": data["description"],
                "category": data["category"],
            }
            for scenario_id, data in SCENARIOS.items()
        ],
        "ban_durations_minutes": BAN_DURATION_CHOICES,
        "firewall_hook_enabled": bool(FIREWALL_BAN_CMD.strip()),
        "default_target_ip": TARGET_DEFAULT,
        "max_concurrent_runs": MAX_CONCURRENT_RUNS,
        "kali_network": {
            "subnet": str(KALI_ALLOWED_SUBNET),
            "reserved_ips": sorted(KALI_RESERVED_IPS),
            "current_ip": kali_network_state.get("ip", KALI_CURRENT_IP),
            "gateway": KALI_GATEWAY_IP,
            "interface": KALI_INTERFACE,
            "notes": "If OPNsense aliases reference a fixed Kali IP, update them after reassignment.",
        },
    }


@app.post("/launch")
def launch(req: LaunchRequest, x_api_token: str = Header(default="")) -> dict[str, Any]:
    require_auth(x_api_token)
    cleanup_expired_bans()
    if req.scenario not in SCENARIOS:
        raise HTTPException(status_code=400, detail="Scenario not allowed")
    req.target_ip = validate_ipv4(req.target_ip)
    if active_run_count() >= MAX_CONCURRENT_RUNS:
        raise HTTPException(
            status_code=409,
            detail=f"Concurrent attack cap reached ({MAX_CONCURRENT_RUNS}). Stop an active run before launching another.",
        )
    run_id = str(uuid4())
    cmd = kali_exec_command(SCENARIOS[req.scenario]["script"], run_id, req.target_ip)
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    process_registry[run_id] = process
    entry = {
        "run_id": run_id,
        "scenario": req.scenario,
        "target_ip": req.target_ip,
        "source_hint": req.source_hint,
        "submitted_at": utcnow_iso(),
        "status": "running",
        "pid": process.pid,
    }
    with state_lock:
        run_log.insert(0, entry)
        del run_log[100:]
        save_state(RUN_LOG_PATH, run_log)
    return entry


@app.get("/runs")
def get_runs(x_api_token: str = Header(default="")) -> dict[str, Any]:
    require_auth(x_api_token)
    cleanup_expired_bans()
    refresh_run_states()
    return {"runs": run_log[:30]}


@app.post("/runs/{run_id}/stop")
def stop_run(run_id: str, req: StopRequest, x_api_token: str = Header(default="")) -> dict[str, Any]:
    require_auth(x_api_token)
    cleanup_expired_bans()
    refresh_run_states()
    entry = find_run(run_id)
    stop_run_entry(entry, req.reason)
    with state_lock:
        save_state(RUN_LOG_PATH, run_log)
    return entry


@app.post("/runs/{run_id}/pause")
def pause_run(run_id: str, req: RunControlRequest, x_api_token: str = Header(default="")) -> dict[str, Any]:
    require_auth(x_api_token)
    cleanup_expired_bans()
    refresh_run_states()
    entry = find_run(run_id)
    pause_run_entry(entry, req.reason)
    with state_lock:
        save_state(RUN_LOG_PATH, run_log)
    return entry


@app.post("/runs/{run_id}/resume")
def resume_run(run_id: str, req: RunControlRequest, x_api_token: str = Header(default="")) -> dict[str, Any]:
    require_auth(x_api_token)
    cleanup_expired_bans()
    refresh_run_states()
    entry = find_run(run_id)
    resume_run_entry(entry, req.reason)
    with state_lock:
        save_state(RUN_LOG_PATH, run_log)
    return entry


@app.post("/runs/stop-all")
def stop_all_runs(req: StopRequest, x_api_token: str = Header(default="")) -> dict[str, Any]:
    require_auth(x_api_token)
    cleanup_expired_bans()
    refresh_run_states()
    stopped_runs: list[dict[str, Any]] = []
    with state_lock:
        for entry in run_log:
            if is_active_run(entry):
                stopped_runs.append(stop_run_entry(entry, req.reason))
        save_state(RUN_LOG_PATH, run_log)
    return {
        "stopped": len(stopped_runs),
        "reason": req.reason,
        "run_ids": [item["run_id"] for item in stopped_runs],
    }


@app.get("/firewall/status")
def firewall_status(x_api_token: str = Header(default="")) -> dict[str, Any]:
    require_auth(x_api_token)
    cleanup_expired_bans()
    return {
        "ban_hook_enabled": bool(FIREWALL_BAN_CMD.strip()),
        "unban_hook_enabled": bool(FIREWALL_UNBAN_CMD.strip()),
        "active_bans": len([item for item in ban_log if item["status"] == "active"]),
        "supported_durations_minutes": BAN_DURATION_CHOICES,
    }


@app.get("/firewall/bans")
def list_bans(x_api_token: str = Header(default="")) -> dict[str, Any]:
    require_auth(x_api_token)
    cleanup_expired_bans()
    return {"bans": ban_log}


@app.get("/kali/network")
def get_kali_network(x_api_token: str = Header(default="")) -> dict[str, Any]:
    require_auth(x_api_token)
    cleanup_expired_bans()
    return {
        "ip": kali_network_state.get("ip", KALI_CURRENT_IP),
        "interface": KALI_INTERFACE,
        "gateway": KALI_GATEWAY_IP,
        "subnet": str(KALI_ALLOWED_SUBNET),
        "reserved_ips": sorted(KALI_RESERVED_IPS),
        "mode": kali_network_state.get("mode", "default"),
        "updated_at": kali_network_state.get("updated_at", utcnow_iso()),
        "notes": "Readdressing Kali may require OPNsense alias updates if you use fixed source-IP aliases.",
    }


@app.post("/kali/network")
def set_kali_network(req: KaliIpAssignRequest, x_api_token: str = Header(default="")) -> dict[str, Any]:
    require_auth(x_api_token)
    cleanup_expired_bans()
    ip_address = validate_kali_ip(req.ip)
    hook_result = assign_kali_ip(ip_address)
    kali_network_state.update(
        {
            "ip": ip_address,
            "interface": KALI_INTERFACE,
            "gateway": KALI_GATEWAY_IP,
            "subnet": str(KALI_ALLOWED_SUBNET),
            "reserved_ips": sorted(KALI_RESERVED_IPS),
            "updated_at": utcnow_iso(),
            "reason": req.reason,
            "mode": hook_result["mode"],
            "notes": "Readdressing Kali may require OPNsense alias updates if you use fixed source-IP aliases.",
        }
    )
    with state_lock:
        save_dict_state(KALI_NETWORK_PATH, kali_network_state)
    return kali_network_state


@app.post("/firewall/ban")
def create_ban(req: BanRequest, x_api_token: str = Header(default="")) -> dict[str, Any]:
    require_auth(x_api_token)
    cleanup_expired_bans()
    if req.duration_minutes not in BAN_DURATION_CHOICES:
        raise HTTPException(status_code=400, detail=f"duration_minutes must be one of {BAN_DURATION_CHOICES}")
    existing = find_ban(req.ip)
    if existing:
        raise HTTPException(status_code=409, detail="IP already has an active ban")
    entry = {
        "ban_id": str(uuid4()),
        "ip": req.ip,
        "reason": req.reason,
        "created_at": utcnow_iso(),
        "expires_at": (utcnow() + timedelta(minutes=req.duration_minutes)).isoformat(),
        "duration_minutes": req.duration_minutes,
        "status": "active",
    }
    hook_result = run_shell_hook(
        FIREWALL_BAN_CMD,
        {
            "BAN_IP": entry["ip"],
            "BAN_ID": entry["ban_id"],
            "BAN_REASON": entry["reason"],
            "BAN_DURATION_MINUTES": entry["duration_minutes"],
        },
    )
    entry["hook_mode"] = hook_result["mode"]
    with state_lock:
        ban_log.insert(0, entry)
        save_state(BAN_LOG_PATH, ban_log)
    return entry


@app.post("/firewall/unban")
def remove_ban(req: UnbanRequest, x_api_token: str = Header(default="")) -> dict[str, Any]:
    require_auth(x_api_token)
    cleanup_expired_bans()
    entry = find_ban(req.ip)
    if not entry:
        raise HTTPException(status_code=404, detail="Active ban not found for IP")
    release_ban(entry, req.reason)
    with state_lock:
        save_state(BAN_LOG_PATH, ban_log)
    return entry


@app.get("/telemetry/events")
def get_events(limit: int = 20, x_api_token: str = Header(default="")) -> dict[str, Any]:
    require_auth(x_api_token)
    cleanup_expired_bans()
    return {"events": tail_events(limit)}


@app.get("/telemetry/summary")
def get_summary(limit: int = 200, x_api_token: str = Header(default="")) -> dict[str, Any]:
    require_auth(x_api_token)
    cleanup_expired_bans()
    return summarize_events(tail_events(limit))


@app.get("/ml/summary")
def get_ml_summary(x_api_token: str = Header(default="")) -> dict[str, Any]:
    require_auth(x_api_token)
    cleanup_expired_bans()
    if not ML_RESULTS_PATH.exists():
        return {
            "total_scored": 0,
            "anomaly_pct": "0.0",
            "top_class": "none",
            "distribution": {},
            "trend": [],
        }
    return json.loads(ML_RESULTS_PATH.read_text(encoding="utf-8"))


@app.get("/ml/predictions")
def get_ml_predictions(limit: int = 15, x_api_token: str = Header(default="")) -> dict[str, Any]:
    require_auth(x_api_token)
    cleanup_expired_bans()
    if not ML_PREDICTIONS_PATH.exists():
        return {"predictions": []}
    data = json.loads(ML_PREDICTIONS_PATH.read_text(encoding="utf-8"))
    return {"predictions": data[:limit]}