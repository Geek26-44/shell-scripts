#!/bin/bash
# mouse-jiggler.sh — двигает курсор каждые 30 секунд через AppleScript
# Экран не засыпает благодаря caffeinate + движение мыши

LOG="/Users/geek2026/.openclaw/workspace/logs/mouse-jiggler.log"
mkdir -p "$(dirname "$LOG")"

echo "[$(date)] mouse-jiggler started (pid $$)" >> "$LOG"

# caffeinate -d в фоне — экран не гаснет
/usr/bin/caffeinate -d &

while true; do
    # AppleScript: получить позицию курсора и сдвинуть
    osascript -e '
    use framework "CoreGraphics"
    set p to current application's class "NSEvent"'s mouseLocation()
    set x to p's x as integer
    set y to p's y as integer
    ' 2>/dev/null
    
    # Простой подход: cliclick через полный путь, с fallthrough на caffeinate
    /opt/homebrew/bin/cliclick "m:+1,+1" 2>/dev/null && sleep 0.3 && /opt/homebrew/bin/cliclick "m:-1,-1" 2>/dev/null
    
    echo "[$(date)] jiggle done" >> "$LOG"
    sleep 30
done
