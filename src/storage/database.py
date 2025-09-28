"""
Database manager for persistent storage
"""
import asyncio
import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Set
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
                # Create new user
                default_preferences = {"ru", "en", "th", "ja", "ko", "vi"}  # Default supported languages

                analytics = {
                    "is_disabled": False,
                    "voice_replies_enabled": False,
                    "message_count": 0,
                    "voice_responses_sent": 0,
                    "last_activity": datetime.now(),
                    "preferred_targets": default_preferences,
                    "user_profile": user_profile or {
                        "username": None,
                        "first_name": None,
                        "last_name": None,
                    }
                }

                # Insert new user
                profile = analytics["user_profile"]
                conn.execute("""
                    INSERT INTO users (id, username, first_name, last_name)
                    VALUES (?, ?, ?, ?)
                """, (user_id, profile["username"], profile["first_name"], profile["last_name"]))

                # Insert default preferences
                for lang_code in default_preferences:
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