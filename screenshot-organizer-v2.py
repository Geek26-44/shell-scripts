#!/Users/geek2026/.openclaw/workspace/.venv/bin/python3
"""
Screenshot Organizer & OCR — с поддержкой LLaVA Vision для фото экранов
"""

import os
import sys
import shutil
import subprocess
import json
from pathlib import Path
from PIL import Image, ImageEnhance, ImageFilter

# Папки
INBOUND = "/Users/geek2026/.openclaw/media/inbound"
ORGANIZED = "/Users/geek2026/Screenshots/Geek"

# Категории
CATEGORIES = {
    "phone": {
        "ratios": [(9, 19), (9, 16), (3, 4)],
        "resolutions": [(1170, 2532), (1284, 2778), (1080, 1920), (750, 1334)],
        "folder": "phone"
    },
    "ipad": {
        "ratios": [(4, 3), (3, 2)],
        "resolutions": [(2048, 2732), (1668, 2388), (1536, 2048)],
        "folder": "ipad"
    },
    "mac": {
        "ratios": [(16, 10), (16, 9), (3, 2)],
        "resolutions": [(2560, 1600), (1920, 1080), (1440, 900), (2880, 1800)],
        "folder": "mac"
    },
    "photo": {
        "folder": "photo"
    }
}

def detect_device(img_path):
    """Определить тип устройства по размеру изображения"""
    try:
        img = Image.open(img_path)
        w, h = img.size
        ratio = w / h

        for device, config in CATEGORIES.items():
            if device == "photo":
                continue

            for r in config.get("ratios", []):
                if abs(ratio - r[0]/r[1]) < 0.1:
                    return device

            for res in config.get("resolutions", []):
                if (w, h) == res or (h, w) == res:
                    return device

        return "photo"

    except Exception as e:
        print(f"Error detecting device: {e}")
        return "photo"

def preprocess_photo(img_path, output_path):
    """Предобработка фото экрана для лучшего распознавания"""
    try:
        img = Image.open(img_path)

        # Конвертировать в RGB
        if img.mode != 'RGB':
            img = img.convert('RGB')

        # Увеличить контраст (убрать блики)
        enhancer = ImageEnhance.Contrast(img)
        img = enhancer.enhance(1.8)

        # Увеличить резкость
        enhancer = ImageEnhance.Sharpness(img)
        img = enhancer.enhance(2.5)

        # Увеличить яркость
        enhancer = ImageEnhance.Brightness(img)
        img = enhancer.enhance(1.1)

        # Размытие для устранения моллирования
        img = img.filter(ImageFilter.MedianFilter(size=3))

        # Увеличить размер для маленьких фото
        w, h = img.size
        if w < 1500:
            img = img.resize((w * 2, h * 2), Image.LANCZOS)

        img.save(output_path, quality=95)
        return output_path

    except Exception as e:
        print(f"Error preprocessing: {e}")
        return img_path

def ocr_tesseract(img_path, device_type):
    """OCR через Tesseract (для чистых скриншотов)"""
    try:
        import pytesseract

        img = Image.open(img_path)
        if img.mode != 'RGB':
            img = img.convert('RGB')

        config = {
            "phone": "--psm 6 -l rus+eng --dpi 300",
            "ipad": "--psm 6 -l rus+eng --dpi 200",
            "mac": "--psm 6 -l rus+eng --dpi 150",
            "photo": "--psm 6 -l rus+eng --dpi 200"
        }

        text = pytesseract.image_to_string(img, config=config.get(device_type, "--psm 6 -l rus+eng"))
        return text.strip()

    except Exception as e:
        print(f"Tesseract error: {e}")
        return ""

def ocr_llava(img_path):
    """OCR через LLaVA Vision (для фото экранов)"""
    try:
        # Предобработка фото
        preprocessed = f"/tmp/preprocessed_{Path(img_path).stem}.jpg"
        preprocess_photo(img_path, preprocessed)

        # Запрос к LLaVA
        prompt = """Extract all text from this image. This is a photo of a computer/phone screen.

Important:
- Extract ALL visible text, even if blurry or small
- Preserve layout and structure
- Include buttons, labels, and UI elements
- If text is in Russian, keep it in Russian
- If text is in English, keep it in English

Format: Just output the extracted text, nothing else."""

        result = subprocess.run(
            ["ollama", "run", "llava:13b", "-q"],
            input=f"{prompt}\n\nImage: {preprocessed}",
            capture_output=True,
            text=True,
            timeout=60
        )

        if result.returncode == 0:
            return result.stdout.strip()
        else:
            print(f"LLaVA error: {result.stderr}")
            return ""

    except subprocess.TimeoutExpired:
        print("LLaVA timeout")
        return ""
    except Exception as e:
        print(f"LLaVA error: {e}")
        return ""

def ocr_image(img_path, device_type):
    """Выбрать лучший OCR метод"""
    # Если это фото экрана — использовать LLaVA
    if device_type == "photo":
        print("  Using LLaVA Vision for photo...")
        text = ocr_llava(img_path)
        if text:
            return text
        else:
            print("  LLaVA failed, trying Tesseract...")
            return ocr_tesseract(img_path, device_type)
    else:
        # Для скриншотов — Tesseract
        print("  Using Tesseract for screenshot...")
        return ocr_tesseract(img_path, device_type)

def organize_screenshots():
    """Главная функция организации скриншотов"""

    # Создать папки
    for device in CATEGORIES.keys():
        Path(f"{ORGANIZED}/{device}").mkdir(parents=True, exist_ok=True)

    Path(f"{ORGANIZED}/ocr").mkdir(parents=True, exist_ok=True)

    # Обработать все файлы
    inbound_path = Path(INBOUND)

    if not inbound_path.exists():
        print(f"Inbound folder not found: {INBOUND}")
        return

    files = list(inbound_path.glob("file_*"))

    for file_path in files:
        if file_path.suffix.lower() not in ['.png', '.jpg', '.jpeg']:
            continue

        print(f"\nProcessing: {file_path.name}")

        # Определить тип
        device_type = detect_device(str(file_path))
        print(f"  Detected: {device_type}")

        # OCR
        print(f"  Running OCR...")
        text = ocr_image(str(file_path), device_type)

        # Сохранить OCR результат
        ocr_file = f"{ORGANIZED}/ocr/{file_path.stem}.txt"
        with open(ocr_file, 'w') as f:
            f.write(f"Device: {device_type}\n")
            f.write(f"Source: {file_path.name}\n")
            f.write(f"Method: {'LLaVA' if device_type == 'photo' else 'Tesseract'}\n")
            f.write(f"{'='*50}\n\n")
            f.write(text)

        print(f"  OCR saved: {ocr_file}")

        # Копировать в нужную папку
        dest_folder = f"{ORGANIZED}/{device_type}"
        dest_file = f"{dest_folder}/{file_path.name}"

        shutil.copy2(str(file_path), dest_file)
        print(f"  Copied to: {dest_file}")

def watch_and_organize():
    """Следить за папкой и обрабатывать новые файлы"""
    import time

    print("Watching for new screenshots...")
    print(f"Inbound: {INBOUND}")
    print(f"Organized: {ORGANIZED}")
    print("")

    processed = set()

    while True:
        try:
            for file_path in Path(INBOUND).glob("file_*.*"):
                if file_path.suffix.lower() not in ['.png', '.jpg', '.jpeg']:
                    continue

                if file_path.name not in processed:
                    print(f"\nNew file: {file_path.name}")

                    device_type = detect_device(str(file_path))
                    print(f"  Detected: {device_type}")

                    text = ocr_image(str(file_path), device_type)

                    ocr_file = f"{ORGANIZED}/ocr/{file_path.stem}.txt"
                    with open(ocr_file, 'w') as f:
                        f.write(f"Device: {device_type}\n")
                        f.write(f"{'='*50}\n\n")
                        f.write(text)

                    dest = f"{ORGANIZED}/{device_type}/{file_path.name}"
                    shutil.copy2(str(file_path), dest)

                    print(f"  Organized: {dest}")
                    if text:
                        print(f"  Preview: {text[:150]}...")

                    processed.add(file_path.name)

            time.sleep(2)

        except KeyboardInterrupt:
            print("\nStopped.")
            break
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(5)

if __name__ == '__main__':
    if len(sys.argv) > 1:
        if sys.argv[1] == "watch":
            watch_and_organize()
        elif sys.argv[1] == "organize":
            organize_screenshots()
        elif sys.argv[1] == "detect" and len(sys.argv) > 2:
            device = detect_device(sys.argv[2])
            print(f"Detected: {device}")
        elif sys.argv[1] == "ocr" and len(sys.argv) > 2:
            device = detect_device(sys.argv[2])
            text = ocr_image(sys.argv[2], device)
            print(text)
    else:
        print("Screenshot Organizer & OCR (with LLaVA Vision)")
        print("")
        print("Usage:")
        print("  python3 screenshot-organizer.py watch     — watch for new screenshots")
        print("  python3 screenshot-organizer.py organize  — organize existing")
        print("  python3 screenshot-organizer.py detect <file> — detect device")
        print("  python3 screenshot-organizer.py ocr <file> — OCR single file")
        print("")
        print("OCR Methods:")
        print("  - Tesseract: for clean screenshots")
        print("  - LLaVA Vision: for photos of screens")
        print("")
        print("Folders:")
        print(f"  {ORGANIZED}/")
        print(f"    ├── phone/")
        print(f"    ├── ipad/")
        print(f"    ├── mac/")
        print(f"    ├── photo/")
        print(f"    └── ocr/")
