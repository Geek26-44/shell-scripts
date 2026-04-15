#!/bin/bash
# Auto-move screenshots to Geek folder
# Watch Desktop for new screenshots

DEST="/Users/geek2026/Screenshots/Geek"

while true; do
    # Find new screenshots on Desktop
    find ~/Desktop -name "Screen Shot*" -mmin -1 -exec mv {} "$DEST/" \; 2>/dev/null
    find ~/Desktop -name "Снимок экрана*" -mmin -1 -exec mv {} "$DEST/" \; 2>/dev/null
    sleep 2
done
