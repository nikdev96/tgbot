#!/bin/bash

# Bot Status Monitoring Script
# Checks if translator-bot service is running and sends alerts if not

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/.env"

SERVICE_NAME="${SERVICE_NAME:-translator-bot.service}"
STATUS_FILE="$SCRIPT_DIR/.last_status"
ALERT_SCRIPT="$SCRIPT_DIR/telegram_alert.sh"

# Function to log with timestamp
log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S'): $1"
}

# Function to send alert with proper formatting
send_alert() {
    local message="$1"
    local priority="$2"
    
    "$ALERT_SCRIPT" "$message"
}

# Check if service is active
if systemctl is-active --quiet "$SERVICE_NAME"; then
    SERVICE_STATUS="active"
    log "$SERVICE_NAME is running"
else
    SERVICE_STATUS="failed"
    log "$SERVICE_NAME is NOT running"
fi

# Read previous status
PREV_STATUS=""
if [[ -f "$STATUS_FILE" ]]; then
    PREV_STATUS=$(cat "$STATUS_FILE")
fi

# Compare with previous status and send alerts
if [[ "$SERVICE_STATUS" != "$PREV_STATUS" ]]; then
    case "$SERVICE_STATUS" in
        "active")
            if [[ "$PREV_STATUS" == "failed" ]]; then
                ALERT_MSG="✅ *RECOVERY SUCCESS*

🤖 *Translator Bot is BACK ONLINE!*

The service has recovered and is running normally again.

🔧 *Service Details:*
• Status: \`Running\`
• Service: \`$SERVICE_NAME\`
• Recovery: \`Automatic\`"
                
                send_alert "$ALERT_MSG" "medium"
                log "Alert sent: Bot recovered"
            elif [[ -n "$PREV_STATUS" ]]; then
                ALERT_MSG="ℹ️ *SERVICE STARTED*

🚀 *Translator Bot has been started*

The bot service is now active and ready to serve users.

🔧 *Service Details:*
• Status: \`Active\`
• Service: \`$SERVICE_NAME\`"
                
                send_alert "$ALERT_MSG" "low"
                log "Alert sent: Bot started"
            fi
            ;;
        "failed")
            # Get additional info about the failure
            LAST_LOG=$(journalctl -u "$SERVICE_NAME" -n 3 --no-pager -o cat 2>/dev/null | head -200 || echo "Logs unavailable")
            
            ALERT_MSG="🔴 *CRITICAL ALERT*

❌ *Translator Bot is DOWN!*

The service has stopped and requires immediate attention.

📋 *Service Details:*
• Status: \`Failed/Stopped\`
• Service: \`$SERVICE_NAME\`

📄 *Recent Logs:*
\`\`\`
$LAST_LOG
\`\`\`

🔧 *Immediate Actions:*
1. Check status: \`systemctl status translator-bot.service\`
2. View full logs: \`journalctl -u translator-bot.service -n 20\`
3. Restart service: \`systemctl restart translator-bot.service\`"
            
            send_alert "$ALERT_MSG" "high"
            log "Alert sent: Bot is down"
            ;;
    esac
fi

# Save current status
echo "$SERVICE_STATUS" > "$STATUS_FILE"

# Additional health checks
if [[ "$SERVICE_STATUS" == "active" ]]; then
    # Check if process is consuming reasonable resources
    PID=$(systemctl show "$SERVICE_NAME" --property MainPID --value)
    if [[ "$PID" != "0" ]] && [[ -n "$PID" ]]; then
        # Check memory usage (warn if > 500MB)
        MEM_KB=$(ps -o rss= -p "$PID" 2>/dev/null || echo "0")
        MEM_MB=$((MEM_KB / 1024))
        
        if [[ "$MEM_MB" -gt 500 ]]; then
            log "Warning: High memory usage: ${MEM_MB}MB"
            # Only alert for very high memory usage to avoid spam
            if [[ "$MEM_MB" -gt 1000 ]]; then
                MEMORY_ALERT="⚠️ *HIGH MEMORY USAGE WARNING*

🐘 *Memory consumption is high*

The bot is using significant memory resources and may need attention.

📊 *Resource Details:*
• Memory Usage: \`${MEM_MB} MB\`
• Process ID: \`$PID\`
• Service: \`$SERVICE_NAME\`

💡 *Recommendations:*
• Monitor for memory leaks
• Consider restarting if usage continues to grow
• Check for stuck processes or large data sets"
                
                send_alert "$MEMORY_ALERT" "medium"
            fi
        fi
    fi
fi

log "Status check completed: $SERVICE_STATUS"
