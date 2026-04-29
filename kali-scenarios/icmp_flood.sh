#!/bin/bash
set -eu

RUN_ID="${1:-no-run-id}"
TARGET_IP="${TARGET_IP:-192.168.50.10}"

echo "[run_id=$RUN_ID] ICMP burst starting target=$TARGET_IP ts=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
hping3 --icmp -c 200 "$TARGET_IP" 2>/dev/null || true
echo "[run_id=$RUN_ID] ICMP burst done target=$TARGET_IP ts=$(date -u +%Y-%m-%dT%H:%M:%SZ)"