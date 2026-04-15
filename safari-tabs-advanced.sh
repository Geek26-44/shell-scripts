#!/bin/bash
# Safari Tabs Extractor v2
# Запуск: ./safari-tabs-advanced.sh

OUTPUT="/Users/geek2026/.openclaw/workspace/safari-tabs-current.txt"

echo "=== Safari Tabs [$(date '+%Y-%m-%d %H:%M')] ===" > "$OUTPUT"

osascript /Users/geek2026/.openclaw/workspace/scripts/safari-tabs.scpt >> "$OUTPUT"

cat "$OUTPUT"
echo ""
echo "Total: $(grep -c "^Window" "$OUTPUT" 2>/dev/null || echo 0) tabs"
echo "Saved: $OUTPUT"
