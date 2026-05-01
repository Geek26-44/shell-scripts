# Graph Report - shell-scripts  (2026-04-30)

## Corpus Check
- 8 files · ~15,368 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 55 nodes · 71 edges · 9 communities detected
- Extraction: 100% EXTRACTED · 0% INFERRED · 0% AMBIGUOUS
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_Community 0|Community 0]]
- [[_COMMUNITY_Community 1|Community 1]]
- [[_COMMUNITY_Community 2|Community 2]]
- [[_COMMUNITY_Community 3|Community 3]]
- [[_COMMUNITY_Community 4|Community 4]]
- [[_COMMUNITY_Community 5|Community 5]]
- [[_COMMUNITY_Community 6|Community 6]]
- [[_COMMUNITY_Community 7|Community 7]]
- [[_COMMUNITY_Community 8|Community 8]]

## God Nodes (most connected - your core abstractions)
1. `ocr_image()` - 6 edges
2. `ocr_image()` - 5 edges
3. `process_message()` - 5 edges
4. `process_update()` - 5 edges
5. `detect_device()` - 4 edges
6. `organize_screenshots()` - 4 edges
7. `watch_and_organize()` - 4 edges
8. `api()` - 4 edges
9. `detect_device()` - 4 edges
10. `ocr_llava()` - 4 edges

## Surprising Connections (you probably didn't know these)
- `watch_and_organize()` --calls--> `detect_device()`  [EXTRACTED]
  screenshot-organizer-v2.py → screenshot-organizer-v2.py  _Bridges community 6 → community 8_
- `ocr_image()` --calls--> `ocr_llava()`  [EXTRACTED]
  screenshot-organizer-v2.py → screenshot-organizer-v2.py  _Bridges community 7 → community 5_
- `organize_screenshots()` --calls--> `ocr_image()`  [EXTRACTED]
  screenshot-organizer-v2.py → screenshot-organizer-v2.py  _Bridges community 5 → community 6_
- `watch_and_organize()` --calls--> `ocr_image()`  [EXTRACTED]
  screenshot-organizer-v2.py → screenshot-organizer-v2.py  _Bridges community 5 → community 8_

## Communities

### Community 0 - "Community 0"
Cohesion: 0.27
Nodes (10): detect_device(), ocr_image(), organize_screenshots(), preprocess_image(), OCR с настройками для разных устройств, Главная функция организации скриншотов, Следить за папкой и обрабатывать новые файлы, Определить тип устройства по размеру изображения (+2 more)

### Community 1 - "Community 1"
Cohesion: 0.38
Nodes (9): api(), exec_command(), main(), ollama_chat(), process_message(), process_update(), Process user message through Gemma and execute commands, Execute shell command safely (+1 more)

### Community 2 - "Community 2"
Cohesion: 0.47
Nodes (5): extract_text(), extract_urls(), main(), Извлечь текст из изображения, Извлечь все URLs из текста

### Community 3 - "Community 3"
Cohesion: 0.47
Nodes (5): get_recent_memory(), main(), Read last 2 days of memory files., Ask Gemma to summarize recent activity., summarize()

### Community 4 - "Community 4"
Cohesion: 0.4
Nodes (2): get_name(), Extract sender name from message.

### Community 5 - "Community 5"
Cohesion: 0.5
Nodes (4): ocr_image(), ocr_tesseract(), OCR через Tesseract (для чистых скриншотов), Выбрать лучший OCR метод

### Community 6 - "Community 6"
Cohesion: 0.5
Nodes (4): detect_device(), organize_screenshots(), Главная функция организации скриншотов, Определить тип устройства по размеру изображения

### Community 7 - "Community 7"
Cohesion: 0.5
Nodes (4): ocr_llava(), preprocess_photo(), OCR через LLaVA Vision (для фото экранов), Предобработка фото экрана для лучшего распознавания

### Community 8 - "Community 8"
Cohesion: 1.0
Nodes (2): Следить за папкой и обрабатывать новые файлы, watch_and_organize()

## Knowledge Gaps
- **19 isolated node(s):** `Определить тип устройства по размеру изображения`, `Предобработка изображения для лучшего OCR`, `OCR с настройками для разных устройств`, `Главная функция организации скриншотов`, `Следить за папкой и обрабатывать новые файлы` (+14 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **Thin community `Community 4`** (5 nodes): `get_name()`, `ollama()`, `local-llm-telegram-bot.py`, `Extract sender name from message.`, `tg()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 8`** (2 nodes): `Следить за папкой и обрабатывать новые файлы`, `watch_and_organize()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `ocr_image()` connect `Community 5` to `Community 8`, `Community 6`, `Community 7`?**
  _High betweenness centrality (0.017) - this node is a cross-community bridge._
- **Why does `ocr_llava()` connect `Community 7` to `Community 5`?**
  _High betweenness centrality (0.010) - this node is a cross-community bridge._
- **What connects `Определить тип устройства по размеру изображения`, `Предобработка изображения для лучшего OCR`, `OCR с настройками для разных устройств` to the rest of the system?**
  _19 weakly-connected nodes found - possible documentation gaps or missing edges._