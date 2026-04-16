#!/bin/bash
# transcribe.sh — Fast audio transcription via WhisperKit (Apple Silicon native)
# Replaces Python whisper for voice messages
# Usage: transcribe.sh <audio_file>

set -euo pipefail

AUDIO="$1"

if [[ ! -f "$AUDIO" ]]; then
    echo "ERROR: file not found: $AUDIO" >&2
    exit 1
fi

# Convert to wav if needed (WhisperKit works best with wav)
TMPWAV=""
case "$AUDIO" in
    *.ogg|*.mp3|*.m4a|*.webm)
        TMPWAV="/tmp/transcribe_$$.wav"
        ffmpeg -y -i "$AUDIO" -ar 16000 -ac 1 -c:a pcm_s16le "$TMPWAV" 2>/dev/null
        AUDIO="$TMPWAV"
        ;;
esac

RESULT=$(whisperkit-cli transcribe --audio-path "$AUDIO" --language ru 2>&1)

# Cleanup
[[ -n "$TMPWAV" && -f "$TMPWAV" ]] && rm -f "$TMPWAV"

echo "$RESULT"
