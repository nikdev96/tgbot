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
    """Format admin dashboard text (async)"""
    from ..core.app import db

    all_users = await db.get_all_users()

    total_users = len(all_users)
    active_users = sum(1 for u in all_users if not u["is_disabled"])
    disabled_users = total_users - active_users
    voice_enabled_users = sum(1 for u in all_users if u["voice_replies_enabled"])
    total_voice_responses = sum(u["voice_responses_sent"] for u in all_users)

    text = (
        "🔧 Admin Dashboard\n\n"
        f"Total Users: {total_users}\n"
        f"Active: {active_users} | Disabled: {disabled_users}\n"
        f"Voice Replies: {voice_enabled_users} users | {total_voice_responses} sent\n\n"
        "User Summary:\n"
    )

    for user_data in sorted(all_users, key=lambda x: x["user_id"]):
        user_id = user_data["user_id"]
        profile = user_data["user_profile"]
        raw_username = profile["username"] or profile["first_name"] or f"User {user_id}"
        username = escape_markdown(raw_username)
        status = "🔴 Disabled" if user_data["is_disabled"] else "🟢 Active"
        prefs = escape_markdown(", ".join(user_data["preferred_targets"]))
        last_activity = user_data["last_activity"].strftime("%Y-%m-%d %H:%M")
        msg_count = user_data["message_count"]
        voice_replies = "🎤 ON" if user_data["voice_replies_enabled"] else "🎤 OFF"
        voice_sent = user_data["voice_responses_sent"]

        text += (
            f"\n{username} ({user_id})\n"
            f"Status: {status}\n"
            f"Languages: {prefs}\n"
            f"Messages: {msg_count} | Voice: {voice_replies} ({voice_sent} sent)\n"
            f"Last: {last_activity}\n"
        )

    return text