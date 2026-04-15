#!/bin/bash
# Secure Safari History Extractor — безопасное извлечение истории
# Использует защищённую автоматизацию

SCRIPTS_DIR="/Users/geek2026/.openclaw/workspace/scripts"
OUTPUT_DIR="/Users/geek2026/.openclaw/workspace/safari-extracted"
mkdir -p "$OUTPUT_DIR"

source "$SCRIPTS_DIR/automation.sh"

echo "=== Secure Safari History Extractor ==="
echo ""

# 1. Проверка разрешений
if ! grep -q "^safari:activate" "$SECURITY_DIR/whitelist.txt" 2>/dev/null; then
    echo "First run: Adding safe actions to whitelist..."
    "$SCRIPTS_DIR/automation.sh" allow "safari:activate"
    "$SCRIPTS_DIR/automation.sh" allow "safari:cmd_y"
    "$SCRIPTS_DIR/automation.sh" allow "screenshot:window"
    echo ""
fi

# 2. Активируем Safari
echo "[1/4] Activating Safari..."
automation.sh run safari:activate
sleep 1

# 3. Открываем историю
echo "[2/4] Opening History (Cmd+Y)..."
echo "Press Cmd+Y in Safari to open History, then press Enter here..."
read -t 30 dummy 2>/dev/null || echo "Timeout, continuing..."

# Альтернатива: ручное нажатие
# automation.sh run safari:cmd_y

sleep 1

# 4. Скриншот
echo "[3/4] Taking screenshot..."
echo "Click on Safari History window..."
automation.sh run screenshot:window "$OUTPUT_DIR/history-window.png"

if [ ! -f "$OUTPUT_DIR/history-window.png" ]; then
    echo "ERROR: Screenshot failed"
    echo "Fallback: Taking fullscreen..."
    automation.sh run screenshot:fullscreen "$OUTPUT_DIR/history-window.png"
fi

# 5. OCR
echo "[4/4] Running OCR..."
/Users/geek2026/.openclaw/workspace/.venv/bin/python3 << 'EOF'
import pytesseract
from PIL import Image
import re

try:
    img = Image.open("/Users/geek2026/.openclaw/workspace/safari-extracted/history-window.png")
    text = pytesseract.image_to_string(img, lang='rus+eng')

    with open("/Users/geek2026/.openclaw/workspace/safari-extracted/history-text.txt", 'w') as f:
        f.write(text)

    urls = re.findall(r'https?://[^\s<>"{}|\\\\^`\[\]]+', text)
    with open("/Users/geek2026/.openclaw/workspace/safari-extracted/history-urls.txt", 'w') as f:
        f.write('\n'.join(urls))

    print(f"   ✓ Extracted {len(urls)} URLs")

    # GitHub URLs
    github = [u for u in urls if 'github' in u.lower()]
    if github:
        with open("/Users/geek2026/.openclaw/workspace/safari-extracted/github-urls.txt", 'w') as f:
            f.write('\n'.join(github))
        print(f"   ✓ Found {len(github)} GitHub URLs")

except Exception as e:
    print(f"   ✗ Error: {e}")
EOF

# Результаты
echo ""
echo "=== Results ==="
if [ -f "$OUTPUT_DIR/github-urls.txt" ]; then
    echo "GitHub URLs found:"
    cat "$OUTPUT_DIR/github-urls.txt"
else
    echo "No GitHub URLs in current view"
    echo ""
    echo "Tip: Scroll Safari History and run again"
fi

echo ""
echo "Files:"
echo "  $OUTPUT_DIR/history-window.png"
echo "  $OUTPUT_DIR/history-text.txt"
echo "  $OUTPUT_DIR/history-urls.txt"

# Аудит
echo ""
echo "=== Security Audit ==="
automation.sh audit | tail -10
