#!/bin/bash
# Auto-screenshot every 10 seconds

DEST="/Users/geek2026/Screenshots/Geek"
mkdir -p "$DEST"

while true; do
    TIMESTAMP=$(date '+%Y%m%d_%H%M%S')
    screencapture "$DEST/screenshot_$TIMESTAMP.png" 2>/dev/null
    sleep 10
done
