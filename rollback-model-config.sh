#!/bin/bash
# Rollback script: restores openclaw config from backup and restarts gateway
# Usage: ./rollback-model-config.sh
# Safe to run anytime — checks backup exists first

CONFIG="/Users/geek2026/.openclaw/openclaw.json"
BACKUP="/Users/geek2026/.openclaw/openclaw.json.bak"

if [ ! -f "$BACKUP" ]; then
  echo "ERROR: No backup found at $BACKUP"
  exit 1
fi

echo "Rolling back config from backup..."
cp "$BACKUP" "$CONFIG"
echo "Config restored. Restarting gateway..."
openclaw gateway restart
echo "Done. Rollback complete."
