#!/usr/bin/env bash
# git-status.sh — Проверка состояния git
set -euo pipefail

CONFIG="$1"
if [[ ! -f "$CONFIG" ]]; then echo "❌ CONFIG.md не найден"; exit 1; fi

PROJECT_PATH=$(grep 'Путь:' "$CONFIG" | awk '{print $NF}')
cd "$PROJECT_PATH"

issues=0

# Uncommitted changes
if ! git diff --quiet 2>/dev/null || ! git diff --cached --quiet 2>/dev/null; then
  UNSTAGED=$(git diff --stat | tail -1)
  STAGED=$(git diff --cached --stat | tail -1)
  echo "⚠️ Незакоммиченные изменения:"
  [[ -n "$UNSTAGED" ]] && echo "  Unstaged: $UNSTAGED"
  [[ -n "$STAGED" ]] && echo "  Staged: $STAGED"
  ((issues++))
else
  echo "✅ Нет незакоммиченных изменений"
fi

# Current branch
BRANCH=$(git branch --show-current)
echo "📍 Ветка: $BRANCH"

# Stale branches (older than 30 days)
STALE=$(git for-each-ref --sort=-committerdate --format='%(refname:short) %(committerdate:short)' refs/heads/ | \
  awk -v date="$(date -v-30d +%Y-%m-01 2>/dev/null || date -d '30 days ago' +%Y-%m-%d)" \
  '$2 < date {print $1, $2}')
if [[ -n "$STALE" ]]; then
  echo "⚠️ Старые ветки (>30 дней):"
  echo "$STALE"
  ((issues++))
else
  echo "✅ Нет старых веток"
fi

# Behind remote
if git rev-parse --abbrev-ref '@{upstream}' &>/dev/null; then
  BEHIND=$(git rev-list --count 'HEAD..@{upstream}' 2>/dev/null || echo "0")
  if [[ "$BEHIND" -gt 0 ]]; then
    echo "⚠️ Отстаёт от remote на $BEHIND коммитов"
    ((issues++))
  else
    echo "✅ Актуален с remote"
  fi
fi

echo "---"
if [[ $issues -eq 0 ]]; then
  echo "✅ Git в порядке"
  exit 0
else
  echo "⚠️ Проблем: $issues"
  exit 1
fi
