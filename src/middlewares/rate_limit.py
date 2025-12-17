"""
Rate limiting middleware to prevent spam
"""
import logging
from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import Message, TelegramObject
from cachetools import TTLCache

from ..core.constants import ADMIN_IDS
from ..core.config import get_config

logger = logging.getLogger(__name__)


class RateLimitMiddleware(BaseMiddleware):
    """
    Middleware to limit the number of messages per user per time window.
    Admins can bypass rate limiting if configured.
    """

    def __init__(self):
        super().__init__()
        self.config = get_config()

        # Cache for tracking message counts per user
        # Key: user_id, Value: message count
        # TTL matches the rate limit window (60 seconds for messages_per_minute)
        self.cache = TTLCache(maxsize=10000, ttl=60)

        # Separate cache for voice messages (1 hour TTL)
        self.voice_cache = TTLCache(maxsize=10000, ttl=3600)

        self.enabled = self.config.rate_limits.enabled
        self.messages_per_minute = self.config.rate_limits.messages_per_minute
        self.voice_messages_per_hour = self.config.rate_limits.voice_messages_per_hour
        self.admin_bypass = self.config.rate_limits.admin_bypass

        logger.info(
            f"Rate limiting initialized: "
            f"enabled={self.enabled}, "
            f"messages_per_minute={self.messages_per_minute}, "
            f"voice_per_hour={self.voice_messages_per_hour}, "
            f"admin_bypass={self.admin_bypass}"
        )

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        """Process middleware"""
        # Only process messages
        if not isinstance(event, Message):
            return await handler(event, data)

        # Skip if rate limiting is disabled
        if not self.enabled:
            return await handler(event, data)

        message: Message = event
        user_id = message.from_user.id

        # Bypass rate limiting for admins if configured
        if self.admin_bypass and user_id in ADMIN_IDS:
            logger.debug(f"Rate limit bypassed for admin user {user_id}")
            return await handler(event, data)

        # Check if message is voice/audio
        is_voice = message.voice is not None or message.audio is not None

        if is_voice:
            # Check voice message rate limit
            voice_count = self.voice_cache.get(user_id, 0)

            if voice_count >= self.voice_messages_per_hour:
                logger.warning(
                    f"Voice rate limit exceeded for user {user_id}: "
                    f"{voice_count}/{self.voice_messages_per_hour}"
                )
                await message.reply(
                    f"⚠️ Too many voice messages. "
                    f"Limit: {self.voice_messages_per_hour} per hour.\n"
                    f"Please wait before sending more voice messages."
                )
                return

            # Increment voice counter
            self.voice_cache[user_id] = voice_count + 1
            logger.debug(f"Voice message count for user {user_id}: {voice_count + 1}/{self.voice_messages_per_hour}")

        # Check regular message rate limit
        message_count = self.cache.get(user_id, 0)

        if message_count >= self.messages_per_minute:
            logger.warning(
                f"Message rate limit exceeded for user {user_id}: "
                f"{message_count}/{self.messages_per_minute}"
            )
            await message.reply(
                f"⚠️ Too many messages. "
                f"Limit: {self.messages_per_minute} per minute.\n"
                f"Please slow down."
            )
            return

        # Increment message counter
        self.cache[user_id] = message_count + 1
        logger.debug(f"Message count for user {user_id}: {message_count + 1}/{self.messages_per_minute}")

        # Continue processing
        return await handler(event, data)
