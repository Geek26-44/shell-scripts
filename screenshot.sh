#!/bin/bash
# Screenshot Organizer Launcher

SCRIPT="/Users/geek2026/.openclaw/workspace/scripts/screenshot-organizer.py"

case "$1" in
    watch)
        echo "Starting screenshot watcher..."
        /Users/geek2026/.openclaw/workspace/.venv/bin/python3 "$SCRIPT" watch
        ;;
    organize)
        echo "Organizing existing screenshots..."
        /Users/geek2026/.openclaw/workspace/.venv/bin/python3 "$SCRIPT" organize
        ;;
    detect)
        /Users/geek2026/.openclaw/workspace/.venv/bin/python3 "$SCRIPT" detect "$2"
        ;;
    ocr)
        /Users/geek2026/.openclaw/workspace/.venv/bin/python3 "$SCRIPT" ocr "$2"
        ;;
    *)
        echo "Screenshot Organizer"
        echo ""
        echo "Usage: $0 <command> [file]"
        echo ""
        echo "Commands:"
        echo "  watch     — watch for new screenshots (auto-organize)"
        echo "  organize  — organize existing screenshots in inbound"
        echo "  detect    — detect device type for file"
        echo "  ocr       — OCR single file"
        echo ""
        echo "Folders:"
        echo "  Inbound:  /Users/geek2026/.openclaw/media/inbound"
        echo "  Output:   ~/Screenshots/Geek/"
        echo "            ├── phone/"
        echo "            ├── ipad/"
        echo "            ├── mac/"
        echo "            ├── photo/"
        echo "            └── ocr/"
        ;;
esac
