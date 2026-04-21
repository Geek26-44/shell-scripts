#!/bin/bash
# Ask local LLM via Ollama — no OpenClaw
# Usage: ask-llm.sh "prompt" [model]
# Output: plain text response
source "$(dirname "$0")/config.sh"

PROMPT="$1"
MODEL="${2:-$MODEL_FAST}"
TIMEOUT="${3:-60}"

if [ -z "$PROMPT" ]; then
    echo "Usage: ask-llm.sh \"prompt\" [model] [timeout]"
    exit 1
fi

RESPONSE=$(curl -s --max-time "$TIMEOUT" "$OLLAMA_URL" \
    -d "{\"model\": \"$MODEL\", \"prompt\": $(echo "$PROMPT" | python3 -c 'import sys,json; print(json.dumps(sys.stdin.read()))'), \"stream\": false, \"options\": {\"num_ctx\": 4096}}" 2>/dev/null)

if [ $? -ne 0 ]; then
    echo "⚠️ Ollama timeout/error"
    exit 1
fi

echo "$RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin).get('response','⚠️ Empty').strip())" 2>/dev/null
