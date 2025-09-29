"""
Text message handlers
"""
import logging
from aiogram import F
from aiogram.types import Message
from ..services.analytics import is_user_disabled, update_user_activity
from ..services.translation import process_translation
from ..core.app import audit_logger

logger = logging.getLogger(__name__)


def register_handlers(dp):
    """Register text handlers"""
    dp.message.register(text_handler, F.text)


async def text_handler(message: Message):
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

    await process_translation(message, text, source_type="text")