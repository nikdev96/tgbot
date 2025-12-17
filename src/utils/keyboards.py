"""
Keyboard builders for inline keyboards
"""
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from ..core.constants import SUPPORTED_LANGUAGES
from ..services.analytics import get_user_preferences, is_voice_replies_enabled
from ..core.app import db

# Export for use in callbacks
__all__ = [
    "build_quick_menu_keyboard",
    "build_preferences_keyboard",
    "build_admin_dashboard_keyboard",
    "build_admin_users_keyboard",
    "build_admin_cleanup_keyboard",
    "build_admin_model_select_keyboard",
    "InlineKeyboardMarkup",
    "InlineKeyboardButton"
]


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
    """Build admin dashboard main keyboard with navigation"""
    buttons = [
        [InlineKeyboardButton(text="👥 Manage Users", callback_data="admin_users")],
        [InlineKeyboardButton(text="🤖 Translation Model", callback_data="admin_model_select")],
        [InlineKeyboardButton(text="📊 Server Status", callback_data="admin_server_status")],
        [InlineKeyboardButton(text="🧹 Cleanup & Maintenance", callback_data="admin_cleanup")],
        [InlineKeyboardButton(text="🔄 Refresh", callback_data="admin_refresh")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


async def build_admin_users_keyboard() -> InlineKeyboardMarkup:
    """Build user management keyboard"""
    buttons = []

    # Get all users from database
    all_users = await db.get_all_users()
    for user_data in sorted(all_users, key=lambda x: x["last_activity"], reverse=True):
        user_id = user_data["user_id"]
        profile = user_data["user_profile"]
        raw_username = profile["username"] or profile["first_name"] or f"User {user_id}"
        # Limit button text length to prevent callback_data issues
        button_username = raw_username[:15] + "..." if len(raw_username) > 15 else raw_username

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

    # Add back button
    buttons.append([InlineKeyboardButton(text="🔙 Back to Dashboard", callback_data="admin_refresh")])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


async def build_admin_cleanup_keyboard() -> InlineKeyboardMarkup:
    """Build cleanup and maintenance keyboard"""
    buttons = [
        [InlineKeyboardButton(text="🗑️ Delete Inactive Users (>3 days)", callback_data="admin_cleanup_users")],
        [InlineKeyboardButton(text="🧹 Clear TTS Cache", callback_data="admin_cleanup_cache")],
        [InlineKeyboardButton(text="♻️ Full Cleanup (All)", callback_data="admin_cleanup_all")],
        [InlineKeyboardButton(text="🔙 Back to Dashboard", callback_data="admin_refresh")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


async def build_admin_model_select_keyboard() -> InlineKeyboardMarkup:
    """Build model selection keyboard"""
    from ..services.model_manager import get_model_manager, AVAILABLE_MODELS

    model_manager = get_model_manager()
    current_model = model_manager.get_current_model()

    buttons = []
    for model_id, model_info in AVAILABLE_MODELS.items():
        # Show checkmark for currently selected model
        status = "✅" if model_id == current_model else "⚪"
        text = f"{status} {model_info['icon']} {model_info['name']}"
        buttons.append([InlineKeyboardButton(
            text=text,
            callback_data=f"admin_set_model_{model_id}"
        )])

    # Add back button
    buttons.append([InlineKeyboardButton(text="🔙 Back to Dashboard", callback_data="admin_refresh")])

    return InlineKeyboardMarkup(inline_keyboard=buttons)