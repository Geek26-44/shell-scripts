#!/usr/bin/env bash
# health.sh — Проверка доступности сервисов проекта
set -euo pipefail

CONFIG="$1"
if [[ ! -f "$CONFIG" ]]; then echo "❌ CONFIG.md не найден"; exit 1; fi

PROJECT_PATH=$(grep 'Путь:' "$CONFIG" | awk '{print $NF}')
PROJECT_PORT=$(grep 'Порт:' "$CONFIG" | awk -F':? ?' '{print $NF}')
HEALTH_URL=$(grep 'API:' "$CONFIG" | awk '{print $NF}')

errors=0

# Check dev server
if curl -sf -o /dev/null -m 5 "http://localhost:${PROJECT_PORT}" 2>/dev/null; then
  echo "✅ App (port ${PROJECT_PORT}) — доступен"
else
  echo "❌ App (port ${PROJECT_PORT}) — НЕ доступен"
  ((errors++))
fi

# Check health endpoint
if [[ -n "$HEALTH_URL" ]]; then
  if curl -sf -o /dev/null -m 5 "$HEALTH_URL" 2>/dev/null; then
    echo "✅ Health API — OK"
  else
    echo "⚠️ Health API — не отвечает"
    ((errors++))
  fi
fi

# Check DB (PostgreSQL)
if pg_isready -h localhost -p 5432 &>/dev/null; then
  echo "✅ PostgreSQL — доступен"
else
  echo "❌ PostgreSQL — НЕ доступен"
  ((errors++))
fi

# Check Ollama
if curl -sf -o /dev/null -m 3 http://localhost:11434/api/tags 2>/dev/null; then
  echo "✅ Ollama — доступен"
else
  echo "⚠️ Ollama — НЕ доступен"
  ((errors++))
fi

echo "---"
if [[ $errors -eq 0 ]]; then
  echo "✅ Все сервисы в норме"
  exit 0
else
  echo "❌ Проблем: $errors"
  exit 1
fi
