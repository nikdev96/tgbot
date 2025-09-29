"""
User analytics and management service
"""
import logging
from datetime import datetime
from typing import Dict, Set, Optional
from aiogram.types import User
from ..core.constants import ADMIN_IDS, SUPPORTED_LANGUAGES
from ..core.app import db

logger = logging.getLogger(__name__)
audit_logger = logging.getLogger("audit")


async def get_user_analytics(user_id: int, user: Optional[User] = None) -> Dict:
    """Get or create user analytics entry from database"""
    user_profile = None
    if user:
        user_profile = {
            "username": user.username,
            "first_name": user.first_name,
            "last_name": user.last_name,
        }
    return await db.get_user_analytics(user_id, user_profile)


async def update_user_activity(user_id: int, user: Optional[User] = None):
    """Update user activity timestamp and message count atomically"""
    user_profile = None
    if user:
        user_profile = {
            "username": user.username,
            "first_name": user.first_name,
            "last_name": user.last_name,
        }

    # Use atomic operation to prevent race conditions
    await db.increment_message_count(user_id, user_profile)


def is_admin(user_id: int) -> bool:
    """Check if user is admin"""
    return user_id in ADMIN_IDS


async def is_user_disabled(user_id: int) -> bool:
    """Check if user is disabled"""
    analytics = await get_user_analytics(user_id)
    return analytics["is_disabled"]


async def set_user_disabled(user_id: int, disabled: bool) -> bool:
    """Enable/disable user access atomically"""
    action = "disabled" if disabled else "enabled"
    audit_logger.info(f"ADMIN_ACTION: User {user_id} has been {action}")

    # Use atomic operation to prevent race conditions
    return await db.set_user_disabled(user_id, disabled)


async def is_voice_replies_enabled(user_id: int) -> bool:
    """Check if user has voice replies enabled"""
    analytics = await get_user_analytics(user_id)
    return analytics["voice_replies_enabled"]


async def toggle_voice_replies(user_id: int) -> bool:
    """Toggle voice replies preference for user atomically"""
    # Use atomic operation to prevent race conditions
    enabled = await db.toggle_voice_replies(user_id)
    logger.info(f"User {user_id} voice replies {'enabled' if enabled else 'disabled'}")
    return enabled


async def increment_voice_responses(user_id: int):
    """Increment voice response counter atomically"""
    # Use atomic operation to prevent race conditions
    await db.increment_voice_responses(user_id)


async def get_user_preferences(user_id: int) -> Set[str]:
    """Get user's enabled translation languages from database"""
    return await db.get_user_preferences(user_id)


async def update_user_preference(user_id: int, lang_code: str) -> Set[str]:
    """Toggle language preference for user atomically"""
    # Use atomic operation to prevent race conditions
    return await db.toggle_language_preference(user_id, lang_code)