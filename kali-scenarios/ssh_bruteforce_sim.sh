#!/bin/bash
set -eu

RUN_ID="${1:-no-run-id}"
TARGET_IP="${TARGET_IP:-192.168.50.10}"
SSH_USER="${SSH_USER:-root}"

echo "[run_id=$RUN_ID] SSH brute force simulation starting target=$TARGET_IP user=$SSH_USER ts=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
for _ in $(seq 1 25); do
  ssh -o ConnectTimeout=2 -o BatchMode=yes -o StrictHostKeyChecking=no "$SSH_USER@$TARGET_IP" 2>/dev/null || true
  sleep 0.2
done
echo "[run_id=$RUN_ID] SSH brute force simulation done target=$TARGET_IP user=$SSH_USER ts=$(date -u +%Y-%m-%dT%H:%M:%SZ)"