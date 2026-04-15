#!/bin/bash
# Safari History Extractor — Complete Workflow

OUTPUT_DIR="/Users/geek2026/.openclaw/workspace/safari-extracted"
mkdir -p "$OUTPUT_DIR"

echo "=== Safari History Extractor ==="
echo ""

# 1. Активируем Safari и открываем историю
echo "[1/4] Opening Safari History..."
osascript -e '
tell application "Safari"
    activate
    delay 0.5
end tell

tell application "System Events"
    keystroke "y" using command down
end tell
'

sleep 2

# 2. Делаем скриншот окна истории
echo "[2/4] Capturing History window..."
screencapture -w "$OUTPUT_DIR/history-window.png"

if [ $? -eq 0 ]; then
    echo "   ✓ Screenshot saved: $OUTPUT_DIR/history-window.png"
else
    echo "   ✗ Screenshot failed"
    exit 1
fi

# 3. OCR для извлечения текста
echo "[3/4] Running OCR..."
/Users/geek2026/.openclaw/workspace/.venv/bin/python3 << EOF
import pytesseract
from PIL import Image
import re

img = Image.open("$OUTPUT_DIR/history-window.png")
text = pytesseract.image_to_string(img, lang='rus+eng')

# Save full text
with open("$OUTPUT_DIR/history-text.txt", 'w') as f:
    f.write(text)

# Extract URLs
urls = re.findall(r'https?://[^\s<>"{}|\\\\^`\[\]]+', text)

with open("$OUTPUT_DIR/history-urls.txt", 'w') as f:
    f.write('\n'.join(urls))

print(f"   ✓ Extracted {len(urls)} URLs")
EOF

# 4. Показать GitHub URLs
echo "[4/4] Searching for GitHub URLs..."
if grep -i "github" "$OUTPUT_DIR/history-urls.txt" 2>/dev/null; then
    echo ""
    echo "=== GitHub URLs Found ==="
    grep -i "github" "$OUTPUT_DIR/history-urls.txt"
else
    echo "   No GitHub URLs found in this screenshot"
    echo "   Tip: Scroll down in History and run again"
fi

echo ""
echo "=== Output Files ==="
echo "  $OUTPUT_DIR/history-window.png"
echo "  $OUTPUT_DIR/history-text.txt"
echo "  $OUTPUT_DIR/history-urls.txt"
