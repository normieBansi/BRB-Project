#!/usr/bin/env bash
set -euo pipefail

API_BASE="${API_BASE:-http://127.0.0.1:5000}"
API_TOKEN="${API_TOKEN:-${TOKEN:-}}"
TARGET_IP="${TARGET_IP:-}"
SCENARIO="${SCENARIO:-}"
HOOK_TEST_IP="${HOOK_TEST_IP:-192.168.60.222}"
REASSIGN_IP="${REASSIGN_IP:-}"
DO_REASSIGN="${DO_REASSIGN:-false}"

PASS_COUNT=0
WARN_COUNT=0
FAIL_COUNT=0

HTTP_CODE=""
HTTP_BODY=""

usage() {
  cat <<'EOF'
Usage:
  API_TOKEN=<token> ./debian_smoke_test.sh [options]

Options:
  --api-base URL         API base URL (default: http://127.0.0.1:5000)
  --api-token TOKEN      API token (or set API_TOKEN/TOKEN env var)
  --target-ip IP         Force launch target IP (defaults to /config default_target_ip)
  --scenario NAME        Force launch scenario (default preference: slow_http, web_scan, tcp_syn_burst)
  --hook-test-ip IP      Firewall integration test IP (default: 192.168.60.222)
  --reassign-ip IP       Candidate Kali IP used for optional reassignment test
  --do-reassign          Enable Kali network reassignment test (default: off)
  -h, --help             Show help

Examples:
  API_TOKEN="$TOKEN" ./debian_smoke_test.sh
  API_TOKEN="$TOKEN" ./debian_smoke_test.sh --api-base http://192.168.50.20:5000
  API_TOKEN="$TOKEN" ./debian_smoke_test.sh --do-reassign --reassign-ip 192.168.60.20
EOF
}

log_info() { printf '[INFO] %s\n' "$1"; }
log_pass() { PASS_COUNT=$((PASS_COUNT + 1)); printf '[PASS] %s\n' "$1"; }
log_warn() { WARN_COUNT=$((WARN_COUNT + 1)); printf '[WARN] %s\n' "$1"; }
log_fail() { FAIL_COUNT=$((FAIL_COUNT + 1)); printf '[FAIL] %s\n' "$1"; }

need_cmd() {
  local cmd="$1"
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "Missing required command: $cmd" >&2
    exit 2
  fi
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --api-base)
      API_BASE="$2"
      shift 2
      ;;
    --api-token)
      API_TOKEN="$2"
      shift 2
      ;;
    --target-ip)
      TARGET_IP="$2"
      shift 2
      ;;
    --scenario)
      SCENARIO="$2"
      shift 2
      ;;
    --hook-test-ip)
      HOOK_TEST_IP="$2"
      shift 2
      ;;
    --reassign-ip)
      REASSIGN_IP="$2"
      shift 2
      ;;
    --do-reassign)
      DO_REASSIGN="true"
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage
      exit 2
      ;;
  esac
done

need_cmd curl
need_cmd python3

if [[ -z "$API_TOKEN" ]]; then
  echo "API token is required. Set API_TOKEN or use --api-token." >&2
  exit 2
fi

api_call() {
  local method="$1"
  local path="$2"
  local data="${3-}"
  local tmp_file
  tmp_file=$(mktemp)

  if [[ -n "$data" ]]; then
    HTTP_CODE=$(curl -sS -m 20 -o "$tmp_file" -w "%{http_code}" \
      -X "$method" "$API_BASE$path" \
      -H "X-API-Token: $API_TOKEN" \
      -H "Content-Type: application/json" \
      -d "$data")
  else
    HTTP_CODE=$(curl -sS -m 20 -o "$tmp_file" -w "%{http_code}" \
      -X "$method" "$API_BASE$path" \
      -H "X-API-Token: $API_TOKEN")
  fi

  HTTP_BODY=$(cat "$tmp_file")
  rm -f "$tmp_file"
}

api_call_public() {
  local method="$1"
  local path="$2"
  local tmp_file
  tmp_file=$(mktemp)
  HTTP_CODE=$(curl -sS -m 20 -o "$tmp_file" -w "%{http_code}" \
    -X "$method" "$API_BASE$path")
  HTTP_BODY=$(cat "$tmp_file")
  rm -f "$tmp_file"
}

json_get() {
  local key_path="$1"
  printf '%s' "$HTTP_BODY" | python3 - "$key_path" <<'PY'
import json
import sys

path = sys.argv[1].split('.')
raw = sys.stdin.read().strip()
if not raw:
    print('')
    raise SystemExit(0)

try:
    data = json.loads(raw)
except json.JSONDecodeError:
    print('')
    raise SystemExit(0)

cur = data
for part in path:
    if isinstance(cur, list) and part.isdigit():
        idx = int(part)
        if idx < 0 or idx >= len(cur):
            print('')
            raise SystemExit(0)
        cur = cur[idx]
    elif isinstance(cur, dict):
        cur = cur.get(part)
    else:
        print('')
        raise SystemExit(0)

if cur is None:
    print('')
elif isinstance(cur, (dict, list)):
    print(json.dumps(cur))
else:
    print(cur)
PY
}

pick_launch_scenario() {
  printf '%s' "$HTTP_BODY" | python3 - <<'PY'
import json
import sys
raw = sys.stdin.read().strip()
if not raw:
    print('')
    raise SystemExit(0)
cfg = json.loads(raw)
ids = [x.get('id') for x in cfg.get('scenarios', []) if x.get('id')]
for preferred in ('slow_http', 'web_scan', 'tcp_syn_burst'):
    if preferred in ids:
        print(preferred)
        raise SystemExit(0)
print(ids[0] if ids else '')
PY
}

require_http_200() {
  local label="$1"
  if [[ "$HTTP_CODE" == "200" ]]; then
    log_pass "$label"
  else
    log_fail "$label (HTTP $HTTP_CODE, body: $HTTP_BODY)"
  fi
}

log_info "Starting control API smoke test against $API_BASE"

api_call_public GET "/health"
if [[ "$HTTP_CODE" == "200" ]]; then
  log_pass "GET /health"
else
  log_fail "GET /health (HTTP $HTTP_CODE, body: $HTTP_BODY)"
fi

api_call GET "/config"
require_http_200 "GET /config"

if [[ "$HTTP_CODE" != "200" ]]; then
  log_fail "Cannot continue without /config"
  echo
  printf 'Summary: pass=%d warn=%d fail=%d\n' "$PASS_COUNT" "$WARN_COUNT" "$FAIL_COUNT"
  exit 1
fi

DEFAULT_TARGET=$(json_get "default_target_ip")
MAX_CONCURRENCY=$(json_get "max_concurrent_runs")
HOOK_BAN_ENABLED=$(json_get "firewall_hook_enabled")
HOOK_UNBAN_ENABLED=$(json_get "firewall_unban_hook_enabled")

if [[ -z "$TARGET_IP" ]]; then
  TARGET_IP="$DEFAULT_TARGET"
fi

if [[ -z "$SCENARIO" ]]; then
  SCENARIO=$(pick_launch_scenario)
fi

if [[ -n "$SCENARIO" ]]; then
  log_info "Launch candidate scenario=$SCENARIO target=$TARGET_IP max_concurrency=${MAX_CONCURRENCY:-unknown}"
else
  log_fail "No scenario available from /config"
fi

api_call GET "/runs"
require_http_200 "GET /runs"

RUN_ID=""
if [[ -n "$SCENARIO" ]]; then
  api_call POST "/launch" "{\"scenario\":\"$SCENARIO\",\"target_ip\":\"$TARGET_IP\"}"
  if [[ "$HTTP_CODE" == "200" ]]; then
    RUN_ID=$(json_get "run_id")
    RUN_STATUS=$(json_get "status")
    if [[ -n "$RUN_ID" ]]; then
      log_pass "POST /launch returned run_id=$RUN_ID status=${RUN_STATUS:-unknown}"
    else
      log_fail "POST /launch returned HTTP 200 but no run_id (body: $HTTP_BODY)"
    fi
  else
    log_fail "POST /launch (HTTP $HTTP_CODE, body: $HTTP_BODY)"
  fi
fi

if [[ -n "$RUN_ID" ]]; then
  sleep 1

  api_call POST "/runs/$RUN_ID/pause" "{\"reason\":\"smoke_pause\"}"
  if [[ "$HTTP_CODE" == "200" ]]; then
    PAUSE_STATUS=$(json_get "status")
    log_pass "POST /runs/$RUN_ID/pause status=${PAUSE_STATUS:-unknown}"
  elif [[ "$HTTP_CODE" == "409" ]]; then
    log_warn "Pause skipped because run already inactive (HTTP 409)"
  else
    log_fail "POST /runs/$RUN_ID/pause (HTTP $HTTP_CODE, body: $HTTP_BODY)"
  fi

  api_call POST "/runs/$RUN_ID/resume" "{\"reason\":\"smoke_resume\"}"
  if [[ "$HTTP_CODE" == "200" ]]; then
    RESUME_STATUS=$(json_get "status")
    log_pass "POST /runs/$RUN_ID/resume status=${RESUME_STATUS:-unknown}"
  elif [[ "$HTTP_CODE" == "409" ]]; then
    log_warn "Resume skipped because run already inactive (HTTP 409)"
  else
    log_fail "POST /runs/$RUN_ID/resume (HTTP $HTTP_CODE, body: $HTTP_BODY)"
  fi

  api_call POST "/runs/$RUN_ID/stop" "{\"reason\":\"smoke_stop\"}"
  if [[ "$HTTP_CODE" == "200" ]]; then
    STOP_STATUS=$(json_get "status")
    log_pass "POST /runs/$RUN_ID/stop status=${STOP_STATUS:-unknown}"
  else
    log_fail "POST /runs/$RUN_ID/stop (HTTP $HTTP_CODE, body: $HTTP_BODY)"
  fi
fi

api_call POST "/runs/stop-all" "{\"reason\":\"smoke_cleanup\"}"
if [[ "$HTTP_CODE" == "200" ]]; then
  STOPPED_COUNT=$(json_get "stopped")
  log_pass "POST /runs/stop-all stopped=${STOPPED_COUNT:-unknown}"
else
  log_fail "POST /runs/stop-all (HTTP $HTTP_CODE, body: $HTTP_BODY)"
fi

api_call GET "/firewall/status"
require_http_200 "GET /firewall/status"

if [[ "$HTTP_CODE" == "200" ]]; then
  if [[ "$HOOK_BAN_ENABLED" == "True" && "$HOOK_UNBAN_ENABLED" == "True" ]]; then
    api_call POST "/firewall/hook-test" "{\"ip\":\"$HOOK_TEST_IP\",\"reason\":\"smoke_test\"}"
    if [[ "$HTTP_CODE" == "200" ]]; then
      HOOK_STATUS=$(json_get "status")
      log_pass "POST /firewall/hook-test status=${HOOK_STATUS:-unknown}"
    else
      log_fail "POST /firewall/hook-test (HTTP $HTTP_CODE, body: $HTTP_BODY)"
    fi
  else
    log_warn "Skipping /firewall/hook-test because firewall integration is not enabled (ban=$HOOK_BAN_ENABLED unban=$HOOK_UNBAN_ENABLED)"
  fi
fi

ORIGINAL_KALI_IP=""
api_call GET "/kali/network"
require_http_200 "GET /kali/network"
if [[ "$HTTP_CODE" == "200" ]]; then
  ORIGINAL_KALI_IP=$(json_get "ip")
  log_info "Current Kali IP from API: ${ORIGINAL_KALI_IP:-unknown}"
fi

if [[ "$DO_REASSIGN" == "true" ]]; then
  if [[ -z "$REASSIGN_IP" ]]; then
    log_warn "--do-reassign was set but --reassign-ip is empty, skipping reassignment test"
  else
    api_call POST "/kali/network" "{\"ip\":\"$REASSIGN_IP\",\"reason\":\"smoke_reassign\"}"
    if [[ "$HTTP_CODE" == "200" ]]; then
      NEW_IP=$(json_get "ip")
      log_pass "POST /kali/network reassigned to ${NEW_IP:-unknown}"
    else
      log_fail "POST /kali/network reassign (HTTP $HTTP_CODE, body: $HTTP_BODY)"
    fi

    if [[ -n "$ORIGINAL_KALI_IP" ]]; then
      api_call POST "/kali/network" "{\"ip\":\"$ORIGINAL_KALI_IP\",\"reason\":\"smoke_restore\"}"
      if [[ "$HTTP_CODE" == "200" ]]; then
        RESTORE_IP=$(json_get "ip")
        log_pass "POST /kali/network restore to ${RESTORE_IP:-unknown}"
      else
        log_fail "POST /kali/network restore (HTTP $HTTP_CODE, body: $HTTP_BODY)"
      fi
    fi
  fi
else
  log_warn "Kali reassignment test skipped (use --do-reassign --reassign-ip <ip> to enable)"
fi

api_call GET "/telemetry/summary"
if [[ "$HTTP_CODE" == "200" ]]; then
  log_pass "GET /telemetry/summary"
else
  log_warn "GET /telemetry/summary returned HTTP $HTTP_CODE"
fi

api_call GET "/ml/summary"
if [[ "$HTTP_CODE" == "200" ]]; then
  log_pass "GET /ml/summary"
else
  log_warn "GET /ml/summary returned HTTP $HTTP_CODE"
fi

echo
printf 'Summary: pass=%d warn=%d fail=%d\n' "$PASS_COUNT" "$WARN_COUNT" "$FAIL_COUNT"

if [[ "$FAIL_COUNT" -gt 0 ]]; then
  exit 1
fi

exit 0
