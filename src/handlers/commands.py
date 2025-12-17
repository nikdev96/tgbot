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

    # Check for deep link (room join)
    if message.text and len(message.text.split()) > 1:
        param = message.text.split()[1]
        if param.startswith("join_"):
            room_code = param.replace("join_", "")
            # Redirect to room join with language selection
            from aiogram.fsm.context import FSMContext
            from ..core.app import dp
            state = dp.fsm.get_context(bot=message.bot, user_id=user_id, chat_id=message.chat.id)

            # Auto-trigger join flow
            from .room_commands import handle_join_command
            await handle_join_command(message, room_code, state)
            return

    text = (
        "🌍 **Translation Bot**\n\n"
        "I translate between 6 languages: 🇷🇺 Russian, 🇺🇸 English, 🇹🇭 Thai, 🇸🇦 Arabic, 🇰🇷 Korean, and 🇻🇳 Vietnamese!\n\n"
        "**Features:**\n"
        "• 📝 Text & 🎤 Voice translation with auto-detection\n"
        "• 🏠 Translation Rooms - Multi-user chat with auto-translation\n"
        "• 🔊 TTS voice responses (optional)\n"
        "• ⚙️ Customizable language preferences\n\n"
        "**Commands:**\n"
        "• /menu - Language settings\n"
        "• /room - Create or join translation room\n\n"
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