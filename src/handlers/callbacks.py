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
from ..core.app import audit_logger, db
from ..core.constants import SUPPORTED_LANGUAGES
from ..utils.keyboards import (
    build_preferences_keyboard,
    build_admin_dashboard_keyboard,
    build_admin_users_keyboard,
    build_admin_cleanup_keyboard,
    build_admin_model_select_keyboard,
)
from ..utils.formatting import format_admin_dashboard, format_server_status, format_users_list

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

    # Static text to prevent layout jumps
    text = (
        "⚙️ **Translation Settings**\n\n"
        "Select languages for translation:"
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
        status_msg = "enabled" if voice_enabled else "disabled"
        callback_msg = f"🎤 Voice replies {status_msg}"
    else:
        # Handle language preference toggle
        lang_code = toggle_data
        if lang_code not in SUPPORTED_LANGUAGES:
            await callback.answer("Invalid language")
            return

        prefs = await update_user_preference(user_id, lang_code)
        lang_name = SUPPORTED_LANGUAGES[lang_code]["name"]
        is_enabled = lang_code in prefs
        callback_msg = f"{'✅' if is_enabled else '❌'} {lang_name}"

    keyboard = await build_preferences_keyboard(user_id)

    # Static text - same as show_menu_callback to prevent layout jumps
    text = (
        "⚙️ **Translation Settings**\n\n"
        "Select languages for translation:"
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
            await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="MarkdownV2")
            await callback.answer("✅ Dashboard refreshed")
        except Exception as e:
            if "message is not modified" in str(e):
                await callback.answer("✅ Dashboard already up to date")
            else:
                logger.error(f"Error refreshing dashboard: {e}")
                await callback.answer("❌ Error refreshing dashboard")


    elif action == "users":
        audit_logger.info(f"ADMIN_ACTION: Admin {user_id} opened user management")
        text = await format_users_list()
        keyboard = await build_admin_users_keyboard()
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="MarkdownV2")
        await callback.answer("👥 User management")

    elif action == "cleanup":
        from ..core.app import db
        from datetime import datetime, timedelta

        if len(action_parts) == 2:
            # Show cleanup menu
            audit_logger.info(f"ADMIN_ACTION: Admin {user_id} opened cleanup menu")

            # Get cleanup statistics
            all_users = await db.get_all_users()
            seven_days_ago = datetime.now() - timedelta(days=7)
            inactive_users = sum(1 for u in all_users if u["last_activity"] < seven_days_ago)

            # Check TTS cache size
            import os
            tts_cache_path = "data/cache/tts"
            cache_files = 0
            cache_size = 0
            if os.path.exists(tts_cache_path):
                for file in os.listdir(tts_cache_path):
                    if file.endswith('.ogg'):
                        cache_files += 1
                        cache_size += os.path.getsize(os.path.join(tts_cache_path, file))
            cache_size_mb = cache_size / (1024 * 1024)

            text = (
                "🧹 *Cleanup \\& Maintenance*\n\n"
                f"📊 *Current Status:*\n"
                f"• Inactive users \\(\\>7 days\\): `{inactive_users}`\n"
                f"• TTS cache files: `{cache_files}`\n"
                f"• TTS cache size: `{cache_size_mb:.2f} MB`\n\n"
                "⚠️ *Warning:* Cleanup operations are irreversible\\!\n"
                "Select an option below:"
            )
            keyboard = await build_admin_cleanup_keyboard()
            try:
                await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="MarkdownV2")
                await callback.answer("🧹 Cleanup menu")
            except Exception as e:
                if "message is not modified" in str(e):
                    await callback.answer("🧹 Cleanup menu already open")
                else:
                    raise

        else:
            cleanup_action = action_parts[2]

            if cleanup_action == "users":
                audit_logger.info(f"ADMIN_ACTION: Admin {user_id} initiated inactive users cleanup")
                try:
                    deleted_count = await db.delete_inactive_users(days=7)
                    text = (
                        f"✅ *Cleanup Complete*\n\n"
                        f"Deleted `{deleted_count}` inactive users \\(\\>7 days\\)\\.\n\n"
                        f"Database has been cleaned\\."
                    )
                    keyboard = await build_admin_cleanup_keyboard()
                    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="MarkdownV2")
                    await callback.answer(f"✅ Deleted {deleted_count} users")
                except Exception as e:
                    logger.error(f"Error during user cleanup: {e}")
                    await callback.answer("❌ Error during cleanup", show_alert=True)

            elif cleanup_action == "cache":
                audit_logger.info(f"ADMIN_ACTION: Admin {user_id} initiated TTS cache cleanup")
                try:
                    deleted_count, deleted_size = await db.clear_tts_cache(days=7)
                    text = (
                        f"✅ *Cache Cleanup Complete*\n\n"
                        f"Deleted `{deleted_count}` cache files\n"
                        f"Freed `{deleted_size:.2f} MB` of disk space\\.\n\n"
                        f"Cache has been cleaned\\."
                    )
                    keyboard = await build_admin_cleanup_keyboard()
                    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="MarkdownV2")
                    await callback.answer(f"✅ Freed {deleted_size:.2f} MB")
                except Exception as e:
                    logger.error(f"Error during cache cleanup: {e}")
                    await callback.answer("❌ Error during cleanup", show_alert=True)

            elif cleanup_action == "all":
                audit_logger.info(f"ADMIN_ACTION: Admin {user_id} initiated full cleanup")
                try:
                    deleted_users = await db.delete_inactive_users(days=7)
                    deleted_files, deleted_size = await db.clear_tts_cache(days=7)
                    text = (
                        f"✅ *Full Cleanup Complete*\n\n"
                        f"📊 *Results:*\n"
                        f"• Deleted users: `{deleted_users}`\n"
                        f"• Deleted cache files: `{deleted_files}`\n"
                        f"• Freed space: `{deleted_size:.2f} MB`\n\n"
                        f"System has been fully cleaned\\!"
                    )
                    keyboard = await build_admin_cleanup_keyboard()
                    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="MarkdownV2")
                    await callback.answer(f"✅ Full cleanup complete")
                except Exception as e:
                    logger.error(f"Error during full cleanup: {e}")
                    await callback.answer("❌ Error during cleanup", show_alert=True)

    elif action == "server" and len(action_parts) > 2 and action_parts[2] == "status":
        audit_logger.info(f"ADMIN_ACTION: Admin {user_id} requested server status")

        try:
            status_text = await format_server_status()
            # Create back button
            from ..utils.keyboards import InlineKeyboardButton, InlineKeyboardMarkup
            back_button = InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="🔄 Refresh", callback_data="admin_server_status"),
                InlineKeyboardButton(text="🔙 Back", callback_data="admin_refresh"),
            ]])

            await callback.message.edit_text(
                status_text,
                reply_markup=back_button,
                parse_mode="MarkdownV2"
            )
            await callback.answer("📊 Server status loaded")
        except Exception as e:
            if "message is not modified" in str(e):
                await callback.answer("✅ Already up to date")
            else:
                logger.error(f"Error getting server status: {e}")
                await callback.answer("❌ Error loading server status", show_alert=True)

    elif action in ["enable", "disable"]:
        target_user_id = int(action_parts[2])
        disabled = action == "disable"

        # Update user status
        success = await set_user_disabled(target_user_id, disabled)
        action_text = "disabled" if disabled else "enabled"

        audit_logger.info(f"ADMIN_ACTION: Admin {user_id} {action_text} user {target_user_id}")

        # Refresh user management screen
        text = await format_users_list()
        keyboard = await build_admin_users_keyboard()
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="MarkdownV2")
        await callback.answer(f"✅ User {target_user_id} {action_text}")

    elif action == "model" and len(action_parts) > 2 and action_parts[2] == "select":
        # Show model selection menu
        audit_logger.info(f"ADMIN_ACTION: Admin {user_id} opened model selection")
        from ..services.model_manager import get_model_manager

        model_manager = get_model_manager()
        current_model = model_manager.get_current_model()
        model_info = model_manager.get_model_info(current_model)

        text = (
            f"🤖 *Translation Model Selection*\n\n"
            f"*Current Model:* `{model_info.get('name', current_model)}`\n"
            f"*Description:* {model_info.get('description', 'N/A')}\n\n"
            f"Select a model below to switch:"
        )

        keyboard = await build_admin_model_select_keyboard()
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")
        await callback.answer("🤖 Model selection")

    elif action == "set" and len(action_parts) > 2 and action_parts[2] == "model":
        # Set new model
        if len(action_parts) < 4:
            await callback.answer("❌ Invalid model selection")
            return

        new_model = action_parts[3]
        from ..services.model_manager import get_model_manager

        model_manager = get_model_manager()
        success = model_manager.set_model(new_model)

        if success:
            model_info = model_manager.get_model_info(new_model)
            audit_logger.info(f"ADMIN_ACTION: Admin {user_id} changed model to {new_model}")

            text = (
                f"✅ *Model Changed Successfully*\n\n"
                f"*New Model:* `{model_info.get('name', new_model)}`\n"
                f"*Description:* {model_info.get('description', 'N/A')}\n\n"
                f"All new translations will use this model\\."
            )

            keyboard = await build_admin_model_select_keyboard()
            await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="MarkdownV2")
            await callback.answer(f"✅ Switched to {model_info.get('name', new_model)}")
        else:
            await callback.answer("❌ Invalid model", show_alert=True)
