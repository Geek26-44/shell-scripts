#!/bin/bash
# Secure Automation Wrapper — единая точка входа для автоматизации
# Комбинирует whitelist + мониторинг + логирование

SCRIPTS_DIR="/Users/geek2026/.openclaw/workspace/scripts"
source "$SCRIPTS_DIR/secure-automation.sh" 2>/dev/null || true
source "$SCRIPTS_DIR/automation-monitor.sh" 2>/dev/null || true

# Главная функция безопасной автоматизации
safe_automation() {
    local action="$1"
    shift
    
    # 1. Проверка статуса монитора
    if [ -f "$MONITOR_DIR/monitor-state.json" ]; then
        status=$(grep -o '"status": "[^"]*"' "$MONITOR_DIR/monitor-state.json" | cut -d'"' -f4)
        if [ "$status" = "stopped" ]; then
            echo "ERROR: Automation is stopped (emergency stop active)"
            echo "Run: $0 resume"
            return 1
        fi
    fi
    
    # 2. Проверка whitelist
    if ! is_allowed "$action"; then
        echo "ERROR: Action not whitelisted: $action"
        echo ""
        echo "To allow:"
        echo "  $0 allow $action"
        return 1
    fi
    
    # 3. Проверка аномалий
    reset_counters
    if ! check_anomalies "$action"; then
        echo "ERROR: Anomaly detected, action blocked"
        return 1
    fi
    
    # 4. Выполнение действия
    log "Executing: $action $@"
    update_counters "$action"
    
    case "$action" in
        safari:activate)
            osascript -e 'tell application "Safari" to activate'
            ;;
        safari:cmd_y)
            osascript -e 'tell application "System Events" to keystroke "y" using command down'
            ;;
        screenshot:window)
            screencapture -w "${1:-/tmp/screenshot.png}"
            ;;
        screenshot:fullscreen)
            screencapture "${1:-/tmp/screenshot.png}"
            ;;
        *)
            echo "Unknown action: $action"
            return 1
            ;;
    esac
    
    log "Completed: $action"
    return 0
}

# Командная строка
case "$1" in
    run)
        safe_automation "$2" "$3" "$4"
        ;;
    allow)
        whitelist_add "$2"
        ;;
    deny)
        whitelist_remove "$2"
        ;;
    audit)
        audit
        ;;
    status)
        status
        ;;
    stop)
        emergency_stop
        ;;
    resume)
        resume
        ;;
    *)
        echo "Secure Automation Wrapper"
        echo ""
        echo "Usage: $0 <command> [args]"
        echo ""
        echo "Commands:"
        echo "  run <action> [args]  — execute whitelisted action"
        echo "  allow <action>       — add action to whitelist"
        echo "  deny <action>        — remove from whitelist"
        echo "  audit                — show security audit"
        echo "  status               — show monitor status"
        echo "  stop                 — EMERGENCY STOP"
        echo "  resume               — resume after stop"
        echo ""
        echo "Examples:"
        echo "  $0 run safari:activate"
        echo "  $0 run screenshot:window screenshot.png"
        echo "  $0 allow mouse:click_safe"
        echo ""
        echo "Security:"
        echo "  - All actions must be whitelisted"
        echo "  - Anomaly detection (rate limiting)"
        echo "  - Emergency stop available"
        echo "  - Full audit logging"
        ;;
esac
