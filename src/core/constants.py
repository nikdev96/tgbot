"""
Core constants for the translation bot
"""
import os
import logging
from typing import Final, Set, Dict, TypedDict

logger = logging.getLogger(__name__)


class LanguageMetadata(TypedDict):
    """Language metadata type"""
    name: str
    flag: str


# Supported languages with metadata
SUPPORTED_LANGUAGES: Final[Dict[str, LanguageMetadata]] = {
    "ru": {"name": "Russian", "flag": "🇷🇺"},
    "en": {"name": "English", "flag": "🇺🇸"},
    "th": {"name": "Thai", "flag": "🇹🇭"},
    "ar": {"name": "Arabic", "flag": "🇸🇦"},
    "zh": {"name": "Chinese", "flag": "🇨🇳"},
    "vi": {"name": "Vietnamese", "flag": "🇻🇳"}
}

# Default languages for new users
DEFAULT_LANGUAGES: Final[Set[str]] = {"ru", "en", "th"}

# Load ADMIN_IDS from environment with validation
ADMIN_USER_ID = os.getenv("ADMIN_USER_ID")
if ADMIN_USER_ID:
    try:
        ADMIN_IDS: Set[int] = {
            int(uid.strip())
            for uid in ADMIN_USER_ID.split(',')
            if uid.strip().isdigit()
        }
        logger.info(f"Loaded {len(ADMIN_IDS)} admin user(s)")
    except ValueError as e:
        logger.error(f"Error parsing ADMIN_USER_ID: {e}")
        ADMIN_IDS = set()
else:
    logger.warning("No ADMIN_USER_ID configured")
    ADMIN_IDS = set()