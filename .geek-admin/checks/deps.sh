#!/usr/bin/env bash
# deps.sh — Проверка зависимостей проекта (npm audit + outdated)
set -euo pipefail

CONFIG="$1"
if [[ ! -f "$CONFIG" ]]; then echo "❌ CONFIG.md не найден"; exit 1; fi

PROJECT_PATH=$(grep 'Путь:' "$CONFIG" | awk '{print $NF}')
cd "$PROJECT_PATH"

issues=0

# Detect package manager
if [[ -f "package-lock.json" ]] || [[ -f "package.json" ]]; then
  echo "📦 Проверка npm зависимостей..."

  # npm audit
  audit_output=$(npm audit 2>&1 || true)
  if echo "$audit_output" | grep -q "found 0 vulnerabilities"; then
    echo "✅ npm audit — уязвимостей нет"
  else
    vuln_count=$(echo "$audit_output" | grep -o '[0-9]* vulnerability' | grep -o '[0-9]*' || echo "?")
    echo "⚠️ npm audit — найдено $vuln_count уязвимостей"
    echo "$audit_output" | grep -E "(high|critical|moderate)" | head -5
    ((issues++))
  fi

  # npm outdated
  outdated=$(npm outdated 2>&1 || true)
  if [[ -z "$outdated" ]] || echo "$outdated" | grep -q "empty"; then
    echo "✅ npm outdated — всё актуально"
  else
    echo "⚠️ Устаревшие пакеты:"
    echo "$outdated" | head -10
    ((issues++))
  fi
elif [[ -f "requirements.txt" ]]; then
  echo "📦 Проверка pip зависимостей..."
  if command -v pip-audit &>/dev/null; then
    pip-audit -r requirements.txt 2>&1 && echo "✅ pip-audit — чисто" || { echo "⚠️ pip-audit нашёл проблемы"; ((issues++)); }
  else
    echo "ℹ️ pip-audit не установлен, пропуск"
  fi
else
  echo "ℹ️ Зависимости не обнаружены (не npm/pip проект)"
fi

echo "---"
if [[ $issues -eq 0 ]]; then
  echo "✅ Зависимости в порядке"
  exit 0
else
  echo "⚠️ Проблем: $issues"
  exit 1
fi
