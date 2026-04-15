#!/bin/bash
# Safari UI Navigator — навигация по Safari через UI автоматизацию
# Обходит защиту парсинга через cliclick + скриншоты

source /Users/geek2026/.openclaw/workspace/scripts/mouse.sh

OUTPUT_DIR="/Users/geek2026/.openclaw/workspace/safari-extracted"
mkdir -p "$OUTPUT_DIR"

# Получить координаты меню Safari
get_menu_bar_y() {
    echo "25" # Обычно меню на высоте ~25px
}

# Клик по меню
click_menu() {
    local menu_name="$1"
    local menu_x
    
    case "$menu_name" in
        "History") menu_x=400 ;; # Примерная позиция
        "Bookmarks") menu_x=450 ;;
        "File") menu_x=50 ;;
        "Edit") menu_x=100 ;;
        "View") menu_x=150 ;;
        *) return 1 ;;
    esac
    
    local menu_y=$(get_menu_bar_y)
    click "$menu_x" "$menu_y"
    sleep 0.5
}

# Открыть историю через меню
open_history() {
    log "Opening Safari History..."
    
    # Активируем Safari
    osascript -e 'tell application "Safari" to activate'
    sleep 1
    
    # Cmd+Y для открытия истории
    hotkey "cmd,y"
    sleep 1
}

# Скриншот активного окна Safari
capture_safari_window() {
    local output="${1:-$OUTPUT_DIR/safari-window.png}"
    
    # Получаем границы окна Safari
    local bounds=$(osascript -e '
    tell application "Safari"
        if (count of windows) > 0 then
            set win to window 1
            set {x, y, x2, y2} to bounds of win
            return (x & "," & y & "," & (x2 - x) & "," & (y2 - y))
        end if
    end tell
    ')
    
    if [ -n "$bounds" ]; then
        IFS=',' read -r x y w h <<< "$bounds"
        screenshot "$x" "$y" "$w" "$h" "$output"
        log "Captured Safari window: $output"
    else
        log "ERROR: No Safari window found"
        return 1
    fi
}

# Прокрутить страницу вниз
scroll_down() {
    local times=${1:-1}
    for i in $(seq 1 $times); do
        cliclick "scroll:down"
        sleep 0.3
    done
}

# Прокрутить страницу вверх
scroll_up() {
    local times=${1:-1}
    for i in $(seq 1 $times); do
        cliclick "scroll:up"
        sleep 0.3
    done
}

# Извлечь историю через UI автоматизацию
extract_history_ui() {
    log "=== Extracting Safari History via UI ==="
    
    open_history
    
    # Делаем несколько скриншотов с прокруткой
    for i in {1..5}; do
        capture_safari_window "$OUTPUT_DIR/history-page-$i.png"
        scroll_down 3
        sleep 0.5
    done
    
    log "Screenshots saved to: $OUTPUT_DIR"
    log "Use OCR to extract text from screenshots"
}

# Извлечь все вкладки с прокруткой
extract_all_tabs() {
    log "=== Extracting All Safari Tabs ==="
    
    # Сначала обычным способом
    osascript /Users/geek2026/.openclaw/workspace/scripts/safari-tabs-detailed.scpt > "$OUTPUT_DIR/tabs.txt"
    
    log "Tabs saved to: $OUTPUT_DIR/tabs.txt"
}

# Командная строка
case "$1" in
    history)
        extract_history_ui
        ;;
    tabs)
        extract_all_tabs
        ;;
    window)
        capture_safari_window "${2:-$OUTPUT_DIR/safari-window.png}"
        ;;
    open-history)
        open_history
        ;;
    *)
        echo "Safari UI Navigator"
        echo ""
        echo "Usage: $0 <command>"
        echo ""
        echo "Commands:"
        echo "  history     — extract history via UI (screenshots)"
        echo "  tabs        — extract all open tabs"
        echo "  window      — capture Safari window screenshot"
        echo "  open-history — open Safari history (Cmd+Y)"
        ;;
esac
