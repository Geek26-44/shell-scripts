#!/bin/bash
# Daily daemon status report — sends full status to Telegram
source "$(dirname "$0")/../config.sh"

DATE=$(date +"%Y-%m-%d %H:%M")
REPORT="📊 **Geek Daemon Status — $DATE**\n"

# LaunchAgents status
REPORT+="\n🔧 **Services:**\n"
for agent in "com.geek2026.qwen-bot:Qwen Bot" "com.geek2026.daemon.health:Health Check" "com.geek2026.daemon.backup:Backup" "com.geek2026.daemon.obsidian:Obsidian Log" "com.geek2026.daemon.updates:Update Check" "com.geek2026.daemon.cleanup:Cleanup" "com.geek2026.keep-awake:Keep Awake"; do
    LABEL=$(echo "$agent" | cut -d: -f1)
    NAME=$(echo "$agent" | cut -d: -f2)
    STATUS=$(launchctl list 2>/dev/null | grep "$LABEL" | awk '{print $1}')
    if [ -n "$STATUS" ]; then
        if [ "$STATUS" = "-" ]; then
            REPORT+="⏳ $NAME — idle (waiting for schedule)\n"
        else
            REPORT+="✅ $NAME — PID $STATUS\n"
        fi
    else
        REPORT+="❌ $NAME — NOT LOADED\n"
    fi
done

# Last runs
REPORT+="\n📋 **Recent logs:**\n"
for log in health backup obsidian updates cleanup; do
    LATEST=$(ls -t "$LOG_DIR/${log}"*.log 2>/dev/null | head -1)
    if [ -n "$LATEST" ]; then
        LAST=$(tail -1 "$LATEST" 2>/dev/null)
        REPORT+="  $log: $LAST\n"
    else
        REPORT+="  $log: no log yet\n"
    fi
done

# Disk & Memory snapshot
DISK=$(df -h / | tail -1 | awk '{print $3,"/",$2,"("$5")"}')
REPORT+="\n💾 Disk: $DISK\n"

# Ollama check
OLLAMA_STATUS=$(curl -s --max-time 3 http://localhost:11434/api/tags 2>/dev/null | python3 -c "import sys,json; print(str(len(json.load(sys.stdin).get('models',[])))+' models')" 2>/dev/null || echo "DOWN")
REPORT+="🤖 Ollama: $OLLAMA_STATUS\n"

"$(dirname "$0")/../notify.sh" "$(echo -e "$REPORT")"
echo "Status report sent: $DATE"
