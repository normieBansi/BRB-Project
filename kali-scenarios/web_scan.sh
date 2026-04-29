#!/bin/bash
set -eu

RUN_ID="${1:-no-run-id}"
TARGET_IP="${TARGET_IP:-192.168.50.10}"

echo "[run_id=$RUN_ID] Web scan starting target=$TARGET_IP ts=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
nikto -h "http://$TARGET_IP" -maxtime 60 || true
curl -s "http://$TARGET_IP/?id=1'" -o /dev/null || true
curl -s "http://$TARGET_IP/../../../../etc/passwd" -o /dev/null || true
curl -s -A "sqlmap/1.0" "http://$TARGET_IP/" -o /dev/null || true
curl -s "http://$TARGET_IP/?q=UNION+SELECT+null,null--" -o /dev/null || true
echo "[run_id=$RUN_ID] Web scan done target=$TARGET_IP ts=$(date -u +%Y-%m-%dT%H:%M:%SZ)"