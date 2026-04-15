#!/bin/bash
# Проверка IP роутера

echo "🔍 Поиск IP роутера..."

# Список стандартных IP
ROUTER_IPS=("192.168.1.1" "192.168.0.1" "10.0.0.1" "192.168.1.254")

for ip in "${ROUTER_IPS[@]}"; do
    echo -n "Проверяю $ip... "
    if timeout 3 curl -s "http://$ip" >/dev/null 2>&1; then
        echo "✅ НАЙДЕН! Web интерфейс доступен"
        echo "IP роутера: $ip"
        
        # Обновляем конфиг
        sed -i '' "s/\"ip\": \".*\"/\"ip\": \"$ip\"/" /Users/geek2026/.openclaw/workspace/scripts/router-config.json
        echo "✅ Обновлён router-config.json"
        exit 0
    else
        echo "❌"
    fi
done

echo "❌ Роутер не найден по стандартным адресам"
echo "Попробуй вручную в браузере или укажи IP роутера"