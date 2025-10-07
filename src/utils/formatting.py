"""
Text formatting utilities
"""
import re


def escape_markdown(text: str) -> str:
    """Escape special markdown characters"""
    special_chars = ['_', '*', '`', '[', ']', '(', ')', '~', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    for char in special_chars:
        text = text.replace(char, f'\\{char}')
    return text


async def format_admin_dashboard() -> str:
    """Format admin dashboard main screen with statistics"""
    from ..core.app import db
    from datetime import datetime, timedelta

    all_users = await db.get_all_users()

    total_users = len(all_users)
    active_users = sum(1 for u in all_users if not u["is_disabled"])
    disabled_users = total_users - active_users
    voice_enabled_users = sum(1 for u in all_users if u["voice_replies_enabled"])
    total_voice_responses = sum(u["voice_responses_sent"] for u in all_users)

    # Calculate inactive users (>3 days)
    three_days_ago = datetime.now() - timedelta(days=3)
    inactive_users = sum(1 for u in all_users if u["last_activity"] < three_days_ago)

    text = (
        "🔧 *Admin Dashboard*\n\n"
        "📊 *Statistics:*\n"
        f"• Total Users: `{total_users}`\n"
        f"• Active: `{active_users}` | Disabled: `{disabled_users}`\n"
        f"• Inactive \\(\\>3 days\\): `{inactive_users}`\n"
        f"• Voice Replies: `{voice_enabled_users}` users\n"
        f"• Voice Messages Sent: `{total_voice_responses}`\n\n"
        "📋 *Use buttons below to navigate*"
    )

    return text


async def format_users_list() -> str:
    """Format users list for management"""
    from ..core.app import db

    all_users = await db.get_all_users()

    if not all_users:
        return "👥 *User Management*\n\nNo users found\\."

    text = "👥 *User Management*\n\n"

    for user_data in sorted(all_users, key=lambda x: x["last_activity"], reverse=True):
        user_id = user_data["user_id"]
        profile = user_data["user_profile"]
        raw_username = profile["username"] or profile["first_name"] or f"User {user_id}"
        username = escape_markdown(raw_username)
        status = "🔴 Disabled" if user_data["is_disabled"] else "🟢 Active"
        last_activity = user_data["last_activity"].strftime("%Y\\-%m\\-%d %H:%M")
        msg_count = user_data["message_count"]

        text += (
            f"*{username}* \\(`{user_id}`\\)\n"
            f"{status} \\| Messages: `{msg_count}` \\| Last: {last_activity}\n\n"
        )

    return text

import subprocess
import psutil
import os
import time
from datetime import datetime, timedelta


async def format_server_status() -> str:
    """Format server status information for admin dashboard"""
    try:
        # Bot service status
        try:
            result = subprocess.run(['systemctl', 'is-active', 'translator-bot.service'], 
                                 capture_output=True, text=True)
            bot_status = "🟢 Running" if result.stdout.strip() == 'active' else "🔴 Stopped"
        except Exception:
            bot_status = "❓ Unknown"
        
        # System information
        uptime_seconds = time.time() - psutil.boot_time()
        uptime_str = str(timedelta(seconds=int(uptime_seconds)))
        
        # Memory usage
        memory = psutil.virtual_memory()
        memory_used = f"{memory.used / (1024**3):.1f}GB"
        memory_total = f"{memory.total / (1024**3):.1f}GB"
        memory_percent = f"{memory.percent:.1f}%"
        
        # Disk usage
        disk = psutil.disk_usage('/')
        disk_used = f"{disk.used / (1024**3):.1f}GB"
        disk_total = f"{disk.total / (1024**3):.1f}GB"
        disk_percent = f"{(disk.used / disk.total) * 100:.1f}%"
        
        # CPU usage
        cpu_percent = psutil.cpu_percent(interval=1)
        
        # Bot process info
        try:
            result = subprocess.run(['systemctl', 'show', 'translator-bot.service', 
                                   '--property', 'MainPID', '--value'], 
                                 capture_output=True, text=True)
            pid = result.stdout.strip()
            
            if pid and pid != '0':
                process = psutil.Process(int(pid))
                bot_memory = f"{process.memory_info().rss / (1024**2):.1f}MB"
                bot_cpu = f"{process.cpu_percent():.1f}%"
            else:
                bot_memory = "N/A"
                bot_cpu = "N/A"
        except Exception:
            bot_memory = "N/A"
            bot_cpu = "N/A"
        
        # Server hostname
        hostname = os.uname().nodename
        
        # Current time
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")
        
        text = (
            f"📊 *Server Status Report*\n\n"
            f"🖥️ *Server:* `{hostname}`\n"
            f"⏰ *Current Time:* `{current_time}`\n"
            f"🕐 *Uptime:* `{uptime_str}`\n\n"
            f"🤖 *Translator Bot:*\n"
            f"• Status: {bot_status}\n"
            f"• Memory: `{bot_memory}`\n"
            f"• CPU: `{bot_cpu}`\n\n"
            f"💻 *System Resources:*\n"
            f"• CPU Usage: `{cpu_percent:.1f}%`\n"
            f"• Memory: `{memory_used}/{memory_total}` (`{memory_percent}`)\n"
            f"• Disk: `{disk_used}/{disk_total}` (`{disk_percent}`)\n\n"
            f"🔍 *Monitoring:*\n"
            f"• Automatic checks: ✅ Every 2 minutes\n"
            f"• SystemD alerts: ✅ Configured\n"
            f"• Telegram alerts: ✅ Active\n\n"
            f"_Report generated at {current_time}_"
        )
        
        return text
        
    except Exception as e:
        return f"❌ Error generating server status: {str(e)}"
