#!/bin/bash
# keep-awake.sh — двигает мышку каждые 30 секунд, экран не засыпает
# Создан 11:54, восстановлен 13:38
# Использует cliclick + caffeinate

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:$PATH"

LOG="/Users/geek2026/.openclaw/workspace/logs/keep-awake.log"
mkdir -p "$(dirname "$LOG")"

echo "[$(date)] keep-awake started (pid $$)" >> "$LOG"

# caffeinate держит экран включённым
caffeinate -d &

while true; do
    if command -v cliclick &>/dev/null; then
        cliclick "m:+1,+1" 2>/dev/null
        sleep 0.2
        cliclick "m:-1,-1" 2>/dev/null
        echo "[$(date)] jiggle OK" >> "$LOG"
    else
        echo "[$(date)] cliclick not found" >> "$LOG"
    fi
    sleep 30
done
