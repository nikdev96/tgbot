"""
Keyboard builders for inline keyboards
"""
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from ..core.constants import SUPPORTED_LANGUAGES
from ..services.analytics import get_user_preferences, is_voice_replies_enabled
from ..core.app import db


async def build_quick_menu_keyboard() -> InlineKeyboardMarkup:
    """Build quick access menu keyboard"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚙️ Language Preferences", callback_data="show_menu")]
    ])
    return keyboard


async def build_preferences_keyboard(user_id: int) -> InlineKeyboardMarkup:
    """Build inline keyboard for language preferences"""
    prefs = await get_user_preferences(user_id)
    buttons = []

    for lang_code, info in SUPPORTED_LANGUAGES.items():
        status = "✅" if lang_code in prefs else "❌"
        text = f"{status} {info['flag']} {info['name']}"
        buttons.append([InlineKeyboardButton(
            text=text,
            callback_data=f"toggle_{lang_code}"
        )])

    # Add voice replies toggle
    voice_enabled = await is_voice_replies_enabled(user_id)
    voice_status = "✅" if voice_enabled else "❌"
    voice_text = f"{voice_status} 🎤 Voice replies"
    buttons.append([InlineKeyboardButton(
        text=voice_text,
        callback_data="toggle_voice_replies"
    )])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


async def build_admin_dashboard_keyboard() -> InlineKeyboardMarkup:
    """Build admin dashboard keyboard (async)"""
    buttons = [
        [InlineKeyboardButton(text="🔄 Refresh", callback_data="admin_refresh")],
    ]

    # Get all users from database
    all_users = await db.get_all_users()
    for user_data in all_users:
        user_id = user_data["user_id"]
        profile = user_data["user_profile"]
        raw_username = profile["username"] or profile["first_name"] or f"User {user_id}"
        # Limit button text length to prevent callback_data issues
        button_username = raw_username[:15] + "..." if len(raw_username) > 15 else raw_username
        status = "🔴" if user_data["is_disabled"] else "🟢"

        if user_data["is_disabled"]:
            buttons.append([InlineKeyboardButton(
                text=f"✅ Enable {button_username}",
                callback_data=f"admin_enable_{user_id}"
            )])
        else:
            buttons.append([InlineKeyboardButton(
                text=f"❌ Disable {button_username}",
                callback_data=f"admin_disable_{user_id}"
            )])

    return InlineKeyboardMarkup(inline_keyboard=buttons)