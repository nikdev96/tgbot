"""
Centralized cache management for translations and TTS

Features:
- Translation cache: LRU with 24h TTL, 2000 entries
- TTS cache: Persistent file-based with automatic cleanup
- Text normalization for better cache hit rates
- Thread-safe statistics tracking
"""
import hashlib
import logging
import shutil
import threading
import unicodedata
from pathlib import Path
from typing import Optional, Dict, Any
from cachetools import TTLCache

logger = logging.getLogger(__name__)

# Global caches with improved settings
# Translation cache: 24 hours TTL, 2000 entries (increased from 1000)
translation_cache = TTLCache(maxsize=2000, ttl=86400)  # 24 hours
tts_cache = TTLCache(maxsize=500, ttl=3600)  # 1 hour

# Thread lock for cache statistics
_stats_lock = threading.Lock()

# Cache statistics for monitoring
cache_stats: Dict[str, int] = {
    "translation_hits": 0,
    "translation_misses": 0,
    "tts_hits": 0,
    "tts_misses": 0
}


def normalize_text_for_cache(text: str) -> str:
    """Normalize text for cache key generation.

    Improves cache hit rate by normalizing:
    - Whitespace (collapse multiple spaces, strip)
    - Unicode normalization (NFC form)
    - Case-insensitive matching disabled (preserves meaning)

    Args:
        text: Original text

    Returns:
        Normalized text for cache key
    """
    # Strip and normalize whitespace
    text = ' '.join(text.split())
    # Unicode normalization (NFC - canonical decomposition followed by canonical composition)
    text = unicodedata.normalize('NFC', text)
    return text


def get_cache_stats() -> Dict[str, Any]:
    """Get cache statistics for monitoring (thread-safe).

    Returns:
        Dictionary with cache stats including hit rates
    """
    with _stats_lock:
        total_translation = cache_stats["translation_hits"] + cache_stats["translation_misses"]
        total_tts = cache_stats["tts_hits"] + cache_stats["tts_misses"]

        return {
            "translation": {
                "hits": cache_stats["translation_hits"],
                "misses": cache_stats["translation_misses"],
                "hit_rate": cache_stats["translation_hits"] / total_translation if total_translation > 0 else 0,
                "size": len(translation_cache),
                "maxsize": translation_cache.maxsize,
                "ttl": translation_cache.ttl
            },
            "tts": {
                "hits": cache_stats["tts_hits"],
                "misses": cache_stats["tts_misses"],
                "hit_rate": cache_stats["tts_hits"] / total_tts if total_tts > 0 else 0,
                "size": len(tts_cache),
                "maxsize": tts_cache.maxsize
            }
        }


def increment_cache_stat(cache_type: str, hit: bool):
    """Increment cache statistics counter (thread-safe).

    Args:
        cache_type: "translation" or "tts"
        hit: True for cache hit, False for miss
    """
    key = f"{cache_type}_{'hits' if hit else 'misses'}"
    with _stats_lock:
        if key in cache_stats:
            cache_stats[key] += 1


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
        """Generate cache key from text + current voice + model so changing
        TTS settings produces new cache entries instead of serving stale audio."""
        from .config import get_config
        cfg = get_config()
        key = f"{text}:{cfg.tts.voice}:{cfg.tts.model}"
        return hashlib.md5(key.encode()).hexdigest()

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


def clear_all_caches():
    """Clear all in-memory caches (for admin/maintenance)"""
    translation_cache.clear()
    tts_cache.clear()
    # Use .clear() to reset stats while keeping the same dict reference
    # This prevents race conditions with other threads holding old references
    with _stats_lock:
        cache_stats.clear()
        cache_stats.update({
            "translation_hits": 0,
            "translation_misses": 0,
            "tts_hits": 0,
            "tts_misses": 0
        })
    logger.info("All in-memory caches cleared")