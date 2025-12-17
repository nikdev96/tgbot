"""
Core constants for the translation bot
"""
import os
from typing import Set, Dict

# Supported languages with metadata
SUPPORTED_LANGUAGES: Dict[str, Dict[str, str]] = {
    "ru": {"name": "Russian", "flag": "🇷🇺"},
    "en": {"name": "English", "flag": "🇺🇸"},
    "th": {"name": "Thai", "flag": "🇹🇭"},
    "ar": {"name": "Arabic", "flag": "🇸🇦"},
    "zh": {"name": "Chinese", "flag": "🇨🇳"},
    "vi": {"name": "Vietnamese", "flag": "🇻🇳"}
}

# Default languages for new users
DEFAULT_LANGUAGES: Set[str] = {"ru", "en", "th"}

# Load ADMIN_IDS from environment
ADMIN_USER_ID = os.getenv("ADMIN_USER_ID")
if ADMIN_USER_ID:
    ADMIN_IDS: Set[int] = {int(uid.strip()) for uid in ADMIN_USER_ID.split(',') if uid.strip().isdigit()}
else:
    ADMIN_IDS = set()