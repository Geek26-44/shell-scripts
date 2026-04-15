#!/bin/bash
# Secure Automation Gateway — безопасная автоматизация с whitelist
# Все действия логируются и проверяются перед выполнением

SECURITY_DIR="/Users/geek2026/.openclaw/workspace/security"
WHITELIST="$SECURITY_DIR/whitelist.txt"
LOGS="$SECURITY_DIR/automation.log"
BLOCKED="$SECURITY_DIR/blocked.log"

mkdir -p "$SECURITY_DIR"

# Логирование
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOGS"
}

log_blocked() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] BLOCKED: $1" | tee -a "$BLOCKED"
}

# Проверка whitelist
is_allowed() {
    local action="$1"
    
    # Создать whitelist если не существует
    if [ ! -f "$WHITELIST" ]; then
        cat > "$WHITELIST" << 'EOF'
# Secure Automation Whitelist
# Format: action_type:parameters

# Safari
safari:activate
safari:cmd_y
safari:screenshot

# Screen capture
screenshot:window
screenshot:fullscreen

# Mouse
mouse:click_safe
mouse:scroll_safe

# Keyboard
key:cmd_y
key:cmd_c
key:cmd_v
key:escape

# Scripts
script:extract_history
script:ocr
EOF
        log "Created whitelist: $WHITELIST"
    fi
    
    grep -q "^$action" "$WHITELIST"
    return $?
}

# Безопасный клик (только в определённых зонах)
safe_click() {
    local x=$1 y=$2
    
    # Проверка координат (не кликать в опасные зоны)
    if [ $y -lt 0 ] || [ $y -gt 1200 ]; then
        log_blocked "Click out of bounds: ($x, $y)"
        return 1
    fi
    
    # Проверка whitelist
    if ! is_allowed "mouse:click_safe"; then
        log_blocked "Click not whitelisted"
        return 1
    fi
    
    log "Safe click at ($x, $y)"
    cliclick "c:$x,$y"
}

# Безопасное нажатие клавиш
safe_key() {
    local key="$1"
    local action="key:$key"
    
    if ! is_allowed "$action"; then
        log_blocked "Key not whitelisted: $key"
        return 1
    fi
    
    log "Safe keypress: $key"
    osascript -e "tell application \"System Events\" to keystroke \"$key\""
}

# Безопасный скриншот
safe_screenshot() {
    local output="$1"
    
    if ! is_allowed "screenshot:window"; then
        log_blocked "Screenshot not whitelisted"
        return 1
    fi
    
    log "Safe screenshot: $output"
    screencapture -w "$output"
}

# Аудит действий
audit() {
    echo "=== Security Audit [$(date '+%Y-%m-%d %H:%M')] ==="
    echo ""
    echo "Allowed actions:"
    cat "$WHITELIST" | grep -v "^#" | grep -v "^$"
    echo ""
    echo "Recent actions:"
    tail -20 "$LOGS" 2>/dev/null
    echo ""
    echo "Blocked actions:"
    tail -10 "$BLOCKED" 2>/dev/null || echo "  None"
}

# Добавить действие в whitelist
whitelist_add() {
    local action="$1"
    
    if grep -q "^$action" "$WHITELIST"; then
        echo "Already whitelisted: $action"
        return 0
    fi
    
    echo "$action" >> "$WHITELIST"
    log "Added to whitelist: $action"
    echo "✓ Whitelisted: $action"
}

# Удалить действие из whitelist
whitelist_remove() {
    local action="$1"
    
    if grep -v "^$action" "$WHITELIST" > "$WHITELIST.tmp"; then
        mv "$WHITELIST.tmp" "$WHITELIST"
        log "Removed from whitelist: $action"
        echo "✓ Removed: $action"
    else
        echo "Not found: $action"
    fi
}

# Командная строка
case "$1" in
    click)
        safe_click "$2" "$3"
        ;;
    key)
        safe_key "$2"
        ;;
    screenshot)
        safe_screenshot "${2:-/tmp/screenshot.png}"
        ;;
    audit)
        audit
        ;;
    allow)
        whitelist_add "$2"
        ;;
    deny)
        whitelist_remove "$2"
        ;;
    logs)
        tail -50 "$LOGS"
        ;;
    blocked)
        tail -50 "$BLOCKED"
        ;;
    *)
        echo "Secure Automation Gateway"
        echo ""
        echo "Usage: $0 <command> [args]"
        echo ""
        echo "Commands:"
        echo "  click <x> <y>      — safe click (whitelisted zones only)"
        echo "  key <key>          — safe keypress (whitelisted only)"
        echo "  screenshot [file]  — safe screenshot"
        echo "  audit              — show security audit"
        echo "  allow <action>     — add action to whitelist"
        echo "  deny <action>      — remove action from whitelist"
        echo "  logs               — show recent actions"
        echo "  blocked            — show blocked actions"
        echo ""
        echo "Whitelist: $WHITELIST"
        echo "Logs: $LOGS"
        ;;
esac
