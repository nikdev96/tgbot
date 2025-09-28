"""
Tests for database functionality
"""
import asyncio
import pytest
import tempfile
from pathlib import Path
from src.storage.database import DatabaseManager


class TestDatabaseManager:
    """Test database operations"""

    @pytest.fixture
    async def db_manager(self):
        """Create a temporary database for testing"""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
            db_path = tmp.name

        db = DatabaseManager(db_path)
        await db.init_db()
        yield db

        # Cleanup
        Path(db_path).unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_database_initialization(self, db_manager):
        """Test that database initializes correctly"""
        # Database is already initialized by fixture
        assert Path(db_manager.db_path).exists()

    @pytest.mark.asyncio
    async def test_default_user_preferences(self, db_manager):
        """Test that new users get default preferences"""
        user_id = 12345
        prefs = await db_manager.get_user_preferences(user_id)

        expected = {"ru", "en", "th", "ja", "ko", "vi"}
        assert prefs == expected

    @pytest.mark.asyncio
    async def test_update_user_preferences(self, db_manager):
        """Test updating user preferences"""
        user_id = 12346

        # Update preferences
        new_prefs = {"en", "ru"}
        await db_manager.update_user_preferences(user_id, new_prefs)

        # Verify update
        saved_prefs = await db_manager.get_user_preferences(user_id)
        assert saved_prefs == new_prefs

    @pytest.mark.asyncio
    async def test_user_analytics_creation(self, db_manager):
        """Test creating user analytics"""
        user_id = 12347
        user_profile = {
            "username": "testuser",
            "first_name": "Test",
            "last_name": "User"
        }

        analytics = await db_manager.get_user_analytics(user_id, user_profile)

        assert analytics["is_disabled"] is False
        assert analytics["voice_replies_enabled"] is False
        assert analytics["message_count"] == 0
        assert analytics["voice_responses_sent"] == 0
        assert analytics["user_profile"]["username"] == "testuser"
        assert len(analytics["preferred_targets"]) == 6

    @pytest.mark.asyncio
    async def test_user_analytics_update(self, db_manager):
        """Test updating user analytics"""
        user_id = 12348

        # Create user first
        initial_analytics = await db_manager.get_user_analytics(user_id)

        # Update analytics
        initial_analytics["message_count"] = 10
        initial_analytics["is_disabled"] = True
        initial_analytics["voice_replies_enabled"] = True

        await db_manager.update_user_analytics(user_id, initial_analytics)

        # Verify update
        updated_analytics = await db_manager.get_user_analytics(user_id)
        assert updated_analytics["message_count"] == 10
        assert updated_analytics["is_disabled"] is True
        assert updated_analytics["voice_replies_enabled"] is True

    @pytest.mark.asyncio
    async def test_user_persistence(self, db_manager):
        """Test that user data persists across calls"""
        user_id = 12349

        # Create user with specific preferences
        await db_manager.update_user_preferences(user_id, {"en", "ja"})

        # Get user analytics to create the user
        analytics = await db_manager.get_user_analytics(user_id, {
            "username": "persistent",
            "first_name": "Persistent",
            "last_name": "User"
        })

        # Update message count
        analytics["message_count"] = 5
        await db_manager.update_user_analytics(user_id, analytics)

        # Verify data persists
        fresh_prefs = await db_manager.get_user_preferences(user_id)
        fresh_analytics = await db_manager.get_user_analytics(user_id)

        assert fresh_prefs == {"en", "ja"}
        assert fresh_analytics["message_count"] == 5
        assert fresh_analytics["user_profile"]["username"] == "persistent"

    @pytest.mark.asyncio
    async def test_multiple_users(self, db_manager):
        """Test handling multiple users independently"""
        user1_id = 11111
        user2_id = 22222

        # Set different preferences for each user
        await db_manager.update_user_preferences(user1_id, {"en"})
        await db_manager.update_user_preferences(user2_id, {"ru", "ja"})

        # Verify independence
        user1_prefs = await db_manager.get_user_preferences(user1_id)
        user2_prefs = await db_manager.get_user_preferences(user2_id)

        assert user1_prefs == {"en"}
        assert user2_prefs == {"ru", "ja"}

    @pytest.mark.asyncio
    async def test_all_users_summary(self, db_manager):
        """Test getting summary of all users"""
        # Create a few users
        await db_manager.get_user_analytics(100, {"username": "user1", "first_name": "User", "last_name": "One"})
        await db_manager.get_user_analytics(200, {"username": "user2", "first_name": "User", "last_name": "Two"})

        summary = await db_manager.get_all_users_summary()

        assert len(summary) >= 2
        assert 100 in summary
        assert 200 in summary
        assert summary[100]["user_profile"]["username"] == "user1"
        assert summary[200]["user_profile"]["username"] == "user2"