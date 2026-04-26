#!/usr/bin/env bash
# build.sh — Проверка сборки проекта
set -euo pipefail

CONFIG="$1"
if [[ ! -f "$CONFIG" ]]; then echo "❌ CONFIG.md не найден"; exit 1; fi

PROJECT_PATH=$(grep 'Путь:' "$CONFIG" | awk '{print $NF}')
BUILD_CMD=$(grep 'Build:' "$CONFIG" | sed 's/.*: //' | xargs)

if [[ -z "$BUILD_CMD" ]]; then
  echo "⚠️ Build команда не задана"
  exit 0
fi

cd "$PROJECT_PATH"

echo "🔨 Запуск: $BUILD_CMD"
if $BUILD_CMD 2>&1; then
  echo "✅ Сборка успешна"
  exit 0
else
  echo "❌ Сборка упала"
  exit 1
fi
