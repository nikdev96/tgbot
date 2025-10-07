"""
Database manager for persistent storage
"""
import asyncio
import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Set, List
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)

class DatabaseManager:
    """SQLite database manager for user data persistence"""

    def __init__(self, db_path: str = "data/translator_bot.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(exist_ok=True)

    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection with proper settings"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    async def init_db(self):
        """Initialize database with required tables"""
        conn = self._get_connection()
        try:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    last_name TEXT,
                    is_disabled BOOLEAN DEFAULT FALSE,
                    voice_replies_enabled BOOLEAN DEFAULT FALSE,
                    message_count INTEGER DEFAULT 0,
                    voice_responses_sent INTEGER DEFAULT 0,
                    last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS user_language_preferences (
                    user_id INTEGER,
                    language_code TEXT,
                    PRIMARY KEY (user_id, language_code),
                    FOREIGN KEY (user_id) REFERENCES users(id)
                );

                CREATE INDEX IF NOT EXISTS idx_users_last_activity ON users(last_activity);
                CREATE INDEX IF NOT EXISTS idx_user_prefs_user_id ON user_language_preferences(user_id);
            """)
            conn.commit()
            logger.info("Database initialized successfully")
        except Exception as e:
            logger.error(f"Database initialization failed: {e}")
            raise
        finally:
            conn.close()

    async def get_user_preferences(self, user_id: int) -> Set[str]:
        """Get user's language preferences from database"""
        # Run in thread pool to avoid blocking
        return await asyncio.get_event_loop().run_in_executor(
            None, self._get_user_preferences_sync, user_id
        )

    def _get_user_preferences_sync(self, user_id: int) -> Set[str]:
        """Synchronous version of get_user_preferences"""
        conn = self._get_connection()
        try:
            cursor = conn.execute(
                "SELECT language_code FROM user_language_preferences WHERE user_id = ?",
                (user_id,)
            )
            preferences = {row["language_code"] for row in cursor.fetchall()}

            # Return default if no preferences found
            if not preferences:
                return {"ru", "en", "th", "ja", "ko", "vi"}  # Default supported languages

            return preferences
        finally:
            conn.close()

    async def update_user_preferences(self, user_id: int, preferences: Set[str]):
        """Update user's language preferences in database"""
        await asyncio.get_event_loop().run_in_executor(
            None, self._update_user_preferences_sync, user_id, preferences
        )

    def _update_user_preferences_sync(self, user_id: int, preferences: Set[str]):
        """Synchronous version of update_user_preferences"""
        conn = self._get_connection()
        try:
            # Delete existing preferences
            conn.execute(
                "DELETE FROM user_language_preferences WHERE user_id = ?",
                (user_id,)
            )

            # Insert new preferences
            for lang_code in preferences:
                conn.execute(
                    "INSERT INTO user_language_preferences (user_id, language_code) VALUES (?, ?)",
                    (user_id, lang_code)
                )

            conn.commit()
        finally:
            conn.close()

    async def get_user_analytics(self, user_id: int, user_profile: Optional[Dict] = None) -> Dict:
        """Get or create user analytics from database"""
        return await asyncio.get_event_loop().run_in_executor(
            None, self._get_user_analytics_sync, user_id, user_profile
        )

    def _get_user_analytics_sync(self, user_id: int, user_profile: Optional[Dict] = None) -> Dict:
        """Synchronous version of get_user_analytics"""
        conn = self._get_connection()
        try:
            cursor = conn.execute(
                "SELECT * FROM users WHERE id = ?",
                (user_id,)
            )
            row = cursor.fetchone()

            if row:
                # User exists, return data
                analytics = {
                    "is_disabled": bool(row["is_disabled"]),
                    "voice_replies_enabled": bool(row["voice_replies_enabled"]),
                    "message_count": row["message_count"],
                    "voice_responses_sent": row["voice_responses_sent"],
                    "last_activity": datetime.fromisoformat(row["last_activity"]),
                    "user_profile": {
                        "username": row["username"],
                        "first_name": row["first_name"],
                        "last_name": row["last_name"],
                    }
                }

                # Get preferences
                prefs_cursor = conn.execute(
                    "SELECT language_code FROM user_language_preferences WHERE user_id = ?",
                    (user_id,)
                )
                preferences = {prow["language_code"] for prow in prefs_cursor.fetchall()}
                if not preferences:
                    preferences = {"ru", "en", "th", "ja", "ko", "vi"}  # Default supported languages

                analytics["preferred_targets"] = preferences
                return analytics
            else:
                # Create new user - check if preferences already exist
                prefs_cursor = conn.execute(
                    "SELECT language_code FROM user_language_preferences WHERE user_id = ?",
                    (user_id,)
                )
                existing_preferences = {prow["language_code"] for prow in prefs_cursor.fetchall()}

                # Use existing preferences if any, otherwise default
                preferences = existing_preferences if existing_preferences else {"ru", "en", "th", "ja", "ko", "vi"}

                analytics = {
                    "is_disabled": False,
                    "voice_replies_enabled": False,
                    "message_count": 0,
                    "voice_responses_sent": 0,
                    "last_activity": datetime.now(),
                    "preferred_targets": preferences,
                    "user_profile": user_profile or {
                        "username": None,
                        "first_name": None,
                        "last_name": None,
                    }
                }

                # Insert new user
                profile = analytics["user_profile"]
                conn.execute("""
                    INSERT OR IGNORE INTO users (id, username, first_name, last_name)
                    VALUES (?, ?, ?, ?)
                """, (user_id, profile["username"], profile["first_name"], profile["last_name"]))

                # Insert default preferences only if no existing preferences
                if not existing_preferences:
                    for lang_code in preferences:
                        conn.execute(
                            "INSERT OR IGNORE INTO user_language_preferences (user_id, language_code) VALUES (?, ?)",
                            (user_id, lang_code)
                        )

                conn.commit()
                return analytics
        finally:
            conn.close()

    async def add_vietnamese_to_existing_users(self):
        """Add Vietnamese to all existing users' preferences"""
        await asyncio.get_event_loop().run_in_executor(
            None, self._add_vietnamese_to_existing_users_sync
        )

    def _add_vietnamese_to_existing_users_sync(self):
        """Synchronous version of add_vietnamese_to_existing_users"""
        conn = self._get_connection()
        try:
            # Get all users who don't have Vietnamese in their preferences
            cursor = conn.execute("""
                SELECT DISTINCT id as user_id
                FROM users
                WHERE id NOT IN (
                    SELECT user_id
                    FROM user_language_preferences
                    WHERE language_code = 'vi'
                )
            """)
            users_without_vi = [row["user_id"] for row in cursor.fetchall()]

            # Add Vietnamese to their preferences
            for user_id in users_without_vi:
                conn.execute(
                    "INSERT OR IGNORE INTO user_language_preferences (user_id, language_code) VALUES (?, ?)",
                    (user_id, "vi")
                )

            conn.commit()
            logger.info(f"Added Vietnamese to {len(users_without_vi)} existing users")

        finally:
            conn.close()

    async def update_user_analytics(self, user_id: int, analytics: Dict):
        """Update user analytics in database"""
        await asyncio.get_event_loop().run_in_executor(
            None, self._update_user_analytics_sync, user_id, analytics
        )

    def _update_user_analytics_sync(self, user_id: int, analytics: Dict):
        """Synchronous version of update_user_analytics"""
        conn = self._get_connection()
        try:
            profile = analytics["user_profile"]
            conn.execute("""
                UPDATE users SET
                    username = ?,
                    first_name = ?,
                    last_name = ?,
                    is_disabled = ?,
                    voice_replies_enabled = ?,
                    message_count = ?,
                    voice_responses_sent = ?,
                    last_activity = ?
                WHERE id = ?
            """, (
                profile["username"],
                profile["first_name"],
                profile["last_name"],
                analytics["is_disabled"],
                analytics["voice_replies_enabled"],
                analytics["message_count"],
                analytics["voice_responses_sent"],
                analytics["last_activity"].isoformat(),
                user_id
            ))

            # Update preferences if provided
            if "preferred_targets" in analytics:
                conn.execute(
                    "DELETE FROM user_language_preferences WHERE user_id = ?",
                    (user_id,)
                )
                for lang_code in analytics["preferred_targets"]:
                    conn.execute(
                        "INSERT OR IGNORE INTO user_language_preferences (user_id, language_code) VALUES (?, ?)",
                        (user_id, lang_code)
                    )

            conn.commit()
        finally:
            conn.close()

    async def get_all_users(self) -> List[Dict]:
        """Get all users with their analytics data"""
        return await asyncio.get_event_loop().run_in_executor(
            None, self._get_all_users_sync
        )

    def _get_all_users_sync(self) -> List[Dict]:
        """Synchronous version of get_all_users"""
        conn = self._get_connection()
        try:
            cursor = conn.execute("""
                SELECT u.*, GROUP_CONCAT(ulp.language_code) as preferences
                FROM users u
                LEFT JOIN user_language_preferences ulp ON u.id = ulp.user_id
                GROUP BY u.id
                ORDER BY u.last_activity DESC
            """)

            users = []
            for row in cursor.fetchall():
                preferences = set(row["preferences"].split(",")) if row["preferences"] else set()
                user_data = {
                    "user_id": row["id"],
                    "is_disabled": bool(row["is_disabled"]),
                    "voice_replies_enabled": bool(row["voice_replies_enabled"]),
                    "message_count": row["message_count"],
                    "voice_responses_sent": row["voice_responses_sent"],
                    "last_activity": datetime.fromisoformat(row["last_activity"]) if row["last_activity"] else datetime.now(),
                    "created_at": datetime.fromisoformat(row["created_at"]) if row["created_at"] else datetime.now(),
                    "user_profile": {
                        "username": row["username"],
                        "first_name": row["first_name"],
                        "last_name": row["last_name"],
                    },
                    "preferred_targets": preferences
                }
                users.append(user_data)
            return users
        finally:
            conn.close()

    async def get_all_users_summary(self) -> Dict:
        """Get summary of all users for admin dashboard"""
        return await asyncio.get_event_loop().run_in_executor(
            None, self._get_all_users_summary_sync
        )

    def _get_all_users_summary_sync(self) -> Dict:
        """Synchronous version of get_all_users_summary"""
        conn = self._get_connection()
        try:
            cursor = conn.execute("""
                SELECT u.*, GROUP_CONCAT(ulp.language_code) as preferences
                FROM users u
                LEFT JOIN user_language_preferences ulp ON u.id = ulp.user_id
                GROUP BY u.id
                ORDER BY u.last_activity DESC
            """)

            users = {}
            for row in cursor.fetchall():
                preferences = set(row["preferences"].split(",")) if row["preferences"] else set()
                users[row["id"]] = {
                    "is_disabled": bool(row["is_disabled"]),
                    "voice_replies_enabled": bool(row["voice_replies_enabled"]),
                    "message_count": row["message_count"],
                    "voice_responses_sent": row["voice_responses_sent"],
                    "last_activity": datetime.fromisoformat(row["last_activity"]),
                    "preferred_targets": preferences,
                    "user_profile": {
                        "username": row["username"],
                        "first_name": row["first_name"],
                        "last_name": row["last_name"],
                    }
                }

            return users
        finally:
            conn.close()

    # Atomic operations for analytics to prevent race conditions
    async def increment_message_count(self, user_id: int, user_profile: Optional[Dict] = None):
        """Atomically increment user message count and update last activity"""
        await asyncio.get_event_loop().run_in_executor(
            None, self._increment_message_count_sync, user_id, user_profile
        )

    def _increment_message_count_sync(self, user_id: int, user_profile: Optional[Dict] = None):
        """Synchronous version of increment_message_count"""
        conn = self._get_connection()
        try:
            # Ensure user exists first
            profile = user_profile or {"username": None, "first_name": None, "last_name": None}
            conn.execute("""
                INSERT OR IGNORE INTO users (id, username, first_name, last_name)
                VALUES (?, ?, ?, ?)
            """, (user_id, profile["username"], profile["first_name"], profile["last_name"]))

            # Atomically increment message count and update last activity
            conn.execute("""
                UPDATE users SET
                    message_count = message_count + 1,
                    last_activity = CURRENT_TIMESTAMP,
                    username = COALESCE(?, username),
                    first_name = COALESCE(?, first_name),
                    last_name = COALESCE(?, last_name)
                WHERE id = ?
            """, (profile["username"], profile["first_name"], profile["last_name"], user_id))

            conn.commit()
        finally:
            conn.close()

    async def increment_voice_responses(self, user_id: int):
        """Atomically increment voice response counter"""
        await asyncio.get_event_loop().run_in_executor(
            None, self._increment_voice_responses_sync, user_id
        )

    def _increment_voice_responses_sync(self, user_id: int):
        """Synchronous version of increment_voice_responses"""
        conn = self._get_connection()
        try:
            # Ensure user exists first
            conn.execute("""
                INSERT OR IGNORE INTO users (id) VALUES (?)
            """, (user_id,))

            # Atomically increment voice responses counter
            conn.execute("""
                UPDATE users SET voice_responses_sent = voice_responses_sent + 1
                WHERE id = ?
            """, (user_id,))

            conn.commit()
        finally:
            conn.close()

    async def toggle_user_disabled(self, user_id: int) -> bool:
        """Atomically toggle user disabled status"""
        return await asyncio.get_event_loop().run_in_executor(
            None, self._toggle_user_disabled_sync, user_id
        )

    def _toggle_user_disabled_sync(self, user_id: int) -> bool:
        """Synchronous version of toggle_user_disabled"""
        conn = self._get_connection()
        try:
            # Ensure user exists first
            conn.execute("""
                INSERT OR IGNORE INTO users (id) VALUES (?)
            """, (user_id,))

            # Get current disabled status and toggle it
            cursor = conn.execute("""
                SELECT is_disabled FROM users WHERE id = ?
            """, (user_id,))
            row = cursor.fetchone()
            current_disabled = bool(row["is_disabled"]) if row else False
            new_disabled = not current_disabled

            # Atomically update disabled status
            conn.execute("""
                UPDATE users SET is_disabled = ? WHERE id = ?
            """, (new_disabled, user_id))

            conn.commit()
            return not new_disabled  # Return enabled status
        finally:
            conn.close()

    async def set_user_disabled(self, user_id: int, disabled: bool) -> bool:
        """Atomically set user disabled status"""
        return await asyncio.get_event_loop().run_in_executor(
            None, self._set_user_disabled_sync, user_id, disabled
        )

    def _set_user_disabled_sync(self, user_id: int, disabled: bool) -> bool:
        """Synchronous version of set_user_disabled"""
        conn = self._get_connection()
        try:
            # Ensure user exists first
            conn.execute("""
                INSERT OR IGNORE INTO users (id) VALUES (?)
            """, (user_id,))

            # Atomically set disabled status
            conn.execute("""
                UPDATE users SET is_disabled = ? WHERE id = ?
            """, (disabled, user_id))

            conn.commit()
            return not disabled  # Return enabled status
        finally:
            conn.close()

    async def toggle_voice_replies(self, user_id: int) -> bool:
        """Atomically toggle voice replies preference"""
        return await asyncio.get_event_loop().run_in_executor(
            None, self._toggle_voice_replies_sync, user_id
        )

    def _toggle_voice_replies_sync(self, user_id: int) -> bool:
        """Synchronous version of toggle_voice_replies"""
        conn = self._get_connection()
        try:
            # Ensure user exists first
            conn.execute("""
                INSERT OR IGNORE INTO users (id) VALUES (?)
            """, (user_id,))

            # Get current voice replies status and toggle it
            cursor = conn.execute("""
                SELECT voice_replies_enabled FROM users WHERE id = ?
            """, (user_id,))
            row = cursor.fetchone()
            current_enabled = bool(row["voice_replies_enabled"]) if row else False
            new_enabled = not current_enabled

            # Atomically update voice replies status
            conn.execute("""
                UPDATE users SET voice_replies_enabled = ? WHERE id = ?
            """, (new_enabled, user_id))

            conn.commit()
            return new_enabled
        finally:
            conn.close()

    async def toggle_language_preference(self, user_id: int, lang_code: str) -> Set[str]:
        """Atomically toggle language preference and return current preferences"""
        return await asyncio.get_event_loop().run_in_executor(
            None, self._toggle_language_preference_sync, user_id, lang_code
        )

    def _toggle_language_preference_sync(self, user_id: int, lang_code: str) -> Set[str]:
        """Synchronous version of toggle_language_preference"""
        conn = self._get_connection()
        try:
            # Ensure user exists first
            conn.execute("""
                INSERT OR IGNORE INTO users (id) VALUES (?)
            """, (user_id,))

            # Check if preference exists
            cursor = conn.execute("""
                SELECT 1 FROM user_language_preferences WHERE user_id = ? AND language_code = ?
            """, (user_id, lang_code))
            exists = cursor.fetchone() is not None

            if exists:
                # Remove preference
                conn.execute("""
                    DELETE FROM user_language_preferences WHERE user_id = ? AND language_code = ?
                """, (user_id, lang_code))
            else:
                # Add preference
                conn.execute("""
                    INSERT OR IGNORE INTO user_language_preferences (user_id, language_code) VALUES (?, ?)
                """, (user_id, lang_code))

            # Get current preferences
            cursor = conn.execute("""
                SELECT language_code FROM user_language_preferences WHERE user_id = ?
            """, (user_id,))
            current_prefs = {row["language_code"] for row in cursor.fetchall()}

            # If no preferences left, restore all default languages
            if not current_prefs:
                default_langs = {"ru", "en", "th", "ja", "ko", "vi"}
                for lang in default_langs:
                    conn.execute("""
                        INSERT OR IGNORE INTO user_language_preferences (user_id, language_code) VALUES (?, ?)
                    """, (user_id, lang))
                current_prefs = default_langs

            conn.commit()
            return current_prefs
        finally:
            conn.close()

    async def delete_inactive_users(self, days: int = 3) -> int:
        """Delete users inactive for more than specified days"""
        return await asyncio.get_event_loop().run_in_executor(
            None, self._delete_inactive_users_sync, days
        )

    def _delete_inactive_users_sync(self, days: int) -> int:
        """Synchronous version of delete_inactive_users"""
        conn = self._get_connection()
        try:
            from datetime import datetime, timedelta
            threshold = datetime.now() - timedelta(days=days)

            # Get count of users to be deleted
            cursor = conn.execute("""
                SELECT COUNT(*) as count FROM users
                WHERE last_activity < ?
            """, (threshold.isoformat(),))
            count = cursor.fetchone()["count"]

            # Delete language preferences first (foreign key constraint)
            conn.execute("""
                DELETE FROM user_language_preferences
                WHERE user_id IN (
                    SELECT id FROM users WHERE last_activity < ?
                )
            """, (threshold.isoformat(),))

            # Delete users
            conn.execute("""
                DELETE FROM users WHERE last_activity < ?
            """, (threshold.isoformat(),))

            conn.commit()
            logger.info(f"Deleted {count} inactive users (>{days} days)")
            return count
        finally:
            conn.close()

    async def clear_tts_cache(self, days: int = 3) -> tuple[int, float]:
        """Clear TTS cache files older than specified days"""
        return await asyncio.get_event_loop().run_in_executor(
            None, self._clear_tts_cache_sync, days
        )

    def _clear_tts_cache_sync(self, days: int) -> tuple[int, float]:
        """Synchronous version of clear_tts_cache"""
        import os
        from datetime import datetime, timedelta

        cache_path = Path("data/cache/tts")
        if not cache_path.exists():
            return (0, 0.0)

        threshold = datetime.now() - timedelta(days=days)
        deleted_count = 0
        deleted_size = 0.0

        for file_path in cache_path.glob("*.ogg"):
            try:
                file_mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
                if file_mtime < threshold:
                    file_size = file_path.stat().st_size
                    file_path.unlink()
                    deleted_count += 1
                    deleted_size += file_size
            except Exception as e:
                logger.error(f"Error deleting cache file {file_path}: {e}")

        deleted_size_mb = deleted_size / (1024 * 1024)
        logger.info(f"Cleared {deleted_count} TTS cache files ({deleted_size_mb:.2f} MB)")
        return (deleted_count, deleted_size_mb)