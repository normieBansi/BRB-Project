#!/bin/bash
set -eu

RUN_ID="${1:-no-run-id}"
TARGET_IP="${TARGET_IP:-192.168.50.10}"

echo "[run_id=$RUN_ID] TCP SYN burst starting target=$TARGET_IP ts=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
hping3 -S -p 80 -c 500 "$TARGET_IP" 2>/dev/null || nmap -sS -Pn -p 1-500 "$TARGET_IP"
echo "[run_id=$RUN_ID] TCP SYN burst done target=$TARGET_IP ts=$(date -u +%Y-%m-%dT%H:%M:%SZ)"