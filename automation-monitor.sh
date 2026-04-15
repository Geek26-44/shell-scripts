#!/bin/bash
# Automation Monitor — мониторинг автоматизации в реальном времени
# Детектирует аномалии и может остановить опасные действия

MONITOR_DIR="/Users/geek2026/.openclaw/workspace/security"
MONITOR_LOG="$MONITOR_DIR/monitor.log"
ALERTS="$MONITOR_DIR/alerts.log"
STATE="$MONITOR_DIR/monitor-state.json"

mkdir -p "$MONITOR_DIR"

# Инициализация состояния
init_state() {
    cat > "$STATE" << 'EOF'
{
  "clicks_per_minute": 0,
  "keystrokes_per_minute": 0,
  "last_reset": "2026-04-04T00:00:00",
  "total_actions": 0,
  "blocked_actions": 0,
  "status": "active"
}
EOF
}

# Проверка аномалий
check_anomalies() {
    local action_type="$1"
    local threshold_clicks=50      # Максимум кликов в минуту
    local threshold_keystrokes=100 # Максимум нажатий в минуту
    
    # Читаем текущее состояние
    if [ ! -f "$STATE" ]; then
        init_state
    fi
    
    local clicks=$(grep -o '"clicks_per_minute": [0-9]*' "$STATE" | grep -o '[0-9]*')
    local keystrokes=$(grep -o '"keystrokes_per_minute": [0-9]*' "$STATE" | grep -o '[0-9]*')
    
    # Проверка превышения лимитов
    if [ "$action_type" = "click" ] && [ "$clicks" -gt "$threshold_clicks" ]; then
        alert "CRITICAL: Too many clicks ($clicks/min > $threshold_clicks)"
        return 1
    fi
    
    if [ "$action_type" = "keystroke" ] && [ "$keystrokes" -gt "$threshold_keystrokes" ]; then
        alert "CRITICAL: Too many keystrokes ($keystrokes/min > $threshold_keystrokes)"
        return 1
    fi
    
    # Проверка подозрительных паттернов
    if [ "$clicks" -gt 30 ] && [ "$keystrokes" -gt 50 ]; then
        alert "WARNING: High activity detected (clicks: $clicks, keystrokes: $keystrokes)"
    fi
    
    return 0
}

# Запись алерта
alert() {
    local message="$1"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $message" | tee -a "$ALERTS"
    
    # Можно добавить уведомление
    osascript -e "display notification \"$message\" with title \"Automation Alert\"" 2>/dev/null
}

# Обновление счётчиков
update_counters() {
    local action_type="$1"
    
    # Увеличиваем соответствующий счётчик
    if [ -f "$STATE" ]; then
        case "$action_type" in
            click)
                sed -i '' 's/"clicks_per_minute": \([0-9]*\)/"clicks_per_minute": \1+1/' "$STATE" 2>/dev/null || true
                ;;
            keystroke)
                sed -i '' 's/"keystrokes_per_minute": \([0-9]*\)/"keystrokes_per_minute": \1+1/' "$STATE" 2>/dev/null || true
                ;;
        esac
    fi
}

# Сброс счётчиков каждую минуту
reset_counters() {
    local now=$(date '+%Y-%m-%dT%H:%M:%S')
    
    if [ -f "$STATE" ]; then
        local last_reset=$(grep -o '"last_reset": "[^"]*"' "$STATE" | cut -d'"' -f4)
        local last_min=$(echo "$last_reset" | cut -d'T' -f2 | cut -d':' -f2)
        local current_min=$(date '+%M')
        
        if [ "$last_min" != "$current_min" ]; then
            # Сбрасываем счётчики
            sed -i '' 's/"clicks_per_minute": [0-9]*/"clicks_per_minute": 0/' "$STATE"
            sed -i '' 's/"keystrokes_per_minute": [0-9]*/"keystrokes_per_minute": 0/' "$STATE"
            sed -i '' "s/\"last_reset\": \"[^\"]*\"/\"last_reset\": \"$now\"/" "$STATE"
        fi
    fi
}

# Остановка всех автоматизаций (emergency stop)
emergency_stop() {
    log "EMERGENCY STOP activated"
    
    # Убить все процессы cliclick
    pkill -9 cliclick 2>/dev/null
    
    # Убить все osascript процессы
    pkill -9 osascript 2>/dev/null
    
    # Обновить статус
    if [ -f "$STATE" ]; then
        sed -i '' 's/"status": "active"/"status": "stopped"/' "$STATE"
    fi
    
    alert "EMERGENCY: All automation stopped"
    
    # Уведомление
    osascript -e 'display dialog "Automation Emergency Stop\n\nAll automation processes killed." buttons {"OK"} default button "OK"'
}

# Возобновление работы
resume() {
    if [ -f "$STATE" ]; then
        sed -i '' 's/"status": "stopped"/"status": "active"/' "$STATE"
    fi
    log "Automation resumed"
}

# Проверка статуса
status() {
    if [ ! -f "$STATE" ]; then
        init_state
    fi
    
    echo "=== Automation Monitor Status ==="
    cat "$STATE" | python3 -m json.tool 2>/dev/null || cat "$STATE"
    echo ""
    
    if [ -f "$ALERTS" ]; then
        echo "=== Recent Alerts ==="
        tail -5 "$ALERTS"
    fi
}

# Логирование
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$MONITOR_LOG"
}

# Командная строка
case "$1" in
    check)
        check_anomalies "$2"
        ;;
    update)
        update_counters "$2"
        ;;
    reset)
        reset_counters
        ;;
    stop)
        emergency_stop
        ;;
    resume)
        resume
        ;;
    status)
        status
        ;;
    init)
        init_state
        echo "Monitor initialized"
        ;;
    *)
        echo "Automation Monitor"
        echo ""
        echo "Usage: $0 <command>"
        echo ""
        echo "Commands:"
        echo "  check <type>  — check for anomalies (click/keystroke)"
        echo "  update <type> — update counters"
        echo "  reset         — reset per-minute counters"
        echo "  stop          — EMERGENCY STOP (kill all automation)"
        echo "  resume        — resume automation"
        echo "  status        — show current status"
        echo "  init          — initialize monitor"
        echo ""
        echo "Thresholds:"
        echo "  Clicks: 50/min"
        echo "  Keystrokes: 100/min"
        ;;
esac
