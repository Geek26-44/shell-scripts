#!/Users/geek2026/.openclaw/workspace/.venv/bin/python3
"""
Screenshot OCR Extractor — извлекает текст со скриншотов
Требует: pip install pytesseract pillow
"""

import sys
import os
from pathlib import Path

try:
    from PIL import Image
    import pytesseract
except ImportError:
    print("ERROR: Install dependencies:")
    print("  pip install pytesseract pillow")
    print("  brew install tesseract")
    sys.exit(1)

def extract_text(image_path, lang='eng+rus'):
    """Извлечь текст из изображения"""
    if not os.path.exists(image_path):
        print(f"ERROR: File not found: {image_path}")
        return None
    
    try:
        img = Image.open(image_path)
        text = pytesseract.image_to_string(img, lang=lang)
        return text
    except Exception as e:
        print(f"ERROR: {e}")
        return None

def extract_urls(text):
    """Извлечь все URLs из текста"""
    import re
    url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+'
    urls = re.findall(url_pattern, text)
    return urls

def main():
    if len(sys.argv) < 2:
        print("Screenshot OCR Extractor")
        print("")
        print("Usage: python3 screenshot-ocr.py <image> [output.txt]")
        print("")
        print("Examples:")
        print("  python3 screenshot-ocr.py screenshot.png")
        print("  python3 screenshot-ocr.py screenshot.png extracted.txt")
        sys.exit(1)
    
    image_path = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else None
    
    print(f"Processing: {image_path}")
    
    text = extract_text(image_path)
    
    if not text:
        print("No text extracted")
        sys.exit(1)
    
    # Извлечь URLs
    urls = extract_urls(text)
    
    output = f"=== OCR Result ===\n\n{text}\n\n"
    
    if urls:
        output += f"=== URLs Found ({len(urls)}) ===\n"
        for url in urls:
            output += f"{url}\n"
    
    if output_file:
        with open(output_file, 'w') as f:
            f.write(output)
        print(f"Saved to: {output_file}")
    else:
        print(output)

if __name__ == '__main__':
    main()
