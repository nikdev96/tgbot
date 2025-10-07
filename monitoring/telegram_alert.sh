#!/bin/bash

# Telegram Alert Script for Bot Monitoring
# Usage: ./telegram_alert.sh "message" [chat_id]

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/.env"

MESSAGE="$1"
CHAT_ID="${2:-$ALERT_CHAT_ID}"
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S UTC')
SERVER="${SERVER_NAME:-$(hostname)}"

# Check if required variables are set
if [[ -z "$ALERT_BOT_TOKEN" ]]; then
    echo "ERROR: ALERT_BOT_TOKEN not set in .env file"
    exit 1
fi

if [[ -z "$CHAT_ID" ]] || [[ "$CHAT_ID" == "REPLACE_WITH_YOUR_TELEGRAM_ID" ]]; then
    echo "ERROR: ALERT_CHAT_ID not set in .env file"
    echo "Please set your Telegram ID. You can get it from @userinfobot"
    exit 1
fi

if [[ -z "$MESSAGE" ]]; then
    echo "ERROR: No message provided"
    echo "Usage: $0 \"message\" [chat_id]"
    exit 1
fi

# Format message with proper line breaks and server info
FORMATTED_MESSAGE="🚨 *SERVER ALERT* 🚨

🖥️ *Server:* \`$SERVER\`
⏰ *Time:* \`$TIMESTAMP\`

$MESSAGE

───────────────────────
_Automated monitoring system_"

# Send message to Telegram
RESPONSE=$(curl -s -X POST "https://api.telegram.org/bot${ALERT_BOT_TOKEN}/sendMessage" \
    -d "chat_id=${CHAT_ID}" \
    -d "text=${FORMATTED_MESSAGE}" \
    -d "parse_mode=Markdown" \
    -d "disable_web_page_preview=true")

# Check if message was sent successfully
if echo "$RESPONSE" | grep -q '"ok":true'; then
    echo "✅ Alert sent successfully"
    exit 0
else
    echo "❌ Failed to send alert"
    echo "Response: $RESPONSE"
    exit 1
fi
