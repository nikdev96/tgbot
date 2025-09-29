"""
Command handlers (/start, /menu, /admin)
"""
import logging
from aiogram import F
from aiogram.filters import Command
from aiogram.types import Message

logger = logging.getLogger(__name__)


def register_handlers(dp):
    """Register command handlers"""
    dp.message.register(start_handler, Command("start"))
    dp.message.register(menu_handler, Command("menu"))
    dp.message.register(admin_handler, Command("admin"))


async def start_handler(message: Message):
    """Handle /start command"""
    # Import services
    from ..services.analytics import update_user_activity, is_user_disabled
    from ..core.app import audit_logger
    from ..utils.keyboards import build_quick_menu_keyboard

    user_id = message.from_user.id

    # Check if user is disabled
    if await is_user_disabled(user_id):
        audit_logger.warning(f"BLOCKED_ACCESS: Disabled user {user_id} attempted /start")
        await message.reply(
            "❌ Access disabled. Contact support if you believe this is an error."
        )
        return

    # Update user activity
    await update_user_activity(user_id, message.from_user)

    text = (
        "🌍 **Translation Bot**\n\n"
        "I translate between 6 languages: 🇷🇺 Russian, 🇺🇸 English, 🇹🇭 Thai, 🇯🇵 Japanese, 🇰🇷 Korean, and 🇻🇳 Vietnamese!\n\n"
        "**How it works:**\n"
        "• Send text or voice messages in supported languages\n"
        "• I'll detect the language and translate to your enabled targets\n"
        "• Use /menu to customize which languages you want\n\n"
        "**Voice messages:** Send voice notes and I'll transcribe + translate!\n\n"
        "Try sending a message or tap the button below:"
    )

    keyboard = await build_quick_menu_keyboard()
    await message.reply(text, reply_markup=keyboard, parse_mode="Markdown")


async def menu_handler(message: Message):
    """Handle /menu command"""
    # Import services
    from ..services.analytics import update_user_activity, is_user_disabled
    from ..core.app import audit_logger
    from ..utils.keyboards import build_preferences_keyboard

    user_id = message.from_user.id

    # Check if user is disabled
    if await is_user_disabled(user_id):
        audit_logger.warning(f"BLOCKED_ACCESS: Disabled user {user_id} attempted /menu")
        await message.reply(
            "❌ Access disabled. Contact support if you believe this is an error."
        )
        return

    # Update user activity
    await update_user_activity(user_id, message.from_user)

    menu_text = """⚙️ **Translation Preferences**

Toggle languages on/off:
✅ = Enabled (will translate)
❌ = Disabled (skip translation)

**Voice Replies:**
🔊 Enable to get TTS audio responses
💰 Uses additional OpenAI credits

Choose your preferences below:"""

    keyboard = await build_preferences_keyboard(user_id)
    await message.answer(menu_text, reply_markup=keyboard, parse_mode="Markdown")


async def admin_handler(message: Message):
    """Handle /admin command"""
    # Import services
    from ..services.analytics import is_admin, update_user_activity, is_user_disabled
    from ..core.app import audit_logger
    from ..utils.keyboards import build_admin_dashboard_keyboard
    from ..utils.formatting import format_admin_dashboard

    user_id = message.from_user.id

    # Check if user is disabled
    if await is_user_disabled(user_id):
        audit_logger.warning(f"BLOCKED_ACCESS: Disabled user {user_id} attempted /admin")
        await message.reply(
            "❌ Access disabled. Contact support if you believe this is an error."
        )
        return

    # Update user activity
    await update_user_activity(user_id, message.from_user)

    # Check admin privileges
    if not is_admin(user_id):
        audit_logger.warning(f"BLOCKED_ACCESS: Non-admin user {user_id} attempted admin access")
        await message.reply("❌ Access denied. Admin privileges required.")
        return

    # Log admin access
    audit_logger.info(f"ADMIN_ACCESS: Admin {user_id} accessed dashboard")

    # Get dashboard content
    dashboard_text = await format_admin_dashboard()
    keyboard = await build_admin_dashboard_keyboard()

    await message.answer(dashboard_text, reply_markup=keyboard, parse_mode="Markdown")