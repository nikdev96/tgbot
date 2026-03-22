"""
Text message handlers
"""
import logging
from aiogram import F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from ..services.analytics import is_user_disabled, update_user_activity
from ..services.translation import process_translation
from ..core.app import audit_logger, bot, get_bot_info

logger = logging.getLogger(__name__)


def register_handlers(dp):
    """Register text handlers"""
    dp.message.register(text_handler, F.text)


def is_reply_to_bot(message: Message, bot_id: int) -> bool:
    """Check if message is a reply to bot's message"""
    if message.reply_to_message:
        return message.reply_to_message.from_user and message.reply_to_message.from_user.id == bot_id
    return False


def get_bot_username(message: Message) -> str:
    """Get bot username from message context"""
    # This will be set after bot starts
    return getattr(bot, '_username', None)


def extract_text_after_mention(message: Message, bot_username: str) -> str:
    """Extract text after @botname mention"""
    if not bot_username:
        return message.text

    text = message.text.strip()
    mention = f"@{bot_username}"

    if text.lower().startswith(mention.lower()):
        return text[len(mention):].strip()

    # Check for mention entity
    if message.entities:
        for entity in message.entities:
            if entity.type == "mention":
                mention_text = text[entity.offset:entity.offset + entity.length]
                if mention_text.lower() == mention.lower():
                    # Return text after the mention
                    return text[entity.offset + entity.length:].strip()

    return text


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

    # Handle group chats
    if message.chat.type in ["group", "supergroup"]:
        bot_info = await get_bot_info()
        bot_id = bot_info.id
        bot_username = bot_info.username

        # Option 1: Reply to bot's message
        if is_reply_to_bot(message, bot_id):
            await process_translation(message, text, source_type="text")
            return

        # Option 2: Message starts with @botname
        if bot_username and f"@{bot_username.lower()}" in text.lower():
            extracted_text = extract_text_after_mention(message, bot_username)
            if extracted_text:
                await process_translation(message, extracted_text, source_type="text")
            return

        # Ignore other messages in groups (don't translate everything)
        return

    # Check if user is in an active room (private chats only)
    from ..services.room_manager import RoomManager
    active_room = await RoomManager.get_active_room(user_id)
    if active_room:
        # Handle as room message
        await RoomManager.handle_room_message(message, active_room)
        return

    await process_translation(message, text, source_type="text")