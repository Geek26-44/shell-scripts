#!/bin/bash
# transcribe.sh — Аудио/войс → текст через whisper (local)
# Usage: ./transcribe.sh <input_audio> [language]
# Supports: mp3, wav, ogg, m4a, flac, webm
# Works independently from OpenClaw.

AUDIO="$1"
LANG="${2:-ru}"

if [ -z "$AUDIO" ]; then
    echo "Usage: $0 <audio_file> [language: ru|en|auto]"
    exit 1
fi

if [ ! -f "$AUDIO" ]; then
    echo "Error: File not found: $AUDIO"
    exit 1
fi

# Convert ogg (Telegram voice) to wav if needed
EXT="${AUDIO##*.}"
PROCCESSABLE="$AUDIO"

if [ "$EXT" = "ogg" ] || [ "$EXT" = "webm" ]; then
    WAV="/tmp/whisper_input_$$.wav"
    ffmpeg -y -i "$AUDIO" -ar 16000 -ac 1 "$WAV" 2>/dev/null
    if [ $? -ne 0 ]; then
        echo "⚠️ ffmpeg conversion failed"
        exit 1
    fi
    PROCCESSABLE="$WAV"
fi

# Run whisper
MODEL_SIZE="base"
if [ "$LANG" = "auto" ]; then
    whisper "$PROCCESSABLE" --model "$MODEL_SIZE" --output_format txt --output_dir /tmp/whisper_out_$$ --verbose False 2>/dev/null
else
    whisper "$PROCCESSABLE" --model "$MODEL_SIZE" --language "$LANG" --output_format txt --output_dir /tmp/whisper_out_$$ --verbose False 2>/dev/null
fi

RESULT=""
TXT_FILE="/tmp/whisper_out_$$/$(basename "${PROCCESSABLE%.*}").txt"
if [ -f "$TXT_FILE" ]; then
    RESULT=$(cat "$TXT_FILE")
fi

# Cleanup
rm -rf "/tmp/whisper_out_$$" "$WAV" 2>/dev/null

if [ -z "$RESULT" ]; then
    echo "⚠️ Whisper failed — no transcription"
    exit 1
fi

echo "$RESULT"
