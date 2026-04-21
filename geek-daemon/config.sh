#!/bin/bash
# geek-daemon config — paths, tokens, models
# NO OpenClaw dependencies

# === Telegram ===
# @Geek26_Bot for notifications
NOTIFY_BOT_TOKEN="8482650505:AAE_KlOr0cc_F6hoSVGw04O3YV9dNmIfvoo"
NOTIFY_CHAT_ID="170285780"

# @Geek2644G_bot (Qwen 14B)
LLM_BOT_TOKEN="8293339092:AAEbV9-19j0qHv8ZmRU8yIG7EgoVMp-CeZk"

# === Ollama ===
OLLAMA_URL="http://localhost:11434/api/generate"
OLLAMA_CHAT_URL="http://localhost:11434/api/chat"
MODEL_FAST="gemma2:9b-32k"       # quick tasks
MODEL_SMART="qwen2.5:14b-32k"    # complex tasks

# === Paths ===
WORKSPACE="/Users/geek2026/.openclaw/workspace"
MEMORY_DIR="$WORKSPACE/memory"
OBSIDIAN_VAULT="/Users/geek2026/Documents/Obsidian-Vault"
OBSIDIAN_LOGS="$OBSIDIAN_VAULT/05_WORKING_MEMORY"
DAEMON_DIR="/Users/geek2026/github/shell-scripts/geek-daemon"
LOG_DIR="/tmp/geek-daemon"
GITHUB_DIR="/Users/geek2026/github"

# === Create dirs ===
mkdir -p "$LOG_DIR" "$OBSIDIAN_LOGS"
