#!/bin/bash
# backup-memory.sh — бэкап MEMORY.md + memory/ на десктоп + git push
# Запускается по cron каждый день

WORKSPACE="/Users/geek2026/.openclaw/workspace"
DESKTOP="/Users/geek2026/Desktop/Geek-Backup"
REPO="$HOME/github/shell-scripts"
DATE=$(date '+%Y-%m-%d_%H%M%S')

mkdir -p "$DESKTOP/memory"

# Копируем на десктоп
cp "$WORKSPACE/MEMORY.md" "$DESKTOP/MEMORY.md"
cp "$WORKSPACE/MEMORY.md" "$DESKTOP/MEMORY_${DATE}.md"
cp -r "$WORKSPACE/memory/"* "$DESKTOP/memory/" 2>/dev/null

# Храним только последние 30 бэкапов на десктопе
ls -t "$DESKTOP"/MEMORY_202*.md 2>/dev/null | tail -n +31 | xargs rm -f 2>/dev/null

# Git push в shell-scripts репо
cd "$REPO" 2>/dev/null || exit 0
cp "$WORKSPACE/MEMORY.md" . 2>/dev/null
mkdir -p memory
cp -r "$WORKSPACE/memory/"* memory/ 2>/dev/null
cp -r "$WORKSPACE/scripts/"* . 2>/dev/null
git add -A
git diff --cached --quiet || git commit -m "auto-backup: memory + scripts ${DATE}" && git push origin main 2>/dev/null

echo "[$(date)] Backup done → Desktop + GitHub"
