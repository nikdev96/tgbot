"""
Centralized cache management for translations and TTS
"""
import hashlib
import logging
import shutil
from pathlib import Path
from typing import Optional
from cachetools import TTLCache

logger = logging.getLogger(__name__)

# Global caches
translation_cache = TTLCache(maxsize=1000, ttl=3600)  # 1 hour
tts_cache = TTLCache(maxsize=500, ttl=1800)  # 30 minutes


class PersistentTTSCache:
    """Persistent file-based TTS cache"""

    def __init__(self, cache_dir: Optional[Path] = None):
        if cache_dir is None:
            # Use data directory relative to project root
            from .config import get_config
            config = get_config()
            cache_dir = Path(config.database.path).parent / "cache" / "tts"

        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _get_cache_key(self, text: str) -> str:
        """Generate cache key for text"""
        return hashlib.md5(text.encode()).hexdigest()

    def _get_cache_path(self, cache_key: str) -> Path:
        """Get file path for cache key"""
        return self.cache_dir / f"tts_{cache_key}.ogg"

    def get(self, text: str) -> Optional[Path]:
        """Get cached TTS file path"""
        cache_key = self._get_cache_key(text)
        cache_path = self._get_cache_path(cache_key)

        if cache_path.exists():
            logger.info(f"TTS cache hit for: {text[:50]}...")
            return cache_path
        return None

    def set(self, text: str, audio_data: bytes) -> Path:
        """Save audio data to cache"""
        cache_key = self._get_cache_key(text)
        cache_path = self._get_cache_path(cache_key)

        with open(cache_path, "wb") as f:
            f.write(audio_data)

        logger.info(f"TTS cached for: {text[:50]}...")
        return cache_path

    def cleanup_old_files(self, max_age_hours: int = 48):
        """Clean up old cache files"""
        import time
        cutoff_time = time.time() - (max_age_hours * 3600)

        for cache_file in self.cache_dir.glob("tts_*.ogg"):
            if cache_file.stat().st_mtime < cutoff_time:
                cache_file.unlink()
                logger.debug(f"Cleaned up old TTS cache: {cache_file}")


# Global persistent TTS cache instance (lazy initialization)
_persistent_tts_cache = None


def get_translation_cache() -> TTLCache:
    """Get translation cache instance"""
    return translation_cache


def get_tts_cache() -> TTLCache:
    """Get TTS memory cache instance"""
    return tts_cache


def get_persistent_tts_cache() -> PersistentTTSCache:
    """Get persistent TTS cache instance"""
    global _persistent_tts_cache
    if _persistent_tts_cache is None:
        _persistent_tts_cache = PersistentTTSCache()
    return _persistent_tts_cache