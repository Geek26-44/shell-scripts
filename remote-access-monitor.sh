#!/bin/bash
# Remote Access Monitor & Auto-Fix
# Мониторит внешний доступ и автоматически чинит проблемы
# Минимальная нагрузка на RAM

EXTERNAL_IP="99.68.180.158"
LOCAL_IP="192.168.1.64" 
VNC_PORT="5900"
SSH_PORT="22"
LOG_FILE="/Users/geek2026/.openclaw/workspace/logs/remote-access.log"
STATUS_FILE="/Users/geek2026/.openclaw/workspace/logs/remote-status.json"
CONFIG_FILE="/Users/geek2026/.openclaw/workspace/scripts/router-config.json"

# Создать директорию для логов
mkdir -p "$(dirname "$LOG_FILE")"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

check_screen_sharing() {
    # Проверка что Screen Sharing работает локально
    if nc -z 127.0.0.1 "$VNC_PORT" 2>/dev/null; then
        return 0
    else
        return 1
    fi
}

fix_screen_sharing() {
    log "🔧 FIXING: Screen Sharing not responding locally"
    
    # Перезапуск Screen Sharing сервисов
    sudo launchctl kickstart -k system/com.apple.screensharing 2>/dev/null
    sleep 3
    
    # Проверка после фикса
    if check_screen_sharing; then
        log "✅ FIXED: Screen Sharing restored"
        return 0
    else
        log "❌ FAILED: Could not restore Screen Sharing"
        return 1
    fi
}

check_external_access() {
    # Проверка внешнего доступа через nmap или nc от другого хоста
    # Используем timeout для быстрой проверки
    timeout 5 nc -z "$EXTERNAL_IP" "$VNC_PORT" 2>/dev/null
}

load_router_config() {
    if [ -f "$CONFIG_FILE" ]; then
        # Простое извлечение значений из JSON (без jq для минимальной нагрузки)
        ROUTER_IP=$(grep '"ip"' "$CONFIG_FILE" | cut -d'"' -f4)
        ROUTER_USER=$(grep '"username"' "$CONFIG_FILE" | cut -d'"' -f4)
        ROUTER_PASS=$(grep '"password"' "$CONFIG_FILE" | cut -d'"' -f4)
        AUTO_FIX=$(grep '"auto_fix_enabled"' "$CONFIG_FILE" | cut -d':' -f2 | tr -d ' ,')
        
        if [ "$ROUTER_PASS" = "YOUR_ROUTER_PASSWORD_HERE" ]; then
            log "⚠️ WARNING: Router password not configured in $CONFIG_FILE"
            return 1
        fi
        return 0
    else
        log "❌ Router config not found: $CONFIG_FILE"
        return 1
    fi
}

fix_router_port_forwarding() {
    if ! load_router_config; then
        return 1
    fi
    
    log "🔧 FIXING: Checking router port forwarding"
    
    # Проверка доступности роутера
    if ! ping -c 1 "$ROUTER_IP" >/dev/null 2>&1; then
        log "❌ Router not reachable: $ROUTER_IP"
        return 1
    fi
    
    # Попытка восстановления через curl (универсальный метод)
    # Сначала получаем страницу настроек
    if curl -s --connect-timeout 5 "http://$ROUTER_IP" >/dev/null 2>&1; then
        log "✅ Router web interface accessible"
        # TODO: Добавить специфичную логику для разных роутеров
        # Пока только логируем что роутер доступен
        log "🔧 TODO: Automated router configuration (manual setup required)"
        return 0
    else
        log "❌ Router web interface not accessible"
        return 1
    fi
}

update_status() {
    local vnc_local=$1
    local vnc_external=$2
    local timestamp=$(date -Iseconds)
    
    cat > "$STATUS_FILE" <<EOF
{
    "timestamp": "$timestamp",
    "external_ip": "$EXTERNAL_IP",
    "local_ip": "$LOCAL_IP",
    "vnc_port": $VNC_PORT,
    "vnc_local": $vnc_local,
    "vnc_external": $vnc_external,
    "uptime": "$(uptime | awk '{print $3,$4}' | sed 's/,//')"
}
EOF
}

main() {
    log "🔍 Remote Access Check Starting"
    
    # 1. Проверка локального Screen Sharing
    if check_screen_sharing; then
        log "✅ Screen Sharing: Local OK"
        vnc_local=true
    else
        log "❌ Screen Sharing: Local FAILED"
        fix_screen_sharing
        vnc_local=false
    fi
    
    # 2. Проверка внешнего доступа (быстро, без нагрузки)
    if check_external_access; then
        log "✅ External Access: VNC reachable from outside"
        vnc_external=true
    else
        log "❌ External Access: VNC blocked or router issue"
        vnc_external=false
        
        # Отправка alert'а о недоступности внешнего доступа
        log "🚨 ALERT: Remote access down! Port forwarding issue on AT&T router"
        log "📋 Manual fix: http://192.168.1.254 → Firewall → Port Forward → VNC 5900"
    fi
    
    # 3. Обновление статуса
    update_status "$vnc_local" "$vnc_external"
    
    # 4. Проверка памяти (не должен жрать RAM)
    mem_usage=$(ps -o pid,rss,comm -p $$ | tail -1 | awk '{print $2}')
    if [ "$mem_usage" -gt 10000 ]; then  # 10MB лимит
        log "⚠️ WARNING: Monitor using too much RAM: ${mem_usage}KB"
    fi
    
    log "📊 Monitor cycle complete (RAM: ${mem_usage}KB)"
}

# Запуск с минимальным интервалом
if [ "$1" = "daemon" ]; then
    log "🚀 Starting Remote Access Monitor Daemon"
    while true; do
        main
        sleep 300  # 5 минут между проверками
    done
else
    # Одиночная проверка
    main
fi