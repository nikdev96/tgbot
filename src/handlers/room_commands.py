"""
Room command handlers for creating and managing translation rooms
"""
import logging
from aiogram import F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command

from ..core.app import audit_logger
from ..services.analytics import is_user_disabled, update_user_activity, get_user_preferences
from ..services.room_manager import RoomManager
from ..services.language import detect_language
from ..utils.room_keyboards import (
    build_rooms_main_menu,
    build_room_info_keyboard,
    build_members_list_keyboard
)

logger = logging.getLogger(__name__)


def register_handlers(dp):
    """Register room command handlers"""
    dp.message.register(room_command, Command("room"))
    dp.callback_query.register(room_callback, F.data.startswith("room_"))


async def room_command(message: Message):
    """Handle /room command - main rooms menu"""
    user_id = message.from_user.id

    # Check if user is disabled
    if await is_user_disabled(user_id):
        audit_logger.warning(f"BLOCKED_ACCESS: Disabled user {user_id} attempted /room")
        await message.reply("❌ Access disabled")
        return

    # Update activity
    await update_user_activity(user_id, message.from_user)

    # Check if user has active room
    active_room = await RoomManager.get_active_room(user_id)

    if active_room:
        # Show room info if already in room
        members = await RoomManager.get_room_members(active_room.id)

        text = (
            f"🏠 *Room: {active_room.code}*\n\n"
            f"👥 Members: {len(members)}/{active_room.max_members}\n"
            f"⏰ Expires: {active_room.expires_at.strftime('%Y-%m-%d %H:%M') if active_room.expires_at else 'Never'}\n\n"
            f"💬 Send messages here and they'll be translated for all members!"
        )
        keyboard = build_room_info_keyboard(active_room, user_id)
        await message.reply(text, parse_mode="Markdown", reply_markup=keyboard)
    else:
        # Show main menu
        text = (
            "🏠 *Translation Rooms*\n\n"
            "Create or join a room to have real-time translated conversations!\n\n"
            "*Features:*\n"
            "• Everyone writes in their language\n"
            "• Messages auto-translated for others\n"
            "• Your original text stays with you\n"
            "• Support for 2-10 participants"
        )
        keyboard = build_rooms_main_menu()
        await message.reply(text, parse_mode="Markdown", reply_markup=keyboard)


async def room_callback(callback: CallbackQuery):
    """Handle room-related callbacks"""
    user_id = callback.from_user.id
    action = callback.data.split("_", 1)[1]

    # Check if user is disabled
    if await is_user_disabled(user_id):
        await callback.answer("❌ Access disabled", show_alert=True)
        return

    # Update activity
    await update_user_activity(user_id, callback.from_user)

    if action == "create":
        # Create a new room
        await handle_create_room(callback)

    elif action == "join":
        # Show join instructions
        text = (
            "🔑 *Join Room*\n\n"
            "To join a room, send the command:\n"
            "`/room join CODE`\n\n"
            "Example: `/room join ABC123`\n\n"
            "Ask the room creator to share their room code with you!"
        )
        await callback.message.edit_text(text, parse_mode="Markdown")
        await callback.answer()

    elif action == "leave":
        # Leave current room
        success, msg = await RoomManager.leave_room(user_id)
        if success:
            text = (
                "👋 *Left Room*\n\n"
                "You have left the room.\n"
                "Use /room to create or join another room."
            )
            await callback.message.edit_text(text, parse_mode="Markdown")
            audit_logger.info(f"ROOM_ACTION: User {user_id} left room")
        else:
            await callback.message.edit_text(msg, parse_mode="Markdown")
        await callback.answer(msg)

    elif action == "close":
        # Close room (creator only)
        active_room = await RoomManager.get_active_room(user_id)
        if not active_room:
            await callback.answer("❌ Not in any room", show_alert=True)
            return

        success, msg = await RoomManager.close_room(active_room.id, user_id)
        if success:
            text = (
                f"🔒 *Room Closed*\n\n"
                f"Room {active_room.code} has been closed.\n"
                f"All members have been notified."
            )
            await callback.message.edit_text(text, parse_mode="Markdown")

            # Notify all members
            members = await RoomManager.get_room_members(active_room.id)
            for member in members:
                if member.user_id != user_id:
                    try:
                        from ..core.app import bot
                        await bot.send_message(
                            member.user_id,
                            f"🔒 Room {active_room.code} has been closed by the creator."
                        )
                    except Exception as e:
                        logger.error(f"Error notifying user {member.user_id}: {e}")

            audit_logger.info(f"ROOM_ACTION: User {user_id} closed room {active_room.code}")
        else:
            await callback.message.edit_text(msg, parse_mode="Markdown")
        await callback.answer(msg)

    elif action == "members":
        # Show members list
        active_room = await RoomManager.get_active_room(user_id)
        if not active_room:
            await callback.answer("❌ Not in any room", show_alert=True)
            return

        members = await RoomManager.get_room_members(active_room.id)
        if not members:
            await callback.answer("❌ No members found", show_alert=True)
            return

        from ..core.constants import SUPPORTED_LANGUAGES

        text = f"👥 *Room {active_room.code} - Members*\n\n"
        for member in members:
            lang_info = SUPPORTED_LANGUAGES.get(member.language_code, {})
            flag = lang_info.get('flag', '🏳️')
            role = "👑" if member.is_creator() else "👤"
            text += f"{role} {flag} {member.display_name()}\n"

        keyboard = build_members_list_keyboard(active_room)
        await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=keyboard)
        await callback.answer()

    elif action == "info":
        # Show room info
        active_room = await RoomManager.get_active_room(user_id)
        if not active_room:
            await callback.answer("❌ Not in any room", show_alert=True)
            return

        members = await RoomManager.get_room_members(active_room.id)

        text = (
            f"🏠 *Room: {active_room.code}*\n\n"
            f"👥 Members: {len(members)}/{active_room.max_members}\n"
            f"⏰ Expires: {active_room.expires_at.strftime('%Y-%m-%d %H:%M') if active_room.expires_at else 'Never'}\n\n"
            f"💬 Send messages and they'll be translated!"
        )
        keyboard = build_room_info_keyboard(active_room, user_id)
        try:
            await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=keyboard)
        except Exception as e:
            if "message is not modified" in str(e):
                pass
            else:
                raise
        await callback.answer()


async def handle_create_room(callback: CallbackQuery):
    """Handle room creation"""
    user_id = callback.from_user.id

    # Check if user already in room
    active_room = await RoomManager.get_active_room(user_id)
    if active_room:
        await callback.answer(f"❌ Already in room {active_room.code}", show_alert=True)
        return

    # Get user's preferred language
    prefs = await get_user_preferences(user_id)
    user_lang = next(iter(prefs)) if prefs else 'en'

    # Create room
    try:
        code = await RoomManager.create_room(user_id, user_lang)

        text = (
            f"✅ *Room Created!*\n\n"
            f"🔑 Room Code: `{code}`\n"
            f"🗣️ Your Language: {user_lang.upper()}\n\n"
            f"*Share this code with others:*\n"
            f"`/room join {code}`\n\n"
            f"💬 Start sending messages!\n"
            f"They'll be auto-translated for all members."
        )

        room = await RoomManager.get_active_room(user_id)
        keyboard = build_room_info_keyboard(room, user_id)

        await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=keyboard)
        audit_logger.info(f"ROOM_ACTION: User {user_id} created room {code}")
        await callback.answer(f"✅ Room {code} created!")

    except Exception as e:
        logger.error(f"Error creating room: {e}")
        await callback.answer("❌ Error creating room", show_alert=True)


async def handle_join_command(message: Message, code: str):
    """
    Handle /room join CODE command

    This is called from the main message handler when it detects 'room join' pattern
    """
    user_id = message.from_user.id

    # Check if user is disabled
    if await is_user_disabled(user_id):
        await message.reply("❌ Access disabled")
        return

    # Update activity
    await update_user_activity(user_id, message.from_user)

    # Get user's preferred language
    prefs = await get_user_preferences(user_id)
    user_lang = next(iter(prefs)) if prefs else 'en'

    # Join room
    success, msg = await RoomManager.join_room(code.upper(), user_id, user_lang)

    if success:
        active_room = await RoomManager.get_active_room(user_id)
        members = await RoomManager.get_room_members(active_room.id)

        text = (
            f"✅ *Joined Room {code.upper()}!*\n\n"
            f"👥 Members: {len(members)}/{active_room.max_members}\n"
            f"🗣️ Your Language: {user_lang.upper()}\n\n"
            f"💬 Start sending messages!\n"
            f"Your messages will be translated to other members' languages."
        )

        keyboard = build_room_info_keyboard(active_room, user_id)
        await message.reply(text, parse_mode="Markdown", reply_markup=keyboard)

        # Notify other members
        for member in members:
            if member.user_id != user_id:
                try:
                    from ..core.app import bot
                    user_name = message.from_user.username or message.from_user.first_name or f"User {user_id}"
                    await bot.send_message(
                        member.user_id,
                        f"👋 {user_name} joined the room!"
                    )
                except Exception as e:
                    logger.error(f"Error notifying member {member.user_id}: {e}")

        audit_logger.info(f"ROOM_ACTION: User {user_id} joined room {code}")
    else:
        await message.reply(msg)
