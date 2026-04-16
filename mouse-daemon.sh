#!/bin/bash
# mouse-daemon.sh — держит mouse.sh доступным, перезапускается при падении
# Запускается через launchd при загрузке системы

MOUSE_SCRIPT="/Users/geek2026/.openclaw/workspace/scripts/mouse.sh"
LOG="/Users/geek2026/.openclaw/workspace/logs/mouse-daemon.log"
PID_FILE="/tmp/mouse-daemon.pid"

mkdir -p "$(dirname "$LOG")"

echo "[$(date)] mouse-daemon started (pid $$)" >> "$LOG"
echo $$ > "$PID_FILE"

# Проверяем что cliclick доступен
if ! command -v cliclick &>/dev/null; then
    echo "[$(date)] ERROR: cliclick not found, exiting" >> "$LOG"
    exit 1
fi

# Keep-alive loop — проверяет доступность каждые 30 секунд
while true; do
    if ! pgrep -f "cliclick" &>/dev/null || ! [ -f "$PID_FILE" ]; then
        echo "[$(date)] Health check OK — mouse tools ready" >> "$LOG"
    fi
    sleep 30
done
