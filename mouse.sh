#!/bin/bash
# Mouse Automation Framework — универсальная система управления курсором
# Использует cliclick для обхода защит парсинга

MOUSE_LOG="/Users/geek2026/.openclaw/workspace/logs/mouse-automation.log"
TEMP_DIR="/tmp/mouse-automation"
mkdir -p "$TEMP_DIR"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$MOUSE_LOG"
}

# === ОСНОВНЫЕ КОМАНДЫ ===

# Клик по координатам
click() {
    local x=$1 y=$2
    log "Click at ($x, $y)"
    cliclick "c:$x,$y"
    sleep 0.2
}

# Двойной клик
double_click() {
    local x=$1 y=$2
    log "Double-click at ($x, $y)"
    cliclick "dc:$x,$y"
    sleep 0.2
}

# Движение курсора
move() {
    local x=$1 y=$2
    log "Move to ($x, $y)"
    cliclick "m:$x,$y"
}

# Перетаскивание (drag & drop)
drag() {
    local x1=$1 y1=$2 x2=$3 y2=$4
    log "Drag from ($x1, $y1) to ($x2, $y2)"
    cliclick "dd:$x1,$y1" "dm:$x2,$y2" "du:$x2,$y2"
}

# Ввод текста
type_text() {
    local text="$1"
    log "Type: $text"
    cliclick "t:$text"
}

# Нажатие клавиш
press_key() {
    local key="$1"
    log "Press key: $key"
    cliclick "kp:$key"
}

# Горячие клавиши
hotkey() {
    local keys="$1"
    log "Hotkey: $keys"
    cliclick "kd:$keys" "ku:$keys"
}

# Скриншот области
screenshot() {
    local x=$1 y=$2 w=$3 h=$4 output="$5"
    log "Screenshot region ($x,$y,$w,$h) -> $output"
    screencapture -R $x,$y,$w,$h "$output"
}

# Скриншот всего экрана
fullscreen() {
    local output="$1"
    log "Fullscreen -> $output"
    screencapture "$output"
}

# === УТИЛИТЫ ===

# Получить позицию курсора
get_cursor_pos() {
    cliclick "p:."
}

# Получить размер экрана
get_screen_size() {
    osascript -e 'tell application "Finder" to get bounds of window of desktop' | awk '{print $3, $4}'
}

# Ждать появления окна
wait_for_window() {
    local app_name="$1"
    local timeout=${2:-10}
    log "Waiting for window: $app_name (timeout: ${timeout}s)"
    
    for i in $(seq 1 $timeout); do
        if osascript -e "tell application \"$app_name\" to if (count of windows) > 0 then return true" 2>/dev/null; then
            log "Window found after ${i}s"
            return 0
        fi
        sleep 1
    done
    
    log "Timeout waiting for window"
    return 1
}

# === КОМАНДНАЯ СТРОКА ===

case "$1" in
    click)
        click "$2" "$3"
        ;;
    double)
        double_click "$2" "$3"
        ;;
    move)
        move "$2" "$3"
        ;;
    drag)
        drag "$2" "$3" "$4" "$5"
        ;;
    type)
        type_text "$2"
        ;;
    key)
        press_key "$2"
        ;;
    hotkey)
        hotkey "$2"
        ;;
    screenshot)
        screenshot "$2" "$3" "$4" "$5" "${6:-$TEMP_DIR/screenshot.png}"
        ;;
    fullscreen)
        fullscreen "${2:-$TEMP_DIR/fullscreen.png}"
        ;;
    pos)
        get_cursor_pos
        ;;
    screen)
        get_screen_size
        ;;
    *)
        echo "Mouse Automation Framework"
        echo ""
        echo "Usage: $0 <command> [args]"
        echo ""
        echo "Commands:"
        echo "  click <x> <y>           — single click"
        echo "  double <x> <y>          — double click"
        echo "  move <x> <y>            — move cursor"
        echo "  drag <x1> <y1> <x2> <y2> — drag and drop"
        echo "  type <text>             — type text"
        echo "  key <key>               — press key"
        echo "  hotkey <keys>           — hotkey (e.g., 'cmd,shift,3')"
        echo "  screenshot <x> <y> <w> <h> [output] — capture region"
        echo "  fullscreen [output]     — capture fullscreen"
        echo "  pos                     — get cursor position"
        echo "  screen                  — get screen size"
        ;;
esac
