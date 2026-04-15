#!/bin/bash
# screenshot-to-text.sh — Фото/скриншот → текстовый .md файл
# Usage: ./screenshot-to-text.sh <input_image> [output_md]

IMAGE="$1"
OUTPUT="${2:-/Users/geek2026/.openclaw/workspace/screenshot-output.md}"

if [ -z "$IMAGE" ]; then
    echo "Usage: $0 <image_path> [output.md]"
    exit 1
fi

if [ ! -f "$IMAGE" ]; then
    echo "Error: File not found: $IMAGE"
    exit 1
fi

echo "Processing: $IMAGE"

# LLaVA извлекает текст
ollama run llava:13b "
You are an OCR and screen-reading assistant. Your ONLY job is to extract ALL visible text from this image.

Rules:
1. Extract EVERY piece of text you can see, no matter how small
2. Preserve layout structure (headers, lists, tables)
3. If it's a UI screenshot, list all buttons, labels, menu items, sidebar items
4. If it's a chat, reproduce all messages with sender names
5. If it's a table, reproduce as markdown table
6. Do NOT describe what you see — ONLY extract text
7. Do NOT add commentary or analysis
8. Format output as markdown

Output the extracted text now:
" "$IMAGE" 2>/dev/null | sed 's/\x1b\[[0-9;]*[a-zA-Z]//g' > "$OUTPUT"

# Cleanup: remove empty lines at start/end
sed -i '' '/./,$!d' "$OUTPUT"
sed -i '' -e :a -e '/^\n*$/{$d;N;ba' -e '}' "$OUTPUT"

LINES=$(wc -l < "$OUTPUT")
echo "✅ Done: $OUTPUT ($LINES lines)"
