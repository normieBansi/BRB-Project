#!/bin/bash
set -eu

RUN_ID="${1:-no-run-id}"
TARGET_IP="${TARGET_IP:-192.168.50.10}"

echo "[run_id=$RUN_ID] FIN scan starting target=$TARGET_IP ts=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
nmap -sF -Pn -p 1-1000 "$TARGET_IP" || true
echo "[run_id=$RUN_ID] FIN scan done target=$TARGET_IP ts=$(date -u +%Y-%m-%dT%H:%M:%SZ)"