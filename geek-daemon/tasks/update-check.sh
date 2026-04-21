#!/bin/bash
# Check for updates to CLI tools and models — no OpenClaw
source "$(dirname "$0")/../config.sh"

REPORT="🔄 **Update Check — $(date +'%Y-%m-%d %H:%M')**\n"

# npm
NPM=$(npm outdated -g 2>/dev/null | grep -iE 'claude|codex|gemini|openclaw')
if [ -n "$NPM" ]; then
    REPORT+="📦 npm updates:\n\`\`\`\n$NPM\n\`\`\`\n"
else
    REPORT+="✅ npm — all current\n"
fi

# brew
BREW=$(brew outdated 2>/dev/null | grep -iE 'ollama|whisper|ffmpeg|gh|postgres')
if [ -n "$BREW" ]; then
    REPORT+="🍺 brew updates:\n\`\`\`\n$BREW\n\`\`\`\n"
else
    REPORT+="✅ brew — all current\n"
fi

# Ollama models
MODELS=$(curl -s --max-time 5 http://localhost:11434/api/tags 2>/dev/null | python3 -c "import sys,json; [print('  '+m['name']+' ('+str(round(m.get('size',0)/1e9,1))+'GB)') for m in json.load(sys.stdin).get('models',[])]" 2>/dev/null)
REPORT+="\n🤖 Ollama:\n$MODELS\n"

# Notify
"$(dirname "$0")/../notify.sh" "$(echo -e "$REPORT")"

echo "Update check done: $(date)"
