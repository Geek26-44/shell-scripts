#!/bin/bash
# Daily system health check — runs via launchd, no OpenClaw
# Notifies via Telegram directly
source "$(dirname "$0")/../config.sh"

LOG="$LOG_DIR/health-$(date +%Y-%m-%d).log"
DATE=$(date +"%Y-%m-%d %H:%M")

REPORT="📋 **System Health — $DATE**\n"

# 1. Services
for svc in "localhost:8080:Dashboard" "localhost:11434:Ollama"; do
    PORT=$(echo "$svc" | cut -d: -f2)
    NAME=$(echo "$svc" | cut -d: -f3)
    if curl -s --max-time 3 "http://localhost:$PORT" > /dev/null 2>&1; then
        REPORT+="✅ $NAME — UP\n"
    else
        REPORT+="❌ $NAME — DOWN\n"
    fi
done

# PostgreSQL
if pg_isready -q 2>/dev/null || pgrep -x postgres > /dev/null; then
    REPORT+="✅ PostgreSQL — UP\n"
else
    REPORT+="❌ PostgreSQL — DOWN\n"
fi

# 2. Disk
DISK=$(df -h / | tail -1 | awk '{print $3, "/", $2, "used (" $5 ")"}')
REPORT+="\n💾 Disk: $DISK\n"

# 3. Memory
MEM=$(vm_stat | head -5 | tail -1)
REPORT+="🧠 Memory: $MEM\n"

# 4. LaunchAgents
REPORT+="\n🔧 LaunchAgents:\n"
for agent in "ai.openclaw.gateway:OpenClaw" "com.geek2026.qwen-bot:Qwen Bot" "com.geek2026.keep-awake:KeepAwake" "homebrew.mxcl.ollama:Ollama" "homebrew.mxcl.postgresql@17:PostgreSQL" "com.geek.dashboard:Dashboard"; do
    LABEL=$(echo "$agent" | cut -d: -f1)
    NAME=$(echo "$agent" | cut -d: -f2)
    if launchctl list 2>/dev/null | grep -q "$LABEL"; then
        PID=$(launchctl list 2>/dev/null | grep "$LABEL" | awk '{print $1}')
        if [ "$PID" = "-" ]; then
            REPORT+="⚠️ $NAME — loaded but not running\n"
        else
            REPORT+="✅ $NAME — running ($PID)\n"
        fi
    else
        REPORT+="❌ $NAME — not loaded\n"
    fi
done

# 5. Git
GIT_LOG=$(cd "$WORKSPACE" && git log --oneline -3 2>/dev/null)
REPORT+="\n📦 Git:\n$GIT_LOG\n"

# 6. Ollama models
MODELS=$(curl -s --max-time 5 http://localhost:11434/api/tags 2>/dev/null | python3 -c "import sys,json; [print('  '+m['name']) for m in json.load(sys.stdin).get('models',[])]" 2>/dev/null)
if [ -n "$MODELS" ]; then
    REPORT+="\n🤖 Ollama models:$MODELS\n"
fi

# Save log
echo -e "$REPORT" > "$LOG"

# Send notification
"$(dirname "$0")/../notify.sh" "$(echo -e "$REPORT")"

echo "Health check done: $DATE"
