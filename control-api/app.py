from __future__ import annotations

import base64
import ipaddress
import json
import os
import re
import shlex
import signal
import ssl
import subprocess
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Lock
from typing import Any
from urllib import error as urllib_error
from urllib import parse as urllib_parse
from urllib import request as urllib_request
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


def parse_bool_env(name: str, default: bool = False) -> bool:
    raw_value = os.environ.get(name)
    if raw_value is None:
        return default
    return raw_value.strip().lower() in {"1", "true", "yes", "on"}


def parse_network_csv_env(name: str, default: list[str]) -> list[ipaddress.IPv4Network]:
    raw_value = os.environ.get(name, "")
    values = [item.strip() for item in raw_value.split(",") if item.strip()] if raw_value.strip() else default
    networks: list[ipaddress.IPv4Network] = []
    for value in values:
        try:
            parsed = ipaddress.ip_network(value, strict=False)
        except ValueError:
            continue
        if isinstance(parsed, ipaddress.IPv4Network):
            networks.append(parsed)
    return networks


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
DASHBOARD_ACTION_LOG_PATH = Path(
    os.environ.get("DASHBOARD_ACTION_LOG_PATH", STATE_DIR / "dashboard_actions.log")
).expanduser().resolve()

KALI_CONTAINER = os.environ.get("KALI_CONTAINER", "kali-lab")
KALI_SCENARIOS_DIR = os.environ.get("KALI_SCENARIOS_DIR", "/opt/lab/scenarios")
TARGET_DEFAULT = os.environ.get("TARGET_DEFAULT", "192.168.50.10")
TARGET_PROFILE = os.environ.get("TARGET_PROFILE", "ubuntu-apache2")
SSH_USER = os.environ.get("SSH_USER", "root")
MAX_CONCURRENT_RUNS = max(1, int(os.environ.get("MAX_CONCURRENT_RUNS", "3")))
KALI_ALLOWED_SUBNET = ipaddress.ip_network(os.environ.get("KALI_ALLOWED_SUBNET", "192.168.60.0/24"), strict=False)
KALI_INTERFACE = os.environ.get("KALI_INTERFACE", "eth0")
KALI_GATEWAY_IP = os.environ.get("KALI_GATEWAY_IP", "192.168.60.1")
KALI_CURRENT_IP = os.environ.get("KALI_CURRENT_IP", "192.168.60.10")
KALI_RESERVED_IPS = {
    item.strip()
    for item in os.environ.get("KALI_RESERVED_IPS", "192.168.60.1,192.168.60.2").split(",")
    if item.strip()
}

# OPNsense REST API integration (preferred over SSH-based hooks).
OPNSENSE_API_BASE_URL = os.environ.get("OPNSENSE_API_BASE_URL", "").strip().rstrip("/")
OPNSENSE_API_KEY = os.environ.get("OPNSENSE_API_KEY", "").strip()
OPNSENSE_API_SECRET = os.environ.get("OPNSENSE_API_SECRET", "").strip()
OPNSENSE_API_VERIFY_TLS = parse_bool_env("OPNSENSE_API_VERIFY_TLS", default=False)
OPNSENSE_API_TIMEOUT_SECONDS = max(1, int(os.environ.get("OPNSENSE_API_TIMEOUT_SECONDS", "4")))
PODMAN_COMMAND_TIMEOUT_SECONDS = max(1, int(os.environ.get("PODMAN_COMMAND_TIMEOUT_SECONDS", "8")))
OPNSENSE_BAN_ALIAS_TABLE = os.environ.get("OPNSENSE_BAN_ALIAS_TABLE", "AUTO_BAN_IPS").strip()
OPNSENSE_KALI_ALIAS_TABLE = os.environ.get("OPNSENSE_KALI_ALIAS_TABLE", "KALI_HOST").strip()
CORS_ALLOWED_ORIGINS = parse_csv_env("CORS_ALLOWED_ORIGINS", ["http://localhost", "http://127.0.0.1"])
CORS_ALLOW_PRIVATE_NETWORKS = parse_bool_env("CORS_ALLOW_PRIVATE_NETWORKS", default=True)
CORS_ALLOW_ORIGIN_REGEX = os.environ.get("CORS_ALLOW_ORIGIN_REGEX", "").strip()
if not CORS_ALLOW_ORIGIN_REGEX and CORS_ALLOW_PRIVATE_NETWORKS:
    CORS_ALLOW_ORIGIN_REGEX = (
        r"^https?://"
        r"(localhost|127\.0\.0\.1|10(?:\.\d{1,3}){3}|192\.168(?:\.\d{1,3}){2}|"
        r"172\.(?:1[6-9]|2\d|3[0-1])(?:\.\d{1,3}){2})"
        r"(?::\d+)?$"
    )
TELEMETRY_LAB_SUBNETS = parse_network_csv_env(
    "TELEMETRY_LAB_SUBNETS",
    ["192.168.50.0/24", "192.168.60.0/24"],
)
TELEMETRY_BUCKET_SECONDS_CHOICES = {30, 60, 120, 180, 300}
TELEMETRY_EXCLUDED_IPS = {
    item.strip()
    for item in os.environ.get(
        "TELEMETRY_EXCLUDED_IPS",
        "192.168.50.1,192.168.50.2,192.168.60.1,192.168.60.2",
    ).split(",")
    if item.strip()
}

BAN_DURATION_CHOICES = [60, 300, 600, 1440]

ALIAS_NAME_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")
IPV4_PATTERN = re.compile(r"(?:\d{1,3}\.){3}\d{1,3}")

STATE_DIR.mkdir(parents=True, exist_ok=True)
try:
    DASHBOARD_ACTION_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    DASHBOARD_ACTION_LOG_PATH.touch(exist_ok=True)
except OSError:
    # Do not block API startup if action log path is not writable yet.
    pass

app = FastAPI(title="NGFW Control API", version="2.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ALLOWED_ORIGINS,
    allow_origin_regex=CORS_ALLOW_ORIGIN_REGEX or None,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "X-API-Token", "Cache-Control", "Pragma"],
)

state_lock = Lock()
action_log_lock = Lock()
process_registry: dict[str, subprocess.Popen[Any]] = {}

SIGSTOP_SIGNAL = getattr(signal, "SIGSTOP", None)
SIGCONT_SIGNAL = getattr(signal, "SIGCONT", None)

SCENARIOS: dict[str, dict[str, Any]] = {
    "tcp_syn_burst": {
        "script": "tcp_syn_burst.sh",
        "description": "Short SYN burst against the selected target.",
        "category": "transport",
        "osi_layer": "L4",
        "severity_hint": "medium",
        "supports_pause": True,
    },
    "web_scan": {
        "script": "web_scan.sh",
        "description": "Nikto plus suspicious HTTP probes against the selected Ubuntu Apache2 target.",
        "category": "application",
        "osi_layer": "L7",
        "severity_hint": "medium",
        "supports_pause": False,
    },
    "ssh_bruteforce_sim": {
        "script": "ssh_bruteforce_sim.sh",
        "description": "SSH login loop using the configured SSH user.",
        "category": "application",
        "osi_layer": "L7",
        "severity_hint": "high",
        "supports_pause": False,
    },
    "sql_injection_sim": {
        "script": "sql_injection_sim.sh",
        "description": "SQL injection payloads and sqlmap probes against Ubuntu Apache2 web paths.",
        "category": "application",
        "osi_layer": "L7",
        "severity_hint": "high",
        "supports_pause": False,
    },
    "udp_flood": {
        "script": "udp_flood.sh",
        "description": "Short UDP burst to a configurable port.",
        "category": "transport",
        "osi_layer": "L4",
        "severity_hint": "medium",
        "supports_pause": True,
    },
    "icmp_flood": {
        "script": "icmp_flood.sh",
        "description": "ICMP burst for L3 visibility and rate-limit testing.",
        "category": "network",
        "osi_layer": "L3",
        "severity_hint": "low",
        "supports_pause": True,
    },
    "fin_scan": {
        "script": "fin_scan.sh",
        "description": "FIN scan against the selected target.",
        "category": "transport",
        "osi_layer": "L4",
        "severity_hint": "low",
        "supports_pause": False,
    },
    "slow_http": {
        "script": "slow_http.sh",
        "description": "Slow HTTP style connection exhaustion against Ubuntu Apache2 using low volume.",
        "category": "application",
        "osi_layer": "L7",
        "severity_hint": "medium",
        "supports_pause": False,
    },
    "credential_stuffing_http": {
        "script": "credential_stuffing_http.sh",
        "description": "Credential stuffing style login abuse against Ubuntu Apache2 web endpoints.",
        "category": "application",
        "osi_layer": "L7",
        "severity_hint": "high",
        "supports_pause": False,
    },
    "command_injection_probe": {
        "script": "command_injection_probe.sh",
        "description": "Command injection probe payloads over Ubuntu Apache2 query and POST fields.",
        "category": "application",
        "osi_layer": "L7",
        "severity_hint": "high",
        "supports_pause": False,
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
    "notes": "KALI_HOST auto-sync uses OPNsense REST API. REST credentials are required.",
}


def save_state(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text(json.dumps(rows, indent=2), encoding="utf-8")


def save_dict_state(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def append_dashboard_action(action: str, details: dict[str, Any] | None = None, actor: str = "dashboard-ui") -> None:
    payload = {
        "timestamp": utcnow_iso(),
        "actor": actor,
        "action": action,
        "details": details or {},
    }
    line = json.dumps(payload, ensure_ascii=True, default=str)
    with action_log_lock:
        with DASHBOARD_ACTION_LOG_PATH.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")


def safe_log_dashboard_action(action: str, details: dict[str, Any] | None = None, actor: str = "dashboard-ui") -> None:
    try:
        append_dashboard_action(action=action, details=details, actor=actor)
    except OSError:
        return


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


def scenario_supports_pause(scenario_name: str) -> bool:
    details = SCENARIOS.get(scenario_name, {})
    return bool(details.get("supports_pause", False))


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


def signal_container_run(run_id: str, signal_name: str) -> None:
    normalized_signal = signal_name.strip().upper()
    if normalized_signal not in {"TERM", "KILL", "STOP", "CONT"}:
        return
    shell_snippet = "\n".join(
        [
            f"run_id={shlex.quote(run_id)}",
            "self_pid=$$",
            "parent_pid=$PPID",
            "for pid in $(pgrep -f -- \"$run_id\" 2>/dev/null || true); do",
            "  if [ \"$pid\" = \"$self_pid\" ] || [ \"$pid\" = \"$parent_pid\" ]; then",
            "    continue",
            "  fi",
            f"  kill -s {normalized_signal} -- \"-$pid\" 2>/dev/null || true",
            f"  kill -s {normalized_signal} \"$pid\" 2>/dev/null || true",
            "done",
        ]
    )
    try:
        subprocess.run(
            ["sudo", "podman", "exec", KALI_CONTAINER, "/bin/bash", "-lc", shell_snippet],
            check=False,
            capture_output=True,
            text=True,
            timeout=PODMAN_COMMAND_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        return


def stop_registered_process(run_id: str) -> None:
    process_handle = process_registry.get(run_id)
    if process_handle is None:
        return
    if process_handle.poll() is None:
        process_handle.terminate()
        try:
            process_handle.wait(timeout=1)
        except subprocess.TimeoutExpired:
            process_handle.kill()
    process_registry.pop(run_id, None)


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


def has_partial_opnsense_api_config() -> bool:
    values = [OPNSENSE_API_BASE_URL, OPNSENSE_API_KEY, OPNSENSE_API_SECRET]
    return any(values) and not all(values)


def opnsense_api_enabled() -> bool:
    return bool(OPNSENSE_API_BASE_URL and OPNSENSE_API_KEY and OPNSENSE_API_SECRET)


def firewall_integration_mode() -> str:
    if opnsense_api_enabled():
        return "opnsense-rest"
    return "disabled"


def require_opnsense_api_configured() -> None:
    if has_partial_opnsense_api_config():
        raise HTTPException(
            status_code=500,
            detail="OPNSENSE_API_BASE_URL, OPNSENSE_API_KEY, and OPNSENSE_API_SECRET must be set together",
        )
    if not opnsense_api_enabled():
        raise HTTPException(
            status_code=400,
            detail="OPNsense REST integration is not configured",
        )


def validate_alias_name(alias_name: str) -> str:
    normalized = alias_name.strip()
    if not normalized:
        raise HTTPException(status_code=500, detail="Alias name cannot be empty")
    if not ALIAS_NAME_PATTERN.fullmatch(normalized):
        raise HTTPException(status_code=500, detail=f"Alias name contains unsupported characters: {normalized}")
    return normalized


def opnsense_api_request(method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    require_opnsense_api_configured()

    request_path = path if path.startswith("/") else f"/{path}"
    url = f"{OPNSENSE_API_BASE_URL}{request_path}"

    auth_token = base64.b64encode(f"{OPNSENSE_API_KEY}:{OPNSENSE_API_SECRET}".encode("utf-8")).decode("ascii")
    headers = {
        "Accept": "application/json",
        "Authorization": f"Basic {auth_token}",
    }

    request_data: bytes | None = None
    method_upper = method.upper()
    if method_upper == "POST":
        headers["Content-Type"] = "application/json"
        request_data = json.dumps(payload if payload is not None else {}).encode("utf-8")

    request_obj = urllib_request.Request(
        url,
        data=request_data,
        headers=headers,
        method=method_upper,
    )

    ssl_context = None
    if url.lower().startswith("https://"):
        if OPNSENSE_API_VERIFY_TLS:
            ssl_context = ssl.create_default_context()
        else:
            ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE

    try:
        with urllib_request.urlopen(
            request_obj,
            timeout=OPNSENSE_API_TIMEOUT_SECONDS,
            context=ssl_context,
        ) as response:
            response_text = response.read().decode("utf-8", errors="ignore")
    except urllib_error.HTTPError as exc:
        response_text = exc.read().decode("utf-8", errors="ignore")
        raise HTTPException(
            status_code=502,
            detail={
                "message": "OPNsense API returned HTTP error",
                "http_status": exc.code,
                "body": response_text[-500:],
            },
        ) from exc
    except urllib_error.URLError as exc:
        raise HTTPException(
            status_code=502,
            detail={
                "message": "Unable to reach OPNsense API",
                "error": str(getattr(exc, "reason", exc)),
            },
        ) from exc

    parsed: Any
    if response_text.strip():
        try:
            parsed = json.loads(response_text)
        except json.JSONDecodeError:
            parsed = {"raw": response_text}
    else:
        parsed = {}

    if isinstance(parsed, dict):
        result_value = str(parsed.get("result", "")).lower()
        status_value = str(parsed.get("status", "")).lower()
        if result_value in {"failed", "error"} or status_value in {"failed", "error"}:
            raise HTTPException(
                status_code=502,
                detail={
                    "message": "OPNsense API returned failure status",
                    "response": parsed,
                },
            )
        return parsed

    return {"response": parsed}


def opnsense_alias_add(alias_name: str, address: str) -> dict[str, Any]:
    alias = validate_alias_name(alias_name)
    return opnsense_api_request(
        "POST",
        f"/api/firewall/alias_util/add/{urllib_parse.quote(alias, safe='')}",
        payload={"address": address},
    )


def opnsense_alias_delete(alias_name: str, address: str) -> dict[str, Any]:
    alias = validate_alias_name(alias_name)
    return opnsense_api_request(
        "POST",
        f"/api/firewall/alias_util/delete/{urllib_parse.quote(alias, safe='')}",
        payload={"address": address},
    )


def opnsense_alias_flush(alias_name: str) -> dict[str, Any]:
    alias = validate_alias_name(alias_name)
    return opnsense_api_request(
        "POST",
        f"/api/firewall/alias_util/flush/{urllib_parse.quote(alias, safe='')}",
        payload={},
    )


def run_firewall_ban(command_payload: dict[str, Any]) -> dict[str, str]:
    require_opnsense_api_configured()
    response = opnsense_alias_add(OPNSENSE_BAN_ALIAS_TABLE, str(command_payload["BAN_IP"]))
    return {
        "mode": "opnsense-rest",
        "stdout": json.dumps(response)[-400:],
        "stderr": "",
    }


def run_firewall_unban(command_payload: dict[str, Any]) -> dict[str, str]:
    require_opnsense_api_configured()
    response = opnsense_alias_delete(OPNSENSE_BAN_ALIAS_TABLE, str(command_payload["BAN_IP"]))
    return {
        "mode": "opnsense-rest",
        "stdout": json.dumps(response)[-400:],
        "stderr": "",
    }


def sync_kali_alias_table(ip_address: str) -> dict[str, str]:
    require_opnsense_api_configured()
    flush_response = opnsense_alias_flush(OPNSENSE_KALI_ALIAS_TABLE)
    add_response = opnsense_alias_add(OPNSENSE_KALI_ALIAS_TABLE, ip_address)
    merged_output = json.dumps({"flush": flush_response, "add": add_response})
    return {
        "mode": "opnsense-rest",
        "stdout": merged_output[-400:],
        "stderr": "",
    }


def assign_kali_ip(ip_address: str) -> dict[str, str]:
    prefix_length = KALI_ALLOWED_SUBNET.prefixlen
    shell_snippet = " ; ".join(
        [
            f"ip addr flush dev {shlex.quote(KALI_INTERFACE)}",
            f"ip addr add {shlex.quote(f'{ip_address}/{prefix_length}')} dev {shlex.quote(KALI_INTERFACE)}",
            f"ip link set {shlex.quote(KALI_INTERFACE)} up",
            f"ip route replace default via {shlex.quote(KALI_GATEWAY_IP)}",
        ]
    )
    try:
        completed = subprocess.run(
            ["sudo", "podman", "exec", KALI_CONTAINER, "/bin/bash", "-lc", shell_snippet],
            capture_output=True,
            check=False,
            text=True,
            timeout=PODMAN_COMMAND_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout[-400:] if isinstance(exc.stdout, str) else ""
        stderr = exc.stderr[-400:] if isinstance(exc.stderr, str) else ""
        raise HTTPException(
            status_code=504,
            detail={
                "message": f"Kali IP assignment timed out after {PODMAN_COMMAND_TIMEOUT_SECONDS}s",
                "stdout": stdout,
                "stderr": stderr,
            },
        ) from exc
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
    hook_result = run_firewall_unban(hook_payload)
    entry["status"] = "released"
    entry["released_at"] = utcnow_iso()
    entry["release_reason"] = reason
    entry["hook_mode"] = hook_result["mode"]


def cleanup_expired_bans() -> None:
    if not opnsense_api_enabled():
        return
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
    # RFC3339 / RFC5424 style timestamps, commonly present in modern syslog payloads.
    iso_match = re.search(
        r"\b(\d{4}-\d{2}-\d{2}[T\s]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})?)\b",
        line,
    )
    if iso_match:
        candidate = iso_match.group(1).replace(" ", "T")
        if candidate.endswith("Z"):
            candidate = f"{candidate[:-1]}+00:00"
        try:
            parsed = datetime.fromisoformat(candidate)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc).isoformat()
        except ValueError:
            pass

    # Legacy BSD syslog timestamp, e.g. "May  6 13:14:15".
    syslog_match = re.search(r"\b([A-Z][a-z]{2}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2})\b", line)
    if syslog_match:
        try:
            now_utc = datetime.now(timezone.utc)
            parsed = datetime.strptime(f"{now_utc.year} {syslog_match.group(1)}", "%Y %b %d %H:%M:%S")
            return parsed.replace(tzinfo=timezone.utc).isoformat()
        except ValueError:
            pass

    # Last-resort fallback for logs with missing/unknown timestamp format.
    return utcnow_iso()


def parse_event(line: str) -> dict[str, Any]:
    tokens = [token.strip() for token in re.split(r"[,\s]+", line) if token.strip()]
    lower_line = line.lower()
    ip_matches = IPV4_PATTERN.findall(line)
    src_ip = ip_matches[0] if len(ip_matches) > 0 else "unknown"
    dst_ip = ip_matches[1] if len(ip_matches) > 1 else "unknown"

    try:
        src_ip = str(ipaddress.ip_address(src_ip))
    except ValueError:
        src_ip = "unknown"
    try:
        dst_ip = str(ipaddress.ip_address(dst_ip))
    except ValueError:
        dst_ip = "unknown"

    dst_port = 0
    for pattern in [
        r"\bdpt[=: ]+(\d+)",
        r"\bdst(?:ination)?(?:_|\s)?port[=: ]+(\d+)",
        r"\btarget(?:_|\s)?port[=: ]+(\d+)",
    ]:
        match = re.search(pattern, line, flags=re.IGNORECASE)
        if not match:
            continue
        candidate = int(match.group(1))
        if 0 < candidate <= 65535:
            dst_port = candidate
            break

    if dst_port == 0 and src_ip != "unknown" and dst_ip != "unknown":
        try:
            dst_ip_idx = tokens.index(dst_ip)
        except ValueError:
            dst_ip_idx = -1
        if dst_ip_idx >= 0:
            if dst_ip_idx + 2 < len(tokens) and tokens[dst_ip_idx + 2].isdigit():
                candidate = int(tokens[dst_ip_idx + 2])
                if 0 < candidate <= 65535:
                    dst_port = candidate
            if dst_port == 0:
                numeric_after = [
                    int(token)
                    for token in tokens[dst_ip_idx + 1 : dst_ip_idx + 7]
                    if token.isdigit()
                ]
                if len(numeric_after) >= 2 and 0 < numeric_after[1] <= 65535:
                    dst_port = numeric_after[1]

    proto = "UNKNOWN"
    proto_match = re.search(r"\b(tcp|udp|icmp|icmpv6)\b", line, flags=re.IGNORECASE)
    if proto_match:
        proto = proto_match.group(1).upper()
    else:
        proto_num_map = {"6": "TCP", "17": "UDP", "1": "ICMP", "58": "ICMPV6"}
        first_ip_index = next((idx for idx, token in enumerate(tokens) if IPV4_PATTERN.fullmatch(token)), len(tokens))
        for token in tokens[:first_ip_index]:
            mapped = proto_num_map.get(token)
            if mapped:
                proto = mapped
                break

    msg_match = re.search(r'msg[:=]"([^"]+)"', line, flags=re.IGNORECASE)
    signature = msg_match.group(1) if msg_match else line[:120]
    if any(token in lower_line for token in ["drop", "block", "reject", "deny"]):
        action = "block"
    elif "alert" in lower_line:
        action = "alert"
    else:
        action = "pass"

    severity_text = f"{lower_line} {signature.lower()}"
    priority_match = re.search(r"\bpriority\s*[:=]?\s*(\d+)\b", severity_text, flags=re.IGNORECASE)
    severity_match = re.search(r"\bseverity\s*[:=]?\s*(\d+)\b", severity_text, flags=re.IGNORECASE)

    priority_value = int(priority_match.group(1)) if priority_match else None
    severity_value = int(severity_match.group(1)) if severity_match else None

    high_keywords = [
        "critical",
        "sql injection",
        "sqli",
        "command injection",
        "cmd injection",
        "brute force",
        "credential stuffing",
        "rce",
        "exploit",
        "shellcode",
        "path traversal",
        "traversal",
        "xss",
        "malware",
        "trojan",
        "web attack",
        "injection attempt",
        "nikto",
    ]
    medium_keywords = [
        "warning",
        "scan",
        "portscan",
        "syn scan",
        "fin scan",
        "flood",
        "dos",
        "suspicious",
        "recon",
        "probe",
    ]

    if priority_value == 1 or severity_value == 1:
        severity = "high"
    elif priority_value == 2 or severity_value == 2:
        severity = "medium"
    elif any(token in severity_text for token in high_keywords):
        severity = "high"
    elif any(token in severity_text for token in medium_keywords):
        severity = "medium"
    elif action == "block":
        severity = "medium"
    elif action == "alert":
        severity = "medium"
    else:
        severity = "low"
    return {
        "timestamp": extract_timestamp(line),
        "raw": line[:300],
        "src_ip": src_ip,
        "dst_ip": dst_ip,
        "dst_port": dst_port,
        "proto": proto,
        "action": action,
        "signature": signature,
        "severity": severity,
    }


def is_lab_ip(ip_value: str) -> bool:
    try:
        address = ipaddress.ip_address(ip_value)
    except ValueError:
        return False
    return any(address in subnet for subnet in TELEMETRY_LAB_SUBNETS)


def is_lab_event(event: dict[str, Any]) -> bool:
    return is_lab_ip(str(event.get("src_ip", ""))) and is_lab_ip(str(event.get("dst_ip", "")))


def is_excluded_event(event: dict[str, Any]) -> bool:
    src_ip = str(event.get("src_ip", ""))
    dst_ip = str(event.get("dst_ip", ""))
    return src_ip in TELEMETRY_EXCLUDED_IPS or dst_ip in TELEMETRY_EXCLUDED_IPS


def tail_events(limit: int | None, lab_only: bool = False) -> list[dict[str, Any]]:
    if not LOG_PATH.exists():
        return []
    lines = [line for line in LOG_PATH.read_text(encoding="utf-8", errors="ignore").splitlines() if line.strip()]
    if not lines:
        return []
    rows = [parse_event(line) for line in lines]
    rows = [item for item in rows if not is_excluded_event(item)]
    if lab_only:
        rows = [item for item in rows if is_lab_event(item)]
    if isinstance(limit, int) and limit > 0:
        rows = rows[-limit:]
    rows.reverse()
    return rows


def summarize_events(events: list[dict[str, Any]], bucket_seconds: int = 300) -> dict[str, Any]:
    normalized_bucket_seconds = bucket_seconds if bucket_seconds in TELEMETRY_BUCKET_SECONDS_CHOICES else 300
    if not events:
        return {
            "total_alerts": 0,
            "blocked": 0,
            "high_sev": 0,
            "medium_sev": 0,
            "low_sev": 0,
            "anomalies": 0,
            "active_flows": 0,
            "bucket_seconds": normalized_bucket_seconds,
            "over_time": [],
            "top_sources": [],
            "top_ports": [],
        }
    severity_counter = Counter(item["severity"] for item in events)
    source_counter = Counter(item["src_ip"] for item in events if item["src_ip"] != "unknown")
    port_counter = Counter(item["dst_port"] for item in events if item["dst_port"])
    bucket_counter: defaultdict[int, int] = defaultdict(int)
    latest_bucket_epoch: int | None = None
    for item in events:
        dt_value = datetime.fromisoformat(item["timestamp"])
        bucket_epoch = int(dt_value.timestamp())
        bucket_epoch -= bucket_epoch % normalized_bucket_seconds
        bucket_counter[bucket_epoch] += 1
        if latest_bucket_epoch is None or bucket_epoch > latest_bucket_epoch:
            latest_bucket_epoch = bucket_epoch

    over_time: list[dict[str, Any]] = []
    if latest_bucket_epoch is not None:
        window_buckets = 12
        start_epoch = latest_bucket_epoch - ((window_buckets - 1) * normalized_bucket_seconds)
        for index in range(window_buckets):
            bucket_epoch = start_epoch + (index * normalized_bucket_seconds)
            bucket_dt = datetime.fromtimestamp(bucket_epoch, tz=timezone.utc)
            bucket_label = bucket_dt.strftime("%H:%M:%S") if normalized_bucket_seconds < 60 else bucket_dt.strftime("%H:%M")
            over_time.append({
                "label": bucket_label,
                "count": bucket_counter.get(bucket_epoch, 0),
            })

    return {
        "total_alerts": len(events),
        "blocked": sum(1 for item in events if item["action"] == "block"),
        "high_sev": severity_counter.get("high", 0),
        "medium_sev": severity_counter.get("medium", 0),
        "low_sev": severity_counter.get("low", 0),
        "anomalies": sum(1 for item in events if "anomaly" in item["raw"].lower()),
        "active_flows": len({(item["src_ip"], item["dst_ip"], item["dst_port"]) for item in events}),
        "bucket_seconds": normalized_bucket_seconds,
        "over_time": over_time,
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


class HookTestRequest(BaseModel):
    ip: str
    reason: str = Field(default="hook_test")


class DashboardActionRequest(BaseModel):
    action: str
    actor: str = Field(default="dashboard-ui")
    details: dict[str, Any] = Field(default_factory=dict)


def stop_run_entry(entry: dict[str, Any], reason: str) -> dict[str, Any]:
    if not is_active_run(entry):
        return entry
    run_id = entry["run_id"]
    signal_container_run(run_id, "TERM")
    pid = entry.get("pid")
    if isinstance(pid, int):
        terminate_process_group(pid)
    stop_registered_process(run_id)
    signal_container_run(run_id, "KILL")
    entry["status"] = "stopped"
    entry["stopped_at"] = utcnow_iso()
    entry["stop_reason"] = reason
    return entry


def pause_run_entry(entry: dict[str, Any], reason: str) -> dict[str, Any]:
    if not is_active_run(entry):
        raise HTTPException(status_code=409, detail="Run is not active")
    if entry.get("status") == "paused":
        return entry
    run_id = entry["run_id"]
    signal_container_run(run_id, "STOP")
    pid = entry.get("pid")
    if isinstance(pid, int) and SIGSTOP_SIGNAL is not None:
        signal_process_group(pid, SIGSTOP_SIGNAL)
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
    signal_container_run(run_id, "CONT")
    pid = entry.get("pid")
    if isinstance(pid, int) and SIGCONT_SIGNAL is not None:
        signal_process_group(pid, SIGCONT_SIGNAL)
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
    integration_mode = firewall_integration_mode()
    return {
        "scenarios": [
            {
                "id": scenario_id,
                "description": data["description"],
                "category": data["category"],
                "osi_layer": data.get("osi_layer", "L7"),
                "severity_hint": data.get("severity_hint", "medium"),
                "supports_pause": bool(data.get("supports_pause", False)),
            }
            for scenario_id, data in SCENARIOS.items()
        ],
        "ban_durations_minutes": BAN_DURATION_CHOICES,
        "firewall_hook_enabled": integration_mode == "opnsense-rest",
        "firewall_unban_hook_enabled": integration_mode == "opnsense-rest",
        "firewall_integration_mode": integration_mode,
        "opnsense_api_enabled": opnsense_api_enabled(),
        "opnsense_api_base_url": OPNSENSE_API_BASE_URL,
        "opnsense_api_verify_tls": OPNSENSE_API_VERIFY_TLS,
        "opnsense_api_timeout_seconds": OPNSENSE_API_TIMEOUT_SECONDS,
        "podman_command_timeout_seconds": PODMAN_COMMAND_TIMEOUT_SECONDS,
        "opnsense_ban_alias_table": OPNSENSE_BAN_ALIAS_TABLE,
        "opnsense_kali_alias_table": OPNSENSE_KALI_ALIAS_TABLE,
        "default_target_ip": TARGET_DEFAULT,
        "default_target_profile": TARGET_PROFILE,
        "dashboard_action_log_path": str(DASHBOARD_ACTION_LOG_PATH),
        "telemetry_excluded_ips": sorted(TELEMETRY_EXCLUDED_IPS),
        "max_concurrent_runs": MAX_CONCURRENT_RUNS,
        "run_control_actions": ["launch", "pause", "resume", "stop", "stop-all"],
        "kali_network": {
            "subnet": str(KALI_ALLOWED_SUBNET),
            "reserved_ips": sorted(KALI_RESERVED_IPS),
            "current_ip": kali_network_state.get("ip", KALI_CURRENT_IP),
            "gateway": KALI_GATEWAY_IP,
            "interface": KALI_INTERFACE,
            "notes": "KALI_HOST auto-sync uses OPNsense REST API.",
        },
    }


@app.post("/dashboard/action-log")
def dashboard_action_log(req: DashboardActionRequest, x_api_token: str = Header(default="")) -> dict[str, Any]:
    require_auth(x_api_token)
    action_name = req.action.strip()
    if not action_name:
        raise HTTPException(status_code=400, detail="action is required")
    actor_name = req.actor.strip() or "dashboard-ui"
    append_dashboard_action(action=action_name, details=req.details, actor=actor_name)
    return {
        "status": "logged",
        "action": action_name,
        "actor": actor_name,
        "path": str(DASHBOARD_ACTION_LOG_PATH),
    }


@app.post("/launch")
def launch(req: LaunchRequest, x_api_token: str = Header(default="")) -> dict[str, Any]:
    require_auth(x_api_token)
    cleanup_expired_bans()
    refresh_run_states()
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
    safe_log_dashboard_action(
        action="launch",
        details={
            "run_id": run_id,
            "scenario": req.scenario,
            "target_ip": req.target_ip,
            "source_hint": req.source_hint,
        },
    )
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
    safe_log_dashboard_action(action="run_stop", details={"run_id": run_id, "reason": req.reason})
    return entry


@app.post("/runs/{run_id}/pause")
def pause_run(run_id: str, req: RunControlRequest, x_api_token: str = Header(default="")) -> dict[str, Any]:
    require_auth(x_api_token)
    cleanup_expired_bans()
    refresh_run_states()
    entry = find_run(run_id)
    if not scenario_supports_pause(str(entry.get("scenario", ""))):
        raise HTTPException(
            status_code=409,
            detail="Pause is enabled for flood scenarios only",
        )
    pause_run_entry(entry, req.reason)
    with state_lock:
        save_state(RUN_LOG_PATH, run_log)
    safe_log_dashboard_action(action="run_pause", details={"run_id": run_id, "reason": req.reason})
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
    safe_log_dashboard_action(action="run_resume", details={"run_id": run_id, "reason": req.reason})
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
    safe_log_dashboard_action(
        action="run_stop_all",
        details={
            "reason": req.reason,
            "stopped": len(stopped_runs),
            "run_ids": [item["run_id"] for item in stopped_runs],
        },
    )
    return {
        "stopped": len(stopped_runs),
        "reason": req.reason,
        "run_ids": [item["run_id"] for item in stopped_runs],
    }


@app.get("/firewall/status")
def firewall_status(x_api_token: str = Header(default="")) -> dict[str, Any]:
    require_auth(x_api_token)
    cleanup_expired_bans()
    integration_mode = firewall_integration_mode()
    return {
        "ban_hook_enabled": integration_mode == "opnsense-rest",
        "unban_hook_enabled": integration_mode == "opnsense-rest",
        "integration_mode": integration_mode,
        "opnsense_api_enabled": opnsense_api_enabled(),
        "opnsense_api_base_url": OPNSENSE_API_BASE_URL,
        "opnsense_api_timeout_seconds": OPNSENSE_API_TIMEOUT_SECONDS,
        "opnsense_ban_alias_table": OPNSENSE_BAN_ALIAS_TABLE,
        "opnsense_kali_alias_table": OPNSENSE_KALI_ALIAS_TABLE,
        "active_bans": len([item for item in ban_log if item["status"] == "active"]),
        "supported_durations_minutes": BAN_DURATION_CHOICES,
    }


@app.get("/firewall/bans")
def list_bans(x_api_token: str = Header(default="")) -> dict[str, Any]:
    require_auth(x_api_token)
    cleanup_expired_bans()
    return {"bans": ban_log}


@app.post("/firewall/hook-test")
def firewall_hook_test(req: HookTestRequest, x_api_token: str = Header(default="")) -> dict[str, Any]:
    require_auth(x_api_token)
    cleanup_expired_bans()
    require_opnsense_api_configured()
    ip_address = validate_ipv4(req.ip)
    ban_payload = {
        "BAN_IP": ip_address,
        "BAN_ID": str(uuid4()),
        "BAN_REASON": req.reason,
        "BAN_DURATION_MINUTES": "1",
    }
    ban_result = run_firewall_ban(ban_payload)
    unban_result = run_firewall_unban(ban_payload)
    safe_log_dashboard_action(
        action="firewall_hook_test",
        details={"ip": ip_address, "reason": req.reason},
    )
    return {
        "status": "ok",
        "ip": ip_address,
        "ban": ban_result,
        "unban": unban_result,
    }


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
        "notes": "KALI_HOST auto-sync uses OPNsense REST API.",
    }


@app.post("/kali/network")
def set_kali_network(req: KaliIpAssignRequest, x_api_token: str = Header(default="")) -> dict[str, Any]:
    require_auth(x_api_token)
    cleanup_expired_bans()
    require_opnsense_api_configured()
    ip_address = validate_kali_ip(req.ip)
    assign_result = assign_kali_ip(ip_address)
    sync_result = sync_kali_alias_table(ip_address)
    network_mode = f"{assign_result['mode']}+{sync_result['mode']}"
    kali_network_state.update(
        {
            "ip": ip_address,
            "interface": KALI_INTERFACE,
            "gateway": KALI_GATEWAY_IP,
            "subnet": str(KALI_ALLOWED_SUBNET),
            "reserved_ips": sorted(KALI_RESERVED_IPS),
            "updated_at": utcnow_iso(),
            "reason": req.reason,
            "mode": network_mode,
            "notes": "KALI_HOST auto-sync uses OPNsense REST API.",
        }
    )
    with state_lock:
        save_dict_state(KALI_NETWORK_PATH, kali_network_state)
    safe_log_dashboard_action(
        action="kali_ip_assign",
        details={"ip": ip_address, "reason": req.reason, "mode": network_mode},
    )
    return kali_network_state


@app.post("/firewall/ban")
def create_ban(req: BanRequest, x_api_token: str = Header(default="")) -> dict[str, Any]:
    require_auth(x_api_token)
    cleanup_expired_bans()
    ip_address = validate_ipv4(req.ip)
    if req.duration_minutes not in BAN_DURATION_CHOICES:
        raise HTTPException(status_code=400, detail=f"duration_minutes must be one of {BAN_DURATION_CHOICES}")
    existing = find_ban(ip_address)
    if existing:
        raise HTTPException(status_code=409, detail="IP already has an active ban")
    entry = {
        "ban_id": str(uuid4()),
        "ip": ip_address,
        "reason": req.reason,
        "created_at": utcnow_iso(),
        "expires_at": (utcnow() + timedelta(minutes=req.duration_minutes)).isoformat(),
        "duration_minutes": req.duration_minutes,
        "status": "active",
    }
    hook_result = run_firewall_ban(
        {
            "BAN_IP": entry["ip"],
            "BAN_ID": entry["ban_id"],
            "BAN_REASON": entry["reason"],
            "BAN_DURATION_MINUTES": entry["duration_minutes"],
        }
    )
    entry["hook_mode"] = hook_result["mode"]
    with state_lock:
        ban_log.insert(0, entry)
        save_state(BAN_LOG_PATH, ban_log)
    safe_log_dashboard_action(
        action="ban_create",
        details={
            "ban_id": entry["ban_id"],
            "ip": entry["ip"],
            "duration_minutes": req.duration_minutes,
            "reason": req.reason,
        },
    )
    return entry


@app.post("/firewall/unban")
def remove_ban(req: UnbanRequest, x_api_token: str = Header(default="")) -> dict[str, Any]:
    require_auth(x_api_token)
    cleanup_expired_bans()
    ip_address = validate_ipv4(req.ip)
    entry = find_ban(ip_address)
    if not entry:
        raise HTTPException(status_code=404, detail="Active ban not found for IP")
    release_ban(entry, req.reason)
    with state_lock:
        save_state(BAN_LOG_PATH, ban_log)
    safe_log_dashboard_action(
        action="ban_release",
        details={"ban_id": entry["ban_id"], "ip": entry["ip"], "reason": req.reason},
    )
    return entry


@app.get("/telemetry/events")
def get_events(limit: int = 20, lab_only: bool = True, x_api_token: str = Header(default="")) -> dict[str, Any]:
    require_auth(x_api_token)
    cleanup_expired_bans()
    event_limit = limit if limit > 0 else None
    return {"events": tail_events(event_limit, lab_only=lab_only)}


@app.get("/telemetry/summary")
def get_summary(
    limit: int = 0,
    bucket_seconds: int = 300,
    lab_only: bool = True,
    x_api_token: str = Header(default=""),
) -> dict[str, Any]:
    require_auth(x_api_token)
    cleanup_expired_bans()
    if bucket_seconds not in TELEMETRY_BUCKET_SECONDS_CHOICES:
        raise HTTPException(
            status_code=400,
            detail=f"bucket_seconds must be one of {sorted(TELEMETRY_BUCKET_SECONDS_CHOICES)}",
        )
    event_limit = limit if limit > 0 else None
    return summarize_events(tail_events(event_limit, lab_only=lab_only), bucket_seconds=bucket_seconds)


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