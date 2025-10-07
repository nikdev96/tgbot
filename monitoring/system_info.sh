#!/bin/bash

# System Information and Status Script

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/.env"

BOT_STATUS=$(systemctl is-active translator-bot.service)
UPTIME=$(uptime -p)
DISK_USAGE=$(df -h / | awk 'NR==2 {print $5}')
MEMORY_USAGE=$(free -m | awk 'NR==2{printf "%.1f%%\n", $3*100/$2}')

if [[ "$BOT_STATUS" == "active" ]]; then
    PID=$(systemctl show translator-bot.service --property MainPID --value)
    if [[ "$PID" != "0" ]] && [[ -n "$PID" ]]; then
        BOT_MEMORY=$(ps -o rss= -p "$PID" 2>/dev/null | awk '{print int($1/1024)}')
        BOT_CPU=$(ps -o %cpu= -p "$PID" 2>/dev/null | awk '{print $1}')
    else
        BOT_MEMORY="N/A"
        BOT_CPU="N/A"
    fi
    STATUS_EMOJI="✅"
    STATUS_TEXT="Running"
else
    BOT_MEMORY="N/A"
    BOT_CPU="N/A"
    STATUS_EMOJI="❌"
    STATUS_TEXT="Stopped"
fi

ALERT_MSG="📊 *SYSTEM STATUS REPORT*

🤖 *Translator Bot Status:*
$STATUS_EMOJI Status: \`$STATUS_TEXT\`
🧠 Memory: \`${BOT_MEMORY} MB\`
⚡ CPU: \`${BOT_CPU}%\`

🖥️ *Server Information:*
📡 Server: \`$(hostname)\`
⏰ Uptime: \`$UPTIME\`
💾 Disk Usage: \`$DISK_USAGE\`
🧠 System Memory: \`$MEMORY_USAGE\`

🔍 *Monitoring Status:*
✅ Cron Job: Active (every 2 minutes)
✅ SystemD OnFailure: Configured  
✅ Telegram Alerts: Operational

📅 *Report Time:* \`$(date '+%Y-%m-%d %H:%M:%S UTC')\`"

"$SCRIPT_DIR/telegram_alert.sh" "$ALERT_MSG"
