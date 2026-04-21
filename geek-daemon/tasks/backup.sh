#!/bin/bash
# Backup MEMORY.md + memory/ to Desktop + GitHub — no OpenClaw
source "$(dirname "$0")/../config.sh"

DATE=$(date +%Y-%m-%d)
BACKUP_DIR="$HOME/Desktop/Geek-Backup"

mkdir -p "$BACKUP_DIR/memory"

# Copy files
cp "$WORKSPACE/MEMORY.md" "$BACKUP_DIR/MEMORY_${DATE}.md" 2>/dev/null
cp "$WORKSPACE/MEMORY.md" "$BACKUP_DIR/MEMORY.md" 2>/dev/null
cp -r "$MEMORY_DIR/"*.md "$BACKUP_DIR/memory/" 2>/dev/null

# Git push workspace
cd "$WORKSPACE" 2>/dev/null
git add -A 2>/dev/null
git commit -m "backup $DATE" --allow-empty 2>/dev/null
git push 2>/dev/null

# Git push shell-scripts
cd "$GITHUB_DIR/shell-scripts" 2>/dev/null
git add -A 2>/dev/null
git commit -m "backup $DATE" --allow-empty 2>/dev/null
git push 2>/dev/null

echo "Backup done: $DATE" >> "$LOG_DIR/backup.log"
