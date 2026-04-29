#!/bin/bash
set -eu

RUN_ID="${1:-no-run-id}"
TARGET_IP="${TARGET_IP:-192.168.50.10}"
TARGET_PORT="${TARGET_PORT:-53}"

echo "[run_id=$RUN_ID] UDP flood starting target=$TARGET_IP port=$TARGET_PORT ts=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
hping3 --udp -p "$TARGET_PORT" -c 300 "$TARGET_IP" 2>/dev/null || true
echo "[run_id=$RUN_ID] UDP flood done target=$TARGET_IP port=$TARGET_PORT ts=$(date -u +%Y-%m-%dT%H:%M:%SZ)"