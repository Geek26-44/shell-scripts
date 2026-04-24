#!/bin/bash
# ocr.sh — Фото/скриншот → текст через minicpm-v (Ollama)
# Usage: ./ocr.sh <input_image> [output_file]
# Works independently from OpenClaw.

IMAGE="$1"
OUTPUT="${2:-/dev/stdout}"
TIMEOUT=180

if [ -z "$IMAGE" ]; then
    echo "Usage: $0 <image_path> [output_file]"
    exit 1
fi

if [ ! -f "$IMAGE" ]; then
    echo "Error: File not found: $IMAGE"
    exit 1
fi

# Encode image to base64
B64=$(base64 -i "$IMAGE")

# Call Ollama API directly (minicpm-v)
RESULT=$(curl -s --max-time $TIMEOUT http://localhost:11434/api/generate -d "{
  \"model\": \"minicpm-v\",
  \"prompt\": \"Extract ALL visible text from this image. Rules: 1) Extract every piece of text, no matter how small. 2) Preserve layout (headers, lists, tables as markdown). 3) If UI screenshot, list all buttons, labels, menus. 4) If chat, reproduce messages with senders. 5) NO commentary, NO description — ONLY extracted text.\",
  \"images\": [\"$B64\"],
  \"stream\": false
}" 2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin).get('response','⚠️ Empty response'))" 2>/dev/null)

if [ -z "$RESULT" ]; then
    echo "⚠️ minicpm-v failed or timed out"
    exit 1
fi

if [ "$OUTPUT" = "/dev/stdout" ]; then
    echo "$RESULT"
else
    echo "$RESULT" > "$OUTPUT"
    echo "✅ Saved to $OUTPUT"
fi
