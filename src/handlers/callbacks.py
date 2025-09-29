"""
Callback query handlers for inline buttons
"""
import logging
from aiogram import F
from aiogram.types import CallbackQuery
from ..services.analytics import (
    is_user_disabled, update_user_activity, get_user_preferences,
    update_user_preference, toggle_voice_replies, is_admin, set_user_disabled
)
from ..core.app import audit_logger
from ..core.constants import SUPPORTED_LANGUAGES
from ..utils.keyboards import build_preferences_keyboard, build_admin_dashboard_keyboard
from ..utils.formatting import format_admin_dashboard

logger = logging.getLogger(__name__)


def register_handlers(dp):
    """Register callback handlers"""
    dp.callback_query.register(show_menu_callback, F.data == "show_menu")
    dp.callback_query.register(toggle_preference, F.data.startswith("toggle_"))
    dp.callback_query.register(admin_callback, F.data.startswith("admin_"))


async def show_menu_callback(callback: CallbackQuery):
    """Handle show menu button press"""
    user_id = callback.from_user.id

    # Check if user is disabled
    if await is_user_disabled(user_id):
        await callback.answer("❌ Access disabled", show_alert=True)
        return

    # Update user activity
    await update_user_activity(user_id, callback.from_user)

    prefs = await get_user_preferences(user_id)
    enabled = [SUPPORTED_LANGUAGES[lang]["name"] for lang in prefs]

    text = (
        "⚙️ **Language Preferences**\n\n"
        f"**Currently enabled:** {', '.join(enabled) if enabled else 'None'}\n\n"
        "Select languages to enable/disable for translation:"
    )

    keyboard = await build_preferences_keyboard(user_id)

    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=keyboard)
    await callback.answer()


async def toggle_preference(callback: CallbackQuery):
    """Handle language preference and voice replies toggle"""
    user_id = callback.from_user.id
    toggle_data = callback.data.split("_", 1)[1]  # Get everything after "toggle_"

    # Check if user is disabled
    if await is_user_disabled(user_id):
        await callback.answer("❌ Access disabled", show_alert=True)
        return

    # Update user activity
    await update_user_activity(user_id, callback.from_user)

    if toggle_data == "voice_replies":
        # Handle voice replies toggle
        voice_enabled = await toggle_voice_replies(user_id)
        prefs = await get_user_preferences(user_id)
        enabled = [SUPPORTED_LANGUAGES[lang]["name"] for lang in prefs]

        status_msg = "enabled" if voice_enabled else "disabled"
        callback_msg = f"✅ Voice replies {status_msg}"
    else:
        # Handle language preference toggle
        lang_code = toggle_data
        if lang_code not in SUPPORTED_LANGUAGES:
            await callback.answer("Invalid language")
            return

        prefs = await update_user_preference(user_id, lang_code)
        enabled = [SUPPORTED_LANGUAGES[lang]["name"] for lang in prefs]
        callback_msg = f"✅ Updated preferences: {', '.join(enabled)}"

    keyboard = await build_preferences_keyboard(user_id)

    text = (
        "⚙️ **Translation Preferences**\n\n"
        f"**Currently enabled:** {', '.join(enabled)}\n\n"
        "Toggle languages below:"
    )

    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")
    await callback.answer(callback_msg)


async def admin_callback(callback: CallbackQuery):
    """Handle admin dashboard callbacks"""
    user_id = callback.from_user.id

    if not is_admin(user_id):
        await callback.answer("❌ Access denied", show_alert=True)
        return

    action_parts = callback.data.split("_")
    action = action_parts[1]

    if action == "refresh":
        audit_logger.info(f"ADMIN_ACTION: Admin {user_id} refreshed dashboard")
        text = await format_admin_dashboard()
        keyboard = await build_admin_dashboard_keyboard()
        try:
            await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")
            await callback.answer("✅ Dashboard refreshed")
        except Exception as e:
            if "message is not modified" in str(e):
                await callback.answer("✅ Dashboard already up to date")
            else:
                logger.error(f"Error refreshing dashboard: {e}")
                await callback.answer("❌ Error refreshing dashboard")

    elif action in ["enable", "disable"]:
        target_user_id = int(action_parts[2])
        disabled = action == "disable"

        # Update user status
        success = await set_user_disabled(target_user_id, disabled)
        action_text = "disabled" if disabled else "enabled"

        audit_logger.info(f"ADMIN_ACTION: Admin {user_id} {action_text} user {target_user_id}")

        # Refresh dashboard
        text = await format_admin_dashboard()
        keyboard = await build_admin_dashboard_keyboard()
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")
        await callback.answer(f"✅ User {target_user_id} {action_text}")