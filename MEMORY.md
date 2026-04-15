# MEMORY.md

## Дима
- Дмитрий, 36, Кострома → EST
- ДР: 20 ноября
- Ценит: приватность, чёткость, эффективность
- Цель: автономность от cloud LLM к февралю 2027

## Я (Geek)
- Цифровой аватар, второе я Димы ⚡

## Инфраструктура
- **Mac mini M4** 16GB/256GB
- **OpenClaw** 2026.4.14
- **Ollama**: Qwen 14B, Gemma 9B, Qwen VL 7B
- **Fallback цепочка**: GLM-5 → Qwen 14B → Gemma 9B

## Модели
- GLM-5 (cloud) — основная
- Antigravity (FREE): Opus 4.6, GPT-5, Gemini 3.1 Pro
- Claude Code v2.1.37, Codex CLI v0.99.0, Gemini CLI v0.27.3
- WhisperKit — голос→текст (локально)

## GitHub (Geek26-44)
- code-shelter, LLM-5-thought, qwen-14b, chart.js, learning, mini-game, shell-script-pack
- **shell-scripts** — все скрипты из workspace/scripts/ (31 файл)
- Finance, 11-steps, Atlantic-Construction-Remodeling-Group
- Правило: всё на GitHub через `gh`, НЕ локально (кроме "на машине")
- **Новые скрипты → сразу пушить в shell-scripts репо**
- code-shelter, LLM-5-thought, qwen-14b, chart.js, learning, mini-game, shell-script-pack
- Finance, 11-steps, Atlantic-Construction-Remodeling-Group
- Правило: всё на GitHub через `gh`, НЕ локально (кроме "на машине")

## MACOS (Multi-Agent Operating System)
- 33 агента, 6 доменов, 27 governance документов
- Документы: `docs/macos/` (DOC-00 through DOC-27)
- AGENT_OPERATING_SYSTEM.md, MODEL_ROUTING.md

## Finance Dashboard
- `~/github/Finance`, PostgreSQL 17, localhost:3000
- Финансы ТОЛЬКО в USD

## Правила
- Финансы в USD
- Antigravity = primary cloud fallback
- Уведомлять о завершении процессов
- Скрипт-откатчик перед конфиг-изменениями

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
