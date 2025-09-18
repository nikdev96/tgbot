import pytest
from src.bot import detect_language, get_user_preferences, update_user_preference


class TestLanguageDetection:
    """Test language detection functionality"""

    def test_detect_english(self):
        result = detect_language("Hello, how are you doing today?")
        assert result == "en"

    def test_detect_russian(self):
        result = detect_language("Привет, как у тебя дела сегодня?")
        assert result == "ru"

    def test_detect_thai(self):
        result = detect_language("สวัสดี เป็นอย่างไรบ้าง วันนี้")
        assert result == "th"

    def test_unsupported_language(self):
        result = detect_language("Bonjour, comment allez-vous?")  # French
        assert result is None

    def test_empty_text(self):
        result = detect_language("")
        assert result is None


class TestUserPreferences:
    """Test user preference management"""

    def test_default_preferences(self):
        user_id = 12345
        prefs = get_user_preferences(user_id)
        assert prefs == {"ru", "en", "th"}

    def test_toggle_preference(self):
        user_id = 12346

        # Toggle off English
        prefs = update_user_preference(user_id, "en")
        assert "en" not in prefs
        assert {"ru", "th"}.issubset(prefs)

        # Toggle English back on
        prefs = update_user_preference(user_id, "en")
        assert "en" in prefs

    def test_auto_fallback_when_all_disabled(self):
        user_id = 12347

        # Disable all languages
        update_user_preference(user_id, "en")
        update_user_preference(user_id, "ru")
        prefs = update_user_preference(user_id, "th")

        # Should auto-enable all languages
        assert prefs == {"ru", "en", "th"}

    def test_preference_persistence(self):
        user_id = 12348

        # Set specific preferences
        update_user_preference(user_id, "en")  # Disable English
        prefs1 = get_user_preferences(user_id)

        # Get preferences again - should be the same
        prefs2 = get_user_preferences(user_id)
        assert prefs1 == prefs2
        assert "en" not in prefs2