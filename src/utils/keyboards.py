"""
Keyboard builders for inline keyboards
"""
import hashlib
from cachetools import TTLCache
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
    "build_translation_feedback_keyboard",
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

    # Short labels for compact buttons
    lang_labels = {
        "ru": "🇷🇺 RU",
        "en": "🇺🇸 EN",
        "th": "🇹🇭 TH",
        "vi": "🇻🇳 VN"
    }

    # Fixed order: ru, en, th, vi
    lang_order = ["ru", "en", "th", "vi"]

    lang_buttons = []
    for lang_code in lang_order:
        if lang_code not in SUPPORTED_LANGUAGES:
            continue
        status = "✅" if lang_code in prefs else "❌"
        text = f"{status} {lang_labels[lang_code]}"
        lang_buttons.append(InlineKeyboardButton(
            text=text,
            callback_data=f"toggle_{lang_code}"
        ))

    # 2 buttons per row
    buttons = [
        [lang_buttons[0], lang_buttons[1]],  # RU, EN
        [lang_buttons[2], lang_buttons[3]],  # TH, VN
    ]

    # Add voice replies toggle
    voice_enabled = await is_voice_replies_enabled(user_id)
    voice_status = "✅" if voice_enabled else "❌"
    buttons.append([InlineKeyboardButton(
        text=f"{voice_status} 🎤 Voice",
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


def build_translation_feedback_keyboard(
    source_text: str,
    source_lang: str,
    target_lang: str,
    translated_text: str
) -> InlineKeyboardMarkup:
    """Build feedback keyboard for translation quality.

    Creates compact inline buttons for quick feedback on translation quality.
    Uses hash-based callback data to avoid Telegram's 64-byte limit.

    Args:
        source_text: Original text (for storing in feedback)
        source_lang: Source language code
        target_lang: Target language code
        translated_text: The translation to get feedback on

    Returns:
        InlineKeyboardMarkup with feedback buttons
    """
    # Create a hash to identify this translation
    # Use 16 chars (64 bits) to reduce collision probability
    data_str = f"{source_text}|{source_lang}|{target_lang}|{translated_text}"
    feedback_id = hashlib.md5(data_str.encode()).hexdigest()[:16]

    buttons = [
        [
            InlineKeyboardButton(text="👍", callback_data=f"fb_pos_{feedback_id}"),
            InlineKeyboardButton(text="👎", callback_data=f"fb_neg_{feedback_id}")
        ]
    ]

    return InlineKeyboardMarkup(inline_keyboard=buttons)


# TTL-based cache for feedback data (24 hours TTL, max 5000 entries)
# This prevents memory leaks and ensures old feedback expires gracefully
_feedback_data_cache: TTLCache = TTLCache(maxsize=5000, ttl=86400)  # 24 hours


def store_feedback_data(
    source_text: str,
    source_lang: str,
    target_lang: str,
    translated_text: str
) -> str:
    """Store translation data for feedback and return feedback ID.

    Uses TTLCache with 24-hour expiration to prevent memory leaks
    while keeping feedback data available for a reasonable time.

    Args:
        source_text: Original text
        source_lang: Source language code
        target_lang: Target language code
        translated_text: The translation

    Returns:
        Feedback ID to use in callback data
    """
    data_str = f"{source_text}|{source_lang}|{target_lang}|{translated_text}"
    feedback_id = hashlib.md5(data_str.encode()).hexdigest()[:16]

    _feedback_data_cache[feedback_id] = {
        "source_text": source_text,
        "source_lang": source_lang,
        "target_lang": target_lang,
        "translated_text": translated_text
    }

    return feedback_id


def get_feedback_data(feedback_id: str) -> dict | None:
    """Retrieve stored feedback data by ID.

    Args:
        feedback_id: The feedback ID from callback data

    Returns:
        Dictionary with translation data or None if expired/not found
    """
    return _feedback_data_cache.get(feedback_id)