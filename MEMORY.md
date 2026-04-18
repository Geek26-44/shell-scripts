# MEMORY.md

## Дима
- Дмитрий, 36, Кострома → EST
- ДР: 20 ноября
- Ценит: приватность, чёткость, эффективность
- Цель: автономность от cloud LLM к февралю 2027

## Я (Geek)
- Цифровой аватар, второе я Димы ⚡

## Инфраструктура
- **Mac mini M4** 16GB/256GB, монитор 1920x1080
- **OpenClaw** 2026.4.14
- **Ollama**: Qwen 14B, Gemma 9B, Qwen VL 7B
- **Модель**: только GLM-5, fallbacks УБРАНЫ (16.04.2026)

## Модели

### Antigravity лимиты
- **Сброс:** 12:00 AM EST (полночь) — подтверждено 17.04.2026
- Лимит падает ~10:00 PM EST при активном использовании
- Opus 4.7 успевает ~15 мин до лимита
- **Правило:** Opus ТОЛЬКО для ревью/эскалации, НЕ для кодинга
- Кодинг → Codex (свой лимит)
- Рутина → Gemma 9B (безлимит)
- Email: vechiioleg475@gmail.com
- **Gemma2 9B (локально)** — рутинные задачи, экономия токенов:
  - Транскрипция голосовых (резюме после whisper)
  - Поиск/сортировка по файлам
  - Простые summaries и переводы
  - Классификация сообщений
  - PII фильтрация (предфильтр перед отправкой в cloud)
  - Анализ логов и мониторинг
- **Qwen 14B (локально)** — задачи посложнее:
  - Роутинг запросов
  - Код-ревью
  - Анализ архитектуры
- **GLM-5 (cloud)** — основная для сложных рассуждений
- Antigravity (FREE): Opus 4.6, GPT-5, Gemini 3.1 Pro
- Claude Code v2.1.37, Codex CLI v0.99.0, Gemini CLI v0.27.3
- Whisper — голос→текст (локально)

### Правило токенов
- **Gemma 9B** — ВСЁ второстепенное (heartbeat, транскрипция резюме, summaries, переводы, классификация, анализ логов, PII фильтр)
- **Qwen 14B** — средней сложности (роутинг, код-ревью)
- **GLM-5 (мой мозг 🧠)** — основное общение с Димой + сложные задачи
- **Antigravity** (Opus 4.7, GPT-5, Gemini 3.1 Pro) — если я не могу ответить, эскалация выше
- Принцип: минимум cloud-токенов, максимум локально
- Gemma отрабатывает за 0.5-2с на второстепенных задачах

### Цепочка интеллекта 🧠
```
Gemma 9B (0.5-2с, бесплатна)      ← рутинный рабочий
     ↓ если не справляется
Qwen 14B (локальна, бесплатна)    ← middle tier
     ↓ если сложнее
GLM-5 (мой мозг, cloud)           ← основное общение + сложное
     ↓ если не могу ответить
Antigravity (cloud, бесплатна)     ← Opus 4.7, GPT-5, Gemini 3.1 Pro
     ↓ если лимит исчерпан
9pm EST — сброс лимита Antigravity
```

**Правило**: всегда начинаю с минимальной модели. Если задача требует больше — иду вверх по цепочке. GLM-5 — мой основной мозг для общения с Димой. Antigravity — эскалация когда я не справляюсь.

### Правило: последние модели
- Всегда использовать последние версии моделей от провайдеров
- При выходе новой версии (Opus 4.7→4.8, GPT-5→5.1 и т.д.) → обновлять конфиг и документацию
- Antigravity: проверять какие модели доступны
- Claude Code: обновлять через `npm update -g @anthropic-ai/claude-code`
- Codex CLI: обновлять через `npm update -g @openai/codex`
- Gemini CLI: обновлять через `npm update -g @anthropic-ai/gemini`

## GitHub (Geek26-44)
- code-shelter, LLM-5-thought, qwen-14b, chart.js, learning, mini-game, shell-script-pack
- Finance, 11-steps, Atlantic-Construction-Remodeling-Group
- Правило: всё на GitHub через `gh`, НЕ локально (кроме "на машине")
- **Новые скрипты → сразу пушить в shell-scripts репо**

## MACOS (Multi-Agent Operating System)
- **17 агентов, 6 доменов** (оптимизировано 16.04.2026)
- Документы: `docs/macos/` (DOC-00 through DOC-27)
- AGENT_OPERATING_SYSTEM.md, MODEL_ROUTING.md
- AGENT_MATRIX v3.0 — универсальная система, не только строительство

### Агенты (17):
1. **Geek (Chief Orchestrator)** — управление системой
2. **PMO** — задачи, сроки, delivery
3. **Product Strategy** — дорожная карта
4. **Data Architect** — схемы, модели данных
5. **Finance** — учёт, биллинг, маржи
6. **Budgeting** — бюджетирование, контроль лимитов, ROI
7. **Sales / Pipeline** — клиенты, продажи
8. **Web Research** — поиск, анализ, разведка
9. **Process Improvement** — оптимизация процессов
10. **Frontend** — UI/UX, дизайн-система
11. **Backend** — API, БД, интеграции
12. **AI Systems** — ML, промпт-роутинг
13. **Security** — аудит, защита
14. **DevOps / QA** — инфра, деплой, тесты
15. **Documentation** — документация, база знаний
16. **Compliance / Legal** — юриспруденция, регуляции, контракты
17. **Client Success** — клиентский успех, поддержка

### Под-агенты (создаются при запуске проекта):
- Atlantic Construction: Construction Ops, Estimating, Property Research

## Finance Dashboard
- `~/github/Finance`, PostgreSQL 17, localhost:8080
- Финансы ТОЛЬКО в USD

## Установленные инструменты
- **Ollama**: Gemma2 9B (5.4GB), Qwen 14B (9GB), Qwen VL 7B (6GB), Nomic Embed (274MB)
- **RAM профилирование**: 15.4/16GB, 5.6GB compressed, 0 swap
- **Одновременно 1 большая модель** (переключение 4-12с)
- **Оптимизировано** — НЕ добавлять новые модели, текущий набор оптимален

## Obsidian
- **Obsidian 1.12.7** — установлен через brew
- **Vault:** ~/Documents/Obsidian-Vault
- **Полностью локальный** — НИКАКИЕ данные не уходят наружу (no cloud, no telemetry)
- **Плагины:** Dataview, Templater, Periodic Notes, Calendar, Tag Wrangler
- **Структура:** Daily/ (Q&A логи), Analysis/, Decisions/, Lessons/, Context/, Templates/
- **Gemma 9B** — пишет Q&A лог каждый час (cron)
- **Использование:** структурированная память, анализ активности, уменьшение лишних действий
- **Cloud**: GLM-5 (ZAI), Antigravity (Opus 4.6, GPT-5, Gemini 3.1 Pro)
- **CLI**: Claude Code 2.1.37, Codex CLI 0.99.0, Gemini CLI 0.27.3, WhisperKit 0.18.0
- **Utils**: ffmpeg, cliclick, gh 2.89.0, Node 24.13.0, Python 3.14.3

## Скрипты (scripts/)

### Автоматизация экрана и мышки
- **`mouse.sh`** — **ОСНОВНОЙ** скрипт управления Mac. Клик, двойной клик, правый клик, движение, drag&drop, ввод текста, нажатие клавиш, hotkey, скролл. Использует `cliclick`. Для сайтов и приложений.
  - `mouse.sh click 500 300` — кликнуть
  - `mouse.sh type "Hello"` — ввести текст
  - `mouse.sh key return` — нажать Enter
  - `mouse.sh hotkey cmd,c` — Cmd+C
  - `mouse.sh pos` / `mouse.sh screen` — позиция курсора / разрешение
- **`keep-awake.sh`** — двигает курсор каждые 30с + caffeinate. LaunchAgent `com.geek2026.keep-awake` (RunAtLoad, KeepAlive)
- **`screenshot-to-text.sh`** — скриншот/фото → текст через Qwen VL 7B (локально)
- **`transcribe.sh`** — голосовые → текст через WhisperKit (Apple Silicon native, 3с)
- **`screenshot.sh`** / **`auto-screenshot.sh`** — быстрый/автоматический скриншот
- **`auto-move-screenshots.sh`** — перемещение скриншотов в папку

### Бэкап и конфигурация
- **`backup-memory.sh`** — MEMORY.md + memory/ → Desktop + git push. OpenClaw cron 2:00 EST
- **`rollback-model-config.sh`** — откат openclaw.json из бэкапа
- **`model-failover.sh`** — монитор GLM → Ollama при падении. **ОТКЛЮЧЕН**

### Утилиты
- **`task.sh`** — дашборд задач (localhost:8080)
- **`vault.sh`** — шифрованное хранилище
- **`check-router-ip.sh`** / **`att-router-fix.sh`** — роутер
- **`remote-access-monitor.sh`** — мониторинг удалённого доступа

### Safari
- **`safari-tabs.sh`** / **`safari-tabs-advanced.sh`** — вкладки Safari
- **`safari-history-extractor.sh`** / **`extract-safari-history-v2.sh`** — история Safari
- **`safari-ui.sh`** — UI автоматизация Safari через mouse.sh

### Активные LaunchAgents
- `ai.openclaw.gateway` — OpenClaw (управляется самим OpenClaw)
- `com.geek2026.keep-awake` — экран не гаснет (НЕ трогать при gateway restart)
- `com.geek.dashboard` — Finance Dashboard
- `homebrew.mxcl.ollama` — Ollama
- `homebrew.mxcl.postgresql@17` — PostgreSQL 17

### Устаревшие (не удалять)
- `mouse-daemon.sh`, `mouse-jiggler.sh` — дубли keep-awake, удалены из LaunchAgents
- `automation.sh`, `automation-monitor.sh`, `secure-automation.sh` — ранние версии

## Правила

### Правило разработки (универсальное)
1. **НЕ писать с нуля** — найти open-source основу на GitHub
2. **Найти 2-3 решения** — выбрать лучшее из каждого
3. **Собрать лучшее** — объединить сильные стороны
4. **Дописать недостающее** — только то, чего нет в open-source
5. **Opus 4.7 = архитектор** — создаёт логику, структуру, разбивает на задачи
6. **Codex / Claude Code = исполнители** — каждый агент получает свою часть
7. **Geek = контроль** — собираю, проверяю, тестирую

Цепочка: Opus (архитектура) → агенты (кодинг) → Geek (сборка + тест)
- Финансы в USD
- Antigravity = primary cloud fallback
- Уведомлять о завершении процессов
- Скрипт-откатчик перед конфиг-изменениями
- **ПЕРЕД любым критичным изменением → `git commit`** (состояние системы)
- Workspace Git: `Geek26-44/openclaw-workspace` (private), origin/master
- Backup: Desktop/Geek-Backup/ + GitHub push (cron 2:10 EST)
- .gitignore: node_modules, *.png/jpg, *.db, *.log, media/, .env
- Fallback модели ОТКЛЮЧЕНЫ — пока только GLM-5
- LaunchAgents НЕ называть `ai.openclaw.*` (кроме gateway) — gateway restart убьёт

## ⚡ Правило: Документы — Основа Основ

**Если что-то ломается → читать `docs/macos/` (26 документов)**

Это Multi-Agent Construction Operating System — полная архитектура с governance, system layers, agent matrix, runtime extensions, deployment.

**Приоритет при конфликте:**
Constitution (07) → Quality (08) → Escalation (09) → Context (11) → Autonomy (12) → Verification (13) → Runtime (14) → System Layers (01-06) → Matrix (10) → Index (00)

**6 законов:**
1. Zero Assumption — не додумывать
2. No Fake Completion — не завершать без validation
3. Verification Before Reasoning — сначала проверяем
4. Context Before Action — контекст перед действием
5. Autonomy Is Conditional — автономия зарабатывается
6. Domain Boundaries Matter — границы важны

---

## Уроки
- npm + sudo = сломанные права → чинить ownership
- macOS respawnит launchd демоны — killall бесполезен
- timeoutSeconds=30 мало → 300
- НЕ давать непроверенную информацию
- keep-awake.sh — launchd + nohup, cliclick нужен accessibility
- НЕ читать все документы целиком → context overflow. Искать точечно.
- LaunchAgents НЕ называть `ai.openclaw.*` — gateway restart убьёт
- Перед конфиг-изменениями — проверять все документы на конфликты
- Дубликаты LaunchAgents (mouse-daemon, mouse-jiggler vs keep-awake) — удалять

## Аудит 16.04.2026
- Проверены все docs/macos/ — конфликтов нет
- MODEL_ROUTING.md обновлён: GLM-5 = основной мозг (не только координация)
- MEMORY.md очищен от дублей GitHub
- Удалены дублирующие LaunchAgents (mouse-daemon, mouse-jiggler)
- keep-awake переименован в com.geek2026.* — не убивается при gateway restart
- Fallbacks убраны из openclaw.json
- Цепочка интеллекта задокументирована: Gemma → Qwen → GLM-5 → Antigravity

## Хроника последних 2 недель (Апр 1-15, 2026)

### Что было сделано и заработало:
- OpenClaw настроен на GLM-5 как единственную основную модель (убраны gpt-4o и другие)
- Telegram подключен и работает
- GitHub аккаунт Geek26-44 подключен через device auth
- Ollama: скачаны gemma2:9b, qwen2.5-coder:14b, qwen2.5vl:7b
- Скрипт screenshot-to-text.sh — фото/скриншоты → текст через локальную VL модель
- Finance Dashboard: PostgreSQL 17 установлен, schema создана через Gemma 9B
- Atlantic Construction репозиторий создан на GitHub
- MACOS: 33 агента, 27 governance документов записаны в docs/macos/
- shell-scripts репо: 31 скрипт запушен на GitHub
- Backup: Desktop/Geek-Backup/ + GitHub, cron 2:00 EST
- keep-awake.sh: launchd + nohup, экран не гаснет

### Повторяющиеся проблемы:
- GLM-5 периодически отваливается → fallback на внутреннюю модель → нет ответа
- Процессы SIGKILL/SIGTERM из-за таймаутов (нужно 300с, не 30с)
- VNC/Screen Sharing exposure — CLOSE_WAIT connections on port 5900
- yt-dlp not found при попытке анализа видео
- Qwen VL 7B — медленная (161s на кадр), кривая кодировка в русских ответах
- Antigravity: "You're out of extra usage — resets 9pm EST"
- GitHub login через CLI — требовал ручного подтверждения через iPad

### Ключевые темы (по частоте):
1. **Настройка моделей** — GLM-5 как основа, борьба с fallback'ами
2. **Автоматизация экрана** — скриншоты → текст, mouse jiggler, accessibility
3. **Finance Dashboard** — PostgreSQL, schema, frontend
4. **GitHub управление** — login, repos, push скриптов
5. **Локальные модели** — что умеют, тесты, скорость
6. **Atlantic Construction** — CRM/SRM для строительства

## Паттерны общения с Димой
- Раздражается когда: 1) одно и то же ломается 2) спрашиваю очевидное 3) таймауты 4) теряется контекст 5) не сообщает о результате
- Работает с Mac только мышкой (НЕТ КЛАВИАТУРЫ) → всё через клики и голосовые
- Правило: «ты сам должен знать что происходит, не спрашивать меня»
- Правило: «если не получается — ищи вариант, не пизди»
- Правило: «НЕ сообщать? а нужно сообщать» — ВСЕГДА уведомлять о завершении
- Подтверждает действия через iPad
- Хочет русский язык по умолчанию, но английский тоже ок
- Любит голосовые → нужен стабильный whisper
- Финансы ТОЛЬКО в USD
- Antigravity: primary cloud fallback (Opus 4.6, GPT-5), лимит сбрасывается 12am EST (полночь)
- Atlantic Construction — строительная CRM/SRM система
- Пароль от Antigravity: Kostroma, email: vechiioleg475@gmail.com
