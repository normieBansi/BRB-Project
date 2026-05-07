from __future__ import annotations

import argparse
import csv
import ipaddress
import re
from datetime import datetime, timezone
from pathlib import Path


IP_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
SIG_RE = re.compile(r'suricata\[\d+\]\s+\[\d+:\d+:\d+\]\s+(.*?)\s+\[Classification:', re.IGNORECASE)
ISO_TS_RE = re.compile(r"\b(\d{4}-\d{2}-\d{2}[T\s]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})?)\b")
BSD_TS_RE = re.compile(r"\b([A-Z][a-z]{2}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2})\b")
SURICATA_ARROW_IPV4_RE = re.compile(r"((?:\d{1,3}\.){3}\d{1,3})(?::(\d+))?\s*->\s*((?:\d{1,3}\.){3}\d{1,3})(?::(\d+))?")


def extract_timestamp(line: str) -> str:
    iso_match = ISO_TS_RE.search(line)
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

    bsd_match = BSD_TS_RE.search(line)
    if bsd_match:
        try:
            now_utc = datetime.now(timezone.utc)
            parsed = datetime.strptime(f"{now_utc.year} {bsd_match.group(1)}", "%Y %b %d %H:%M:%S")
            return parsed.replace(tzinfo=timezone.utc).isoformat()
        except ValueError:
            pass

    return datetime.now(timezone.utc).isoformat()


def normalize_ipv4(value: str) -> str:
    try:
        return str(ipaddress.ip_address(value.strip()))
    except ValueError:
        return "unknown"


def parse_filterlog_line(line: str) -> dict[str, str | int | None]:
    payload_match = re.search(r"filterlog\[\d+\]\s+(.*)$", line)
    payload = payload_match.group(1) if payload_match else line
    parts = [token.strip() for token in payload.split(",")]

    proto_num_map = {
        "1": "ICMP",
        "2": "IGMP",
        "6": "TCP",
        "17": "UDP",
        "58": "ICMPV6",
    }

    rule_label = parts[3] if len(parts) > 3 else ""
    action = (parts[6] if len(parts) > 6 else "pass").lower()
    if action not in {"pass", "block", "alert"}:
        action = "block" if action in {"reject", "drop", "deny"} else "pass"

    direction = (parts[7] if len(parts) > 7 else "unknown").lower()
    proto_text = (parts[16] if len(parts) > 16 else "").upper()
    proto_num = parts[15] if len(parts) > 15 else ""
    proto = proto_text or proto_num_map.get(proto_num, "UNKNOWN")

    src_ip = normalize_ipv4(parts[18]) if len(parts) > 18 else "unknown"
    dst_ip = normalize_ipv4(parts[19]) if len(parts) > 19 else "unknown"

    dst_port = 0
    if len(parts) > 21 and parts[21].isdigit():
        dst_port = int(parts[21])
    elif len(parts) > 20 and parts[20].isdigit() and proto in {"TCP", "UDP"}:
        # Some filterlog lines omit src_port and keep dst_port at first port position.
        dst_port = int(parts[20])

    signature = rule_label or f"filterlog:{action}:{proto}"
    return {
        "timestamp": extract_timestamp(line),
        "event_source": "filterlog",
        "src_ip": src_ip,
        "dst_ip": dst_ip,
        "dst_port": dst_port,
        "proto": proto,
        "action": action,
        "signature": signature,
        "priority": 0,
        "rule_label": rule_label,
        "direction": direction,
        "label": "unknown",
    }


def parse_suricata_line(line: str) -> dict[str, str | int | None]:
    lower_line = line.lower()
    priority_match = re.search(r"\[Priority:\s*(\d+)\]", line, flags=re.IGNORECASE)
    priority = int(priority_match.group(1)) if priority_match else 0

    proto_match = re.search(r"\{\s*([A-Za-z0-9-]+)\s*\}", line)
    proto = proto_match.group(1).upper() if proto_match else "UNKNOWN"

    src_ip = "unknown"
    dst_ip = "unknown"
    dst_port = 0
    arrow_match = SURICATA_ARROW_IPV4_RE.search(line)
    if arrow_match:
        src_ip = normalize_ipv4(arrow_match.group(1))
        dst_ip = normalize_ipv4(arrow_match.group(3))
        if arrow_match.group(4) and arrow_match.group(4).isdigit():
            dst_port = int(arrow_match.group(4))

    sig_match = SIG_RE.search(line)
    signature = sig_match.group(1).strip() if sig_match else line[:120]

    sid_match = re.search(r"\[(\d+:\d+:\d+)\]", line)
    rule_label = sid_match.group(1) if sid_match else ""
    action = "block" if any(token in lower_line for token in ["drop", "block", "reject", "deny"]) else "alert"

    return {
        "timestamp": extract_timestamp(line),
        "event_source": "suricata",
        "src_ip": src_ip,
        "dst_ip": dst_ip,
        "dst_port": dst_port,
        "proto": proto,
        "action": action,
        "signature": signature,
        "priority": priority,
        "rule_label": rule_label,
        "direction": "unknown",
        "label": "unknown",
    }


def parse_line(line: str, include_suricata: bool) -> dict[str, str | int | None] | None:
    lower_line = line.lower()
    if "filterlog[" in lower_line:
        return parse_filterlog_line(line)
    if "suricata[" in lower_line and include_suricata:
        return parse_suricata_line(line)
    return None


def event_is_lab_related(event: dict[str, str | int | None]) -> bool:
    src_ip = str(event.get("src_ip", "unknown"))
    dst_ip = str(event.get("dst_ip", "unknown"))
    return src_ip.startswith("192.168.") or dst_ip.startswith("192.168.")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--log", default=str(Path("~/logs/opnsense.log").expanduser()))
    parser.add_argument("--out", default=str(Path("~/lab/ml/features.csv").expanduser()))
    parser.add_argument("--include-suricata", action="store_true", help="Include Suricata alert lines in ML features")
    parser.add_argument("--all-events", action="store_true", help="Do not filter to lab-related traffic")
    args = parser.parse_args()

    input_path = Path(args.log).expanduser()
    output_path = Path(args.out).expanduser()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, str | int | None]] = []
    skipped = 0
    if input_path.exists():
        for raw_line in input_path.read_text(encoding="utf-8", errors="ignore").splitlines():
            if raw_line.strip():
                parsed = parse_line(raw_line, include_suricata=args.include_suricata)
                if parsed is None:
                    skipped += 1
                    continue
                if not args.all_events and not event_is_lab_related(parsed):
                    skipped += 1
                    continue
                rows.append(parsed)

    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "timestamp",
                "event_source",
                "src_ip",
                "dst_ip",
                "dst_port",
                "proto",
                "action",
                "signature",
                "priority",
                "rule_label",
                "direction",
                "label",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {len(rows)} rows to {output_path} (skipped {skipped})")


if __name__ == "__main__":
    main()