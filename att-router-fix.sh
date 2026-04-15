#!/bin/bash
# AT&T Router Port Forwarding Auto-Fix
# Автоматически настраивает port forwarding для VNC

ROUTER_IP="192.168.1.254"
USERNAME="admin"
PASSWORD="admin"
INTERNAL_IP="192.168.1.64"
VNC_PORT="5900"

log() {
    echo "[$(date '+%H:%M:%S')] $1" | tee -a /Users/geek2026/.openclaw/workspace/logs/att-router.log
}

test_router_access() {
    log "🔍 Testing AT&T router access..."
    
    # Попытка авторизации через curl
    response=$(timeout 10 curl -s -u "$USERNAME:$PASSWORD" "http://$ROUTER_IP" 2>/dev/null)
    
    if [ $? -eq 0 ] && [ -n "$response" ]; then
        log "✅ Router accessible with credentials"
        return 0
    else
        log "❌ Router not accessible or wrong credentials"
        return 1
    fi
}

check_port_forwarding() {
    log "🔍 Checking current port forwarding rules..."
    
    # Проверка внешнего доступа к VNC
    if timeout 5 nc -z 99.68.180.158 "$VNC_PORT" 2>/dev/null; then
        log "✅ VNC port $VNC_PORT already forwarded correctly"
        return 0
    else
        log "❌ VNC port $VNC_PORT not accessible externally"
        return 1
    fi
}

fix_port_forwarding() {
    log "🔧 Attempting to configure port forwarding..."
    
    # AT&T роутеры обычно используют веб-формы для настройки
    # Сначала получаем главную страницу и ищем CSRF токены
    
    # TODO: Автоматическая настройка через веб-формы AT&T
    # Пока создаём инструкцию для ручной настройки
    
    log "📋 MANUAL SETUP REQUIRED:"
    log "1. Go to http://192.168.1.254"
    log "2. Login: admin/admin"
    log "3. Firewall → NAT/Gaming → Port Forwarding"
    log "4. Add rule:"
    log "   - Service: VNC"
    log "   - Global port: 5900"
    log "   - Base host IP: 192.168.1.64" 
    log "   - Local port: 5900"
    log "   - Protocol: TCP"
    log "5. Save changes"
    
    return 1
}

main() {
    log "🚀 AT&T Router Auto-Fix Starting"
    
    if test_router_access; then
        if ! check_port_forwarding; then
            fix_port_forwarding
        fi
    else
        log "❌ Cannot access router - check credentials or IP"
    fi
    
    log "📊 AT&T Router check complete"
}

main