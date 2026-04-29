from __future__ import annotations

import argparse
import csv
import re
from datetime import datetime, timezone
from pathlib import Path


IP_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
PROTO_RE = re.compile(r"\b(TCP|UDP|ICMP)\b")
PORT_RE = re.compile(r"(?:dpt|dst port|port)[=: ]+(\d+)", re.IGNORECASE)
SIG_RE = re.compile(r'msg[:=]"([^"]+)"', re.IGNORECASE)


def parse_line(line: str) -> dict[str, str | int]:
    lower_line = line.lower()
    ip_matches = IP_RE.findall(line)
    src_ip = ip_matches[0] if len(ip_matches) > 0 else "unknown"
    dst_ip = ip_matches[1] if len(ip_matches) > 1 else "unknown"
    proto_match = PROTO_RE.search(line)
    port_match = PORT_RE.search(line)
    sig_match = SIG_RE.search(line)
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
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "src_ip": src_ip,
        "dst_ip": dst_ip,
        "dst_port": int(port_match.group(1)) if port_match else 0,
        "proto": proto_match.group(1) if proto_match else "UNKNOWN",
        "action": action,
        "signature": sig_match.group(1) if sig_match else line[:100],
        "severity": severity,
        "label": "unknown",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--log", default=str(Path("~/logs/opnsense.log").expanduser()))
    parser.add_argument("--out", default=str(Path("~/lab/ml/features.csv").expanduser()))
    args = parser.parse_args()

    input_path = Path(args.log).expanduser()
    output_path = Path(args.out).expanduser()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, str | int]] = []
    if input_path.exists():
        for raw_line in input_path.read_text(encoding="utf-8", errors="ignore").splitlines():
            if raw_line.strip():
                rows.append(parse_line(raw_line))

    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["timestamp", "src_ip", "dst_ip", "dst_port", "proto", "action", "signature", "severity", "label"],
        )
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {len(rows)} rows to {output_path}")


if __name__ == "__main__":
    main()