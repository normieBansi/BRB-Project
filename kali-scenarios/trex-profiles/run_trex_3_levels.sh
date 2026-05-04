#!/usr/bin/env bash
set -euo pipefail

TREX_DIR="${TREX_DIR:-/opt/trex}"
TREX_BIN_GLOB="${TREX_BIN_GLOB:-$TREX_DIR/v3.*/t-rex-64}"
PROFILE_DIR="${PROFILE_DIR:-/opt/trex/profiles}"
SRC_IP="${SRC_IP:-192.168.60.10}"
DST_IP="${DST_IP:-192.168.50.10}"
USE_SOFTWARE_MODE="${USE_SOFTWARE_MODE:-true}"

find_trex_bin() {
  local first
  first=$(ls $TREX_BIN_GLOB 2>/dev/null | head -n 1 || true)
  if [[ -z "$first" ]]; then
    echo "Unable to locate TRex binary using $TREX_BIN_GLOB" >&2
    exit 1
  fi
  echo "$first"
}

run_level() {
  local label="$1"
  local profile="$2"
  local duration="$3"
  local mode_flag=""
  local tunables="src=${SRC_IP},dst=${DST_IP}"

  if [[ "$USE_SOFTWARE_MODE" == "true" ]]; then
    mode_flag="--software"
  fi

  echo "[INFO] Running $label for ${duration}s using $profile"
  sudo "$TREX_BIN" -f "$PROFILE_DIR/$profile" -d "$duration" -m 1 --no-watchdog $mode_flag -t "$tunables"
}

TREX_BIN=$(find_trex_bin)

echo "[INFO] Using TRex binary: $TREX_BIN"
echo "[INFO] Profile directory: $PROFILE_DIR"
echo "[INFO] Source IP: $SRC_IP Destination IP: $DST_IP"

run_level "Level 1 baseline" "level1_baseline.py" 30
run_level "Level 2 pressure" "level2_pressure.py" 30
run_level "Level 3 surge" "level3_surge.py" 15

echo "[INFO] Completed all 3 TRex levels"
