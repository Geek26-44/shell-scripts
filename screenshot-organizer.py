#!/Users/geek2026/.openclaw/workspace/.venv/bin/python3
"""
Screenshot Organizer & OCR — автоматическое распознавание и сортировка скриншотов
"""

import os
import sys
import shutil
from pathlib import Path
from PIL import Image
import pytesseract

# Папки
INBOUND = "/Users/geek2026/.openclaw/media/inbound"
ORGANIZED = "/Users/geek2026/Screenshots/Geek"

# Категории
CATEGORIES = {
    "phone": {
        "ratios": [(9, 19), (9, 16), (3, 4)],  # Типичные для iPhone
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

        # Проверить каждую категорию
        for device, config in CATEGORIES.items():
            if device == "photo":
                continue

            # Проверить соотношение сторон
            for r in config.get("ratios", []):
                if abs(ratio - r[0]/r[1]) < 0.1:
                    return device

            # Проверить точное разрешение
            for res in config.get("resolutions", []):
                if (w, h) == res or (h, w) == res:
                    return device

        # Если не подошло — это фото экрана
        return "photo"

    except Exception as e:
        print(f"Error detecting device: {e}")
        return "photo"

def preprocess_image(img_path, device_type):
    """Предобработка изображения для лучшего OCR"""
    try:
        img = Image.open(img_path)

        # Конвертировать в RGB если нужно
        if img.mode != 'RGB':
            img = img.convert('RGB')

        # Для фото экранов — усиленная предобработка
        if device_type == "photo":
            from PIL import ImageEnhance, ImageFilter

            # Увеличить контрастность
            enhancer = ImageEnhance.Contrast(img)
            img = enhancer.enhance(2.0)

            # Увеличить резкость
            enhancer = ImageEnhance.Sharpness(img)
            img = enhancer.enhance(2.0)

            # Увеличить яркость
            enhancer = ImageEnhance.Brightness(img)
            img = enhancer.enhance(1.2)

            # Размытие для удаления шума
            img = img.filter(ImageFilter.MedianFilter(size=3))

        # Увеличить для маленьких экранов
        if device_type == "phone":
            # Увеличить контраст и для phone (может быть фото)
            from PIL import ImageEnhance
            enhancer = ImageEnhance.Contrast(img)
            img = enhancer.enhance(1.5)

            img = img.resize((img.width * 2, img.height * 2), Image.LANCZOS)

        return img

    except Exception as e:
        print(f"Error preprocessing: {e}")
        return Image.open(img_path)

def ocr_image(img_path, device_type):
    """OCR с настройками для разных устройств"""
    try:
        img = preprocess_image(img_path, device_type)

        # Настройки OCR
        config = {
            "phone": "--psm 6 -l rus+eng --dpi 300",
            "ipad": "--psm 6 -l rus+eng --dpi 200",
            "mac": "--psm 6 -l rus+eng --dpi 150",
            "photo": "--psm 6 -l rus+eng --dpi 200"
        }

        text = pytesseract.image_to_string(img, config=config.get(device_type, "--psm 6 -l rus+eng"))

        return text.strip()

    except Exception as e:
        print(f"OCR error: {e}")
        return ""

def organize_screenshots():
    """Главная функция организации скриншотов"""

    # Создать папки
    for device in CATEGORIES.keys():
        Path(f"{ORGANIZED}/{device}").mkdir(parents=True, exist_ok=True)

    Path(f"{ORGANIZED}/ocr").mkdir(parents=True, exist_ok=True)

    # Обработать все файлы в inbound
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
            # Проверить новые файлы
            for file_path in Path(INBOUND).glob("file_*.png"):
                if file_path.name not in processed:
                    print(f"\nNew screenshot: {file_path.name}")

                    # Определить тип
                    device_type = detect_device(str(file_path))
                    print(f"  Detected: {device_type}")

                    # OCR
                    text = ocr_image(str(file_path), device_type)

                    # Сохранить
                    ocr_file = f"{ORGANIZED}/ocr/{file_path.stem}.txt"
                    with open(ocr_file, 'w') as f:
                        f.write(f"Device: {device_type}\n")
                        f.write(f"{'='*50}\n\n")
                        f.write(text)

                    # Копировать
                    dest = f"{ORGANIZED}/{device_type}/{file_path.name}"
                    shutil.copy2(str(file_path), dest)

                    print(f"  Organized: {dest}")
                    print(f"  OCR preview: {text[:100]}...")

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
        elif sys.argv[1] == "detect":
            if len(sys.argv) > 2:
                device = detect_device(sys.argv[2])
                print(f"Detected: {device}")
        elif sys.argv[1] == "ocr":
            if len(sys.argv) > 2:
                device = detect_device(sys.argv[2])
                text = ocr_image(sys.argv[2], device)
                print(text)
    else:
        print("Screenshot Organizer & OCR")
        print("")
        print("Usage:")
        print("  python3 screenshot-organizer.py watch     — watch for new screenshots")
        print("  python3 screenshot-organizer.py organize  — organize existing screenshots")
        print("  python3 screenshot-organizer.py detect <file> — detect device type")
        print("  python3 screenshot-organizer.py ocr <file> — OCR single file")
        print("")
        print("Folders:")
        print(f"  Inbound: {INBOUND}")
        print(f"  Organized: {ORGANIZED}/")
        print(f"    - phone/")
        print(f"    - ipad/")
        print(f"    - mac/")
        print(f"    - photo/")
        print(f"    - ocr/")
