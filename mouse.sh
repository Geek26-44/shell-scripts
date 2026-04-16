#!/bin/bash
# mouse.sh — Mouse & Keyboard Automation Framework for macOS
# Uses cliclick for pixel-perfect control
#
# Usage: mouse.sh <command> [args]
#   click <x> <y>            — single click
#   double <x> <y>           — double click
#   right <x> <y>            — right click
#   move <x> <y>             — move cursor
#   drag <x1> <y1> <x2> <y2> — drag and drop
#   type <text>              — type text
#   key <key>                — press key (e.g. "return", "tab")
#   hotkey <cmd,shift,s>     — combo keys
#   pos                      — get cursor position
#   screen                   — get screen resolution
#   wait-click <x> <y> <sec> — wait then click (for slow-loading pages)
#   scroll <amount>          — scroll up (+) or down (-)

MOUSE_LOG="/Users/geek2026/.openclaw/workspace/logs/mouse-automation.log"
mkdir -p "$(dirname "$MOUSE_LOG")"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$MOUSE_LOG"
}

click()  { log "click ($1,$2)";   cliclick "c:$1,$2"; }
dclick() { log "dblclick ($1,$2)"; cliclick "dc:$1,$2"; }
rclick() { log "rclick ($1,$2)";  cliclick "rc:$1,$2"; }
move()   { log "move ($1,$2)";    cliclick "m:$1,$2"; }

drag() {
    log "drag ($1,$2)->($3,$4)"
    cliclick "dd:$1,$2" "dm:$3,$4" "du:$3,$4"
}

type_text() { log "type: $1"; cliclick "t:$1"; }
press_key() { log "key: $1"; cliclick "kp:$1"; }
hotkey()    { log "hotkey: $1"; cliclick "kd:$1" "ku:$1"; }

scroll() {
    local amt=${1:--3}
    log "scroll $amt"
    cliclick "scroll:$amt"
}

case "$1" in
    click)  click "$2" "$3" ;;
    double) dclick "$2" "$3" ;;
    right)  rclick "$2" "$3" ;;
    move)   move "$2" "$3" ;;
    drag)   drag "$2" "$3" "$4" "$5" ;;
    type)   type_text "$2" ;;
    key)    press_key "$2" ;;
    hotkey) hotkey "$2" ;;
    pos)    cliclick "p:." ;;
    screen) system_profiler SPDisplaysDataType 2>/dev/null | grep Resolution | head -1 ;;
    scroll) scroll "$2" ;;
    wait-click)
        sleep "${3:-2}"
        click "$2" "$4"
        ;;
    *)
        echo "Mouse Automation Framework (cliclick)"
        echo "Usage: $0 <command> [args]"
        echo ""
        echo "  click <x> <y>            — single click"
        echo "  double <x> <y>           — double click"
        echo "  right <x> <y>            — right click"
        echo "  move <x> <y>             — move cursor"
        echo "  drag <x1> <y1> <x2> <y2> — drag and drop"
        echo "  type <text>              — type text"
        echo "  key <key>                — press key"
        echo "  hotkey <keys>            — combo (cmd,shift,s)"
        echo "  scroll <amount>          — scroll +up/-down"
        echo "  pos                      — cursor position"
        echo "  screen                   — screen resolution"
        echo "  wait-click <x> <y> <sec> — wait then click"
        ;;
esac
