"""
User check middleware to verify user access
"""
import logging
from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery, TelegramObject

logger = logging.getLogger(__name__)
audit_logger = logging.getLogger("audit")


class UserCheckMiddleware(BaseMiddleware):
    """
    Middleware to check if user is disabled before processing any requests.
    This reduces code duplication across all handlers.
    """

    def __init__(self):
        super().__init__()
        logger.info("User check middleware initialized")

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        """Process middleware"""
        # Import here to avoid circular imports
        from ..services.analytics import is_user_disabled

        # Extract user_id and message/callback from event
        user_id = None
        response_target = None

        if isinstance(event, Message):
            user_id = event.from_user.id
            response_target = event
        elif isinstance(event, CallbackQuery):
            user_id = event.from_user.id
            response_target = event.message

        # If we can't determine user_id, skip check
        if user_id is None:
            return await handler(event, data)

        # Check if user is disabled
        if await is_user_disabled(user_id):
            # Log blocked access attempt
            event_type = type(event).__name__
            audit_logger.warning(
                f"BLOCKED_ACCESS: Disabled user {user_id} attempted {event_type}"
            )

            # Send error message
            error_message = "❌ Access disabled. Contact support if you believe this is an error."

            if isinstance(event, Message):
                await event.reply(error_message)
            elif isinstance(event, CallbackQuery):
                await event.answer(error_message, show_alert=True)

            # Do not continue processing
            return

        # User is not disabled, continue processing
        return await handler(event, data)
