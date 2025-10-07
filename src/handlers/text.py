"""
Text message handlers
"""
import logging
from aiogram import F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from ..services.analytics import is_user_disabled, update_user_activity
from ..services.translation import process_translation
from ..core.app import audit_logger

logger = logging.getLogger(__name__)


def register_handlers(dp):
    """Register text handlers"""
    dp.message.register(text_handler, F.text)


async def text_handler(message: Message, state: FSMContext):
    """Handle text translation"""
    user_id = message.from_user.id
    text = message.text.strip()

    # Check if user is disabled
    if await is_user_disabled(user_id):
        audit_logger.warning(f"BLOCKED_ACCESS: Disabled user {user_id} attempted text message: {text[:50]}...")
        await message.reply(
            "❌ Access disabled. Contact support if you believe this is an error."
        )
        return

    if not text:
        await message.reply("Please send a non-empty message.")
        return

    # Check for /room join CODE command
    if text.lower().startswith("/room join "):
        from .room_commands import handle_join_command
        code = text.split(maxsplit=2)[2] if len(text.split()) >= 3 else ""
        if code:
            await handle_join_command(message, code, state)
            return
        else:
            await message.reply("❌ Укажите код комнаты: `/room join КОД`", parse_mode="Markdown")
            return

    # Check if user is in an active room
    from ..services.room_manager import RoomManager
    active_room = await RoomManager.get_active_room(user_id)
    if active_room:
        # Handle as room message
        await RoomManager.handle_room_message(message, active_room)
        return

    await process_translation(message, text, source_type="text")