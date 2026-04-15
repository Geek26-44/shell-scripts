#!/bin/bash
# Safari History Extractor v2 — только cliclick (без System Events)

OUTPUT_DIR="/Users/geek2026/.openclaw/workspace/safari-extracted"
mkdir -p "$OUTPUT_DIR"

echo "=== Safari History Extractor v2 ==="
echo ""

# 1. Активируем Safari
echo "[1/5] Activating Safari..."
osascript -e 'tell application "Safari" to activate'
sleep 1

# 2. Открываем историю через Cmd+Y (cliclick)
echo "[2/5] Opening History (Cmd+Y)..."
cliclick "c:50,25"  # Click on History menu
sleep 0.5
cliclick "c:50,450"  # Click on "Show All History" option
sleep 2

# 3. Делаем скриншот активного окна
echo "[3/5] Taking screenshot..."
screencapture -o -w "$OUTPUT_DIR/history-window.png"

if [ -f "$OUTPUT_DIR/history-window.png" ]; then
    echo "   ✓ Screenshot saved"
else
    # Если интерактивный выбор не сработал, берём fullscreen
    echo "   ! Using fullscreen capture..."
    screencapture "$OUTPUT_DIR/history-window.png"
fi

# 4. OCR для извлечения текста
echo "[4/5] Running OCR..."
/Users/geek2026/.openclaw/workspace/.venv/bin/python3 << 'EOF'
import pytesseract
from PIL import Image
import re
import sys

try:
    img = Image.open("/Users/geek2026/.openclaw/workspace/safari-extracted/history-window.png")
    text = pytesseract.image_to_string(img, lang='rus+eng')

    # Save full text
    with open("/Users/geek2026/.openclaw/workspace/safari-extracted/history-text.txt", 'w') as f:
        f.write(text)

    # Extract URLs
    urls = re.findall(r'https?://[^\s<>"{}|\\\\^`\[\]]+', text)

    with open("/Users/geek2026/.openclaw/workspace/safari-extracted/history-urls.txt", 'w') as f:
        f.write('\n'.join(urls))

    print(f"   ✓ Extracted {len(urls)} URLs")

except Exception as e:
    print(f"   ✗ Error: {e}")
    sys.exit(1)
EOF

# 5. Показать GitHub URLs
echo "[5/5] Searching for GitHub..."
if [ -f "$OUTPUT_DIR/history-urls.txt" ]; then
    github_urls=$(grep -i "github" "$OUTPUT_DIR/history-urls.txt" 2>/dev/null)

    if [ -n "$github_urls" ]; then
        echo ""
        echo "=== ✅ GitHub URLs Found ==="
        echo "$github_urls"

        # Сохраняем GitHub URLs отдельно
        echo "$github_urls" > "$OUTPUT_DIR/github-urls.txt"
        echo ""
        echo "Saved to: $OUTPUT_DIR/github-urls.txt"
    else
        echo "   No GitHub URLs in current view"
        echo "   Tip: Open Safari History, scroll to show GitHub pages, then run again"
    fi
fi

echo ""
echo "=== Output Files ==="
echo "  $OUTPUT_DIR/history-window.png"
echo "  $OUTPUT_DIR/history-text.txt"
echo "  $OUTPUT_DIR/history-urls.txt"
