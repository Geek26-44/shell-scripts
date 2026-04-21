#!/bin/bash
# System cleanup — rotate logs, temp files — no OpenClaw
source "$(dirname "$0")/../config.sh"

LOG="$LOG_DIR/cleanup-$(date +%Y-%m-%d).log"

# Rotate geek-daemon logs (keep 7 days)
find "$LOG_DIR" -name "*.log" -mtime +7 -delete 2>/dev/null

# Clean tmp
find /tmp -name "geek-*" -mtime +3 -delete 2>/dev/null
find /tmp -name "screenshot-*" -mtime +1 -delete 2>/dev/null

# Old screenshot outputs
find "$WORKSPACE" -name "screenshot-output*" -mtime +1 -delete 2>/dev/null

echo "Cleanup done: $(date)" >> "$LOG"
