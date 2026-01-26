"""
Reaction handler for 🌐 emoji translations
"""
import logging
from aiogram import Bot
from aiogram.types import MessageReactionUpdated, ReactionTypeEmoji

from ..core.app import bot
from ..core.constants import SUPPORTED_LANGUAGES
from ..services.language import detect_language
from ..services.analytics import get_user_preferences, is_user_disabled
from ..services.translation import translate_text

logger = logging.getLogger(__name__)

# Globe emoji for translation trigger
TRANSLATE_EMOJI = "🌐"


def register_handlers(dp):
    """Register reaction handlers"""
    dp.message_reaction.register(reaction_handler)


async def reaction_handler(reaction: MessageReactionUpdated):
    """Handle message reactions - translate on 🌐 emoji"""
    user_id = reaction.user.id if reaction.user else None

    if not user_id:
        return

    # Check if user is disabled
    if await is_user_disabled(user_id):
        return

    # Check if 🌐 was added in new reactions
    translate_requested = False
    for r in reaction.new_reaction:
        if isinstance(r, ReactionTypeEmoji) and r.emoji == TRANSLATE_EMOJI:
            translate_requested = True
            break

    if not translate_requested:
        return

    # Get the original message to translate
    # Note: We need to get the message from the chat history
    # This requires bot to have access to messages (admin in groups, or message cached)
    try:
        chat_id = reaction.chat.id
        message_id = reaction.message_id

        # Try to get message text from the chat
        # Unfortunately, Telegram doesn't provide message content in reaction updates
        # We need to fetch it via the API if we have permission

        # For groups where bot is admin, we can use getMessages
        # For now, we'll try to reply to the message explaining the limitation
        # or use a cached message store

        # Note: This feature works best when:
        # 1. Bot is admin in the group
        # 2. Bot has message history access
        # 3. Message was recently sent and might be in cache

        # Since we can't reliably get message content from reactions,
        # we'll send a helpful message instead
        await bot.send_message(
            chat_id=chat_id,
            reply_to_message_id=message_id,
            text=(
                "🌐 To translate this message, please:\n"
                "• Reply to the message and send text to translate, or\n"
                "• Forward the message to me in private chat\n\n"
                "_Reaction-based translation requires message history access._"
            ),
            parse_mode="Markdown"
        )

        logger.info(f"Reaction translation requested by user {user_id} in chat {chat_id}")

    except Exception as e:
        logger.error(f"Error handling reaction translation: {e}")
