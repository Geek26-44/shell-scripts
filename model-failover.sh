#!/usr/bin/env bash
# model-failover.sh — Monitors GLM-5, switches to Ollama on rate-limit/failure
# Runs via cron every 5 min
# State: scripts/.failover-state | Log: scripts/.failover-log

set -euo pipefail

CONFIG="$HOME/.openclaw/openclaw.json"
SCRIPT_DIR="$HOME/.openclaw/workspace/scripts"
STATE_FILE="$SCRIPT_DIR/.failover-state"
LOG_FILE="$SCRIPT_DIR/.failover-log"

# --- Config ---
CLOUD_MODEL="zai/glm-5"
LOCAL_MODEL="ollama/qwen2.5:14b"
CLOUD_TIMEOUT=300
LOCAL_TIMEOUT=300

FAIL_THRESHOLD=3      # failures before switch to local
RECOVER_THRESHOLD=2   # successes before switch back to cloud

# --- Helpers ---
log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" >> "$LOG_FILE"; }

get_state() {
    MODE="cloud"; FAIL_COUNT=0; OK_COUNT=0
    [[ -f "$STATE_FILE" ]] && source "$STATE_FILE"
}

save_state() {
    cat > "$STATE_FILE" <<EOF
MODE="$MODE"
FAIL_COUNT=$FAIL_COUNT
OK_COUNT=$OK_COUNT"
EOF
}

# --- Check GLM health ---
# Strategy: send a minimal chat via the dashboard API (same gateway the bot uses)
check_glm() {
    local gw_url="http://127.0.0.1:18789"
    local token
    token=$(python3 -c "
import json
with open('$CONFIG') as f:
    c = json.load(f)
print(c.get('gateway',{}).get('auth',{}).get('token',''))
" 2>/dev/null)

    # Try a tiny completion through the gateway
    local resp
    resp=$(curl -sf --max-time 30 \
        -H "Authorization: Bearer $token" \
        -H "Content-Type: application/json" \
        "$gw_url/api/v1/chat/completions" \
        -d '{"model":"zai/glm-5","messages":[{"role":"user","content":"ping"}],"max_tokens":1}' \
        2>&1) && return 0

    # Check for rate limit / quota
    if echo "$resp" | grep -qi "rate.limit\|429\|quota\|insufficient\|billing"; then
        log "GLM rate-limited"
        return 2
    fi
    return 1
}

# --- Alternative: check via recent logs for errors ---
check_via_logs() {
    # Count GLM errors in last 10 minutes of OpenClaw logs
    local errors
    errors=$(openclaw logs --lines 200 2>/dev/null \
        | grep -i "glm\|zai" \
        | grep -ci "429\|rate.limit\|quota\|billing\|insufficient\|timeout\|ECONNREFUSED" \
        2>/dev/null || echo "0")
    
    if [[ $errors -gt 3 ]]; then
        return 2
    fi
    return 0
}

# --- Apply config ---
set_primary() {
    local model="$1"
    local timeout="$2"
    
    cp "$CONFIG" "${CONFIG}.bak.$(date +%s)"
    
    python3 -c "
import json
with open('$CONFIG') as f:
    cfg = json.load(f)
cfg['agents']['defaults']['model']['primary'] = '$model'
cfg['agents']['defaults']['timeoutSeconds'] = $timeout
with open('$CONFIG', 'w') as f:
    json.dump(cfg, f, indent=2, ensure_ascii=False)
"
    
    openclaw gateway restart 2>/dev/null || true
}

# --- Main ---
mkdir -p "$SCRIPT_DIR"
get_state

log "Check: MODE=$MODE FAIL=$FAIL_COUNT OK=$OK_COUNT"

# Primary check: direct API call
if check_glm; then
    ((OK_COUNT++))
    FAIL_COUNT=0
    status="ok"
else
    # Fallback: check logs
    if check_via_logs; then
        ((OK_COUNT++))
        FAIL_COUNT=0
        status="ok"
    else
        ((FAIL_COUNT++))
        OK_COUNT=0
        status="fail"
    fi
fi

log "Result: $status FAIL=$FAIL_COUNT OK=$OK_COUNT"

if [[ "$status" == "ok" && "$MODE" == "local" && $OK_COUNT -ge $RECOVER_THRESHOLD ]]; then
    log "GLM recovered. Switching back to cloud."
    set_primary "$CLOUD_MODEL" "$CLOUD_TIMEOUT"
    MODE="cloud"
    OK_COUNT=0
fi

if [[ "$status" == "fail" && "$MODE" == "cloud" && $FAIL_COUNT -ge $FAIL_THRESHOLD ]]; then
    log "GLM failed $FAIL_THRESHOLD times. Switching to local ($LOCAL_MODEL)."
    set_primary "$LOCAL_MODEL" "$LOCAL_TIMEOUT"
    MODE="local"
    FAIL_COUNT=0
fi

save_state
log "Done: MODE=$MODE"
