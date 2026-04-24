#!/bin/bash
# screenshot-to-text.sh — Фото/скриншот → текст через minicpm-v (Ollama)
# Usage: ./screenshot-to-text.sh <input_image> [output_md]
# Works independently from OpenClaw.

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

# Use the shared ocr.sh script
RESULT=$(~/github/shell-scripts/ocr.sh "$IMAGE" "/tmp/ocr_$$.txt" 2>/dev/null)
if [ $? -eq 0 ] && [ -f "/tmp/ocr_$$.txt" ]; then
    cp "/tmp/ocr_$$.txt" "$OUTPUT"
    rm -f "/tmp/ocr_$$.txt"
    echo "✅ Saved to $OUTPUT"
else
    echo "⚠️ OCR failed"
    exit 1
fi
