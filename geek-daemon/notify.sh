#!/bin/bash
# Send notification via Telegram Bot API (direct, no OpenClaw)
# Usage: notify.sh "message"
source "$(dirname "$0")/config.sh"

MSG="$1"
if [ -z "$MSG" ]; then
    MSG="$(cat)"  # read from stdin
fi

# Split long messages
LEN=${#MSG}
if [ "$LEN" -gt 4096 ]; then
    # Send first 4096 chars
    curl -s -X POST "https://api.telegram.org/bot${NOTIFY_BOT_TOKEN}/sendMessage" \
        -H "Content-Type: application/json" \
        -d "{\"chat_id\": \"${NOTIFY_CHAT_ID}\", \"text\": $(echo "${MSG:0:4090}" | python3 -c 'import sys,json; print(json.dumps(sys.stdin.read()))')}" \
        > /dev/null 2>&1
    # Send remainder
    sleep 1
    "$0" "${MSG:4096}"
else
    curl -s -X POST "https://api.telegram.org/bot${NOTIFY_BOT_TOKEN}/sendMessage" \
        -H "Content-Type: application/json" \
        -d "{\"chat_id\": \"${NOTIFY_CHAT_ID}\", \"text\": $(echo "$MSG" | python3 -c 'import sys,json; print(json.dumps(sys.stdin.read()))')}" \
        > /dev/null 2>&1
fi
