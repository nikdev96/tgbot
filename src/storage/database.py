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
from ..core.constants import DEFAULT_LANGUAGES

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

                CREATE TABLE IF NOT EXISTS rooms (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    code TEXT UNIQUE NOT NULL,
                    creator_id INTEGER NOT NULL,
                    name TEXT,
                    status TEXT DEFAULT 'active',
                    max_members INTEGER DEFAULT 10,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    expires_at TIMESTAMP,
                    FOREIGN KEY (creator_id) REFERENCES users(id)
                );

                CREATE TABLE IF NOT EXISTS room_members (
                    room_id INTEGER,
                    user_id INTEGER,
                    language_code TEXT NOT NULL,
                    role TEXT DEFAULT 'member',
                    joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (room_id, user_id),
                    FOREIGN KEY (room_id) REFERENCES rooms(id) ON DELETE CASCADE,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS room_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    room_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    message_text TEXT NOT NULL,
                    language_code TEXT NOT NULL,
                    message_type TEXT DEFAULT 'text',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (room_id) REFERENCES rooms(id) ON DELETE CASCADE,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                );

                CREATE INDEX IF NOT EXISTS idx_users_last_activity ON users(last_activity);
                CREATE INDEX IF NOT EXISTS idx_user_prefs_user_id ON user_language_preferences(user_id);
                CREATE INDEX IF NOT EXISTS idx_rooms_code ON rooms(code);
                CREATE INDEX IF NOT EXISTS idx_rooms_status ON rooms(status);
                CREATE INDEX IF NOT EXISTS idx_room_members_user ON room_members(user_id);
                CREATE INDEX IF NOT EXISTS idx_room_messages_room ON room_messages(room_id);
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
                return DEFAULT_LANGUAGES

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
                    preferences = DEFAULT_LANGUAGES

                analytics["preferred_targets"] = preferences
                return analytics
            else:
                # Create new user - check if preferences already exist
                prefs_cursor = conn.execute(
                    "SELECT language_code FROM user_language_preferences WHERE user_id = ?",
                    (user_id,)
                )
                existing_preferences = {prow["language_code"] for prow in prefs_cursor.fetchall()}

                # Use existing preferences if any, otherwise use default languages
                preferences = existing_preferences if existing_preferences else DEFAULT_LANGUAGES

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

        except Exception as e:
            logger.error(f"Error adding Vietnamese to users: {e}")
            conn.rollback()
        finally:
            conn.close()

    async def replace_japanese_with_arabic(self):
        """Replace Japanese (ja) with Arabic (ar) in all user preferences"""
        await asyncio.get_event_loop().run_in_executor(
            None, self._replace_japanese_with_arabic_sync
        )

    def _replace_japanese_with_arabic_sync(self):
        """Synchronous version of replace_japanese_with_arabic"""
        conn = self._get_connection()
        try:
            # Replace Japanese with Arabic in user preferences
            conn.execute("""
                UPDATE user_language_preferences
                SET language_code = 'ar'
                WHERE language_code = 'ja'
            """)

            # Replace Japanese with Arabic in room members
            conn.execute("""
                UPDATE room_members
                SET language_code = 'ar'
                WHERE language_code = 'ja'
            """)

            # Replace Japanese with Arabic in room messages
            conn.execute("""
                UPDATE room_messages
                SET language_code = 'ar'
                WHERE language_code = 'ja'
            """)

            rows_updated = conn.total_changes
            conn.commit()
            logger.info(f"Replaced Japanese with Arabic: {rows_updated} records updated")

        except Exception as e:
            logger.error(f"Error replacing Japanese with Arabic: {e}")
            conn.rollback()
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

            # If no preferences left, restore default languages
            if not current_prefs:
                for lang in DEFAULT_LANGUAGES:
                    conn.execute("""
                        INSERT OR IGNORE INTO user_language_preferences (user_id, language_code) VALUES (?, ?)
                    """, (user_id, lang))
                current_prefs = DEFAULT_LANGUAGES

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

    # ==================== ROOM MANAGEMENT ====================

    async def create_room(self, creator_id: int, language_code: str, name: Optional[str] = None) -> str:
        """Create a new room and return room code"""
        return await asyncio.get_event_loop().run_in_executor(
            None, self._create_room_sync, creator_id, language_code, name
        )

    def _create_room_sync(self, creator_id: int, language_code: str, name: Optional[str]) -> str:
        """Synchronous version of create_room"""
        import random, string
        from datetime import timedelta

        conn = self._get_connection()
        try:
            # Generate unique room code
            while True:
                code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
                cursor = conn.execute("SELECT 1 FROM rooms WHERE code = ?", (code,))
                if not cursor.fetchone():
                    break

            # Set expiration to 24 hours from now
            expires_at = (datetime.now() + timedelta(hours=24)).isoformat()

            # Create room
            cursor = conn.execute("""
                INSERT INTO rooms (code, creator_id, name, expires_at)
                VALUES (?, ?, ?, ?)
            """, (code, creator_id, name, expires_at))
            room_id = cursor.lastrowid

            # Add creator as first member
            conn.execute("""
                INSERT INTO room_members (room_id, user_id, language_code, role)
                VALUES (?, ?, ?, 'creator')
            """, (room_id, creator_id, language_code))

            conn.commit()
            logger.info(f"Room created: {code} by user {creator_id}")
            return code

        finally:
            conn.close()

    async def get_room_by_code(self, code: str) -> Optional[Dict]:
        """Get room by code"""
        return await asyncio.get_event_loop().run_in_executor(
            None, self._get_room_by_code_sync, code
        )

    def _get_room_by_code_sync(self, code: str) -> Optional[Dict]:
        """Synchronous version of get_room_by_code"""
        conn = self._get_connection()
        try:
            cursor = conn.execute("""
                SELECT * FROM rooms WHERE code = ? AND status = 'active'
            """, (code,))
            row = cursor.fetchone()

            if not row:
                return None

            return {
                "id": row["id"],
                "code": row["code"],
                "creator_id": row["creator_id"],
                "name": row["name"],
                "status": row["status"],
                "max_members": row["max_members"],
                "created_at": datetime.fromisoformat(row["created_at"]),
                "expires_at": datetime.fromisoformat(row["expires_at"]) if row["expires_at"] else None
            }
        finally:
            conn.close()

    async def join_room(self, room_id: int, user_id: int, language_code: str) -> bool:
        """Join room as member"""
        return await asyncio.get_event_loop().run_in_executor(
            None, self._join_room_sync, room_id, user_id, language_code
        )

    def _join_room_sync(self, room_id: int, user_id: int, language_code: str) -> bool:
        """Synchronous version of join_room"""
        conn = self._get_connection()
        try:
            # Check if room is full
            cursor = conn.execute("""
                SELECT COUNT(*) as count, max_members
                FROM room_members, rooms
                WHERE room_members.room_id = ? AND rooms.id = ?
            """, (room_id, room_id))
            row = cursor.fetchone()

            if row and row["count"] >= row["max_members"]:
                logger.warning(f"Room {room_id} is full")
                return False

            # Add member
            conn.execute("""
                INSERT OR REPLACE INTO room_members (room_id, user_id, language_code)
                VALUES (?, ?, ?)
            """, (room_id, user_id, language_code))

            conn.commit()
            logger.info(f"User {user_id} joined room {room_id}")
            return True

        except Exception as e:
            logger.error(f"Error joining room: {e}")
            return False
        finally:
            conn.close()

    async def leave_room(self, room_id: int, user_id: int) -> bool:
        """Leave room"""
        return await asyncio.get_event_loop().run_in_executor(
            None, self._leave_room_sync, room_id, user_id
        )

    def _leave_room_sync(self, room_id: int, user_id: int) -> bool:
        """Synchronous version of leave_room"""
        conn = self._get_connection()
        try:
            conn.execute("""
                DELETE FROM room_members WHERE room_id = ? AND user_id = ?
            """, (room_id, user_id))

            # Check if room is empty, close it
            cursor = conn.execute("""
                SELECT COUNT(*) as count FROM room_members WHERE room_id = ?
            """, (room_id,))
            if cursor.fetchone()["count"] == 0:
                conn.execute("""
                    UPDATE rooms SET status = 'closed' WHERE id = ?
                """, (room_id,))
                logger.info(f"Room {room_id} closed (empty)")

            conn.commit()
            logger.info(f"User {user_id} left room {room_id}")
            return True

        except Exception as e:
            logger.error(f"Error leaving room: {e}")
            return False
        finally:
            conn.close()

    async def get_room_members(self, room_id: int) -> List[Dict]:
        """Get all members of a room"""
        return await asyncio.get_event_loop().run_in_executor(
            None, self._get_room_members_sync, room_id
        )

    def _get_room_members_sync(self, room_id: int) -> List[Dict]:
        """Synchronous version of get_room_members"""
        conn = self._get_connection()
        try:
            cursor = conn.execute("""
                SELECT rm.*, u.username, u.first_name, u.last_name
                FROM room_members rm
                JOIN users u ON rm.user_id = u.id
                WHERE rm.room_id = ?
                ORDER BY rm.joined_at
            """, (room_id,))

            members = []
            for row in cursor.fetchall():
                members.append({
                    "room_id": row["room_id"],
                    "user_id": row["user_id"],
                    "language_code": row["language_code"],
                    "role": row["role"],
                    "joined_at": datetime.fromisoformat(row["joined_at"]),
                    "user_profile": {
                        "username": row["username"],
                        "first_name": row["first_name"],
                        "last_name": row["last_name"]
                    }
                })

            return members
        finally:
            conn.close()

    async def get_user_active_room(self, user_id: int) -> Optional[Dict]:
        """Get user's active room if any"""
        return await asyncio.get_event_loop().run_in_executor(
            None, self._get_user_active_room_sync, user_id
        )

    def _get_user_active_room_sync(self, user_id: int) -> Optional[Dict]:
        """Synchronous version of get_user_active_room"""
        conn = self._get_connection()
        try:
            cursor = conn.execute("""
                SELECT r.*, rm.language_code, rm.role
                FROM rooms r
                JOIN room_members rm ON r.id = rm.room_id
                WHERE rm.user_id = ? AND r.status = 'active'
                LIMIT 1
            """, (user_id,))

            row = cursor.fetchone()
            if not row:
                return None

            return {
                "id": row["id"],
                "code": row["code"],
                "creator_id": row["creator_id"],
                "name": row["name"],
                "status": row["status"],
                "max_members": row["max_members"],
                "created_at": datetime.fromisoformat(row["created_at"]),
                "expires_at": datetime.fromisoformat(row["expires_at"]) if row["expires_at"] else None,
                "user_language": row["language_code"],
                "user_role": row["role"]
            }
        finally:
            conn.close()

    async def close_room(self, room_id: int) -> bool:
        """Close room"""
        return await asyncio.get_event_loop().run_in_executor(
            None, self._close_room_sync, room_id
        )

    def _close_room_sync(self, room_id: int) -> bool:
        """Synchronous version of close_room"""
        conn = self._get_connection()
        try:
            conn.execute("""
                UPDATE rooms SET status = 'closed' WHERE id = ?
            """, (room_id,))
            conn.commit()
            logger.info(f"Room {room_id} closed")
            return True
        except Exception as e:
            logger.error(f"Error closing room: {e}")
            return False
        finally:
            conn.close()

    async def save_room_message(self, room_id: int, user_id: int, text: str, language_code: str) -> bool:
        """Save room message to history"""
        return await asyncio.get_event_loop().run_in_executor(
            None, self._save_room_message_sync, room_id, user_id, text, language_code
        )

    def _save_room_message_sync(self, room_id: int, user_id: int, text: str, language_code: str) -> bool:
        """Synchronous version of save_room_message"""
        conn = self._get_connection()
        try:
            conn.execute("""
                INSERT INTO room_messages (room_id, user_id, message_text, language_code)
                VALUES (?, ?, ?, ?)
            """, (room_id, user_id, text, language_code))
            conn.commit()
            return True
        except Exception as e:
            logger.error(f"Error saving room message: {e}")
            return False
        finally:
            conn.close()

    async def delete_expired_rooms(self, hours: int = 24) -> int:
        """Delete expired rooms"""
        return await asyncio.get_event_loop().run_in_executor(
            None, self._delete_expired_rooms_sync, hours
        )

    def _delete_expired_rooms_sync(self, hours: int) -> int:
        """Synchronous version of delete_expired_rooms"""
        conn = self._get_connection()
        try:
            now = datetime.now().isoformat()

            # Get count first
            cursor = conn.execute("""
                SELECT COUNT(*) as count FROM rooms
                WHERE expires_at < ? AND status = 'active'
            """, (now,))
            count = cursor.fetchone()["count"]

            # Close expired rooms
            conn.execute("""
                UPDATE rooms SET status = 'closed'
                WHERE expires_at < ? AND status = 'active'
            """, (now,))

            conn.commit()
            logger.info(f"Closed {count} expired rooms")
            return count
        finally:
            conn.close()