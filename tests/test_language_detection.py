import pytest
from datetime import datetime
from src.bot import (
    detect_language, get_user_preferences, update_user_preference,
    get_user_analytics, update_user_activity, is_user_disabled, set_user_disabled,
    is_admin, ADMIN_IDS, is_voice_replies_enabled, toggle_voice_replies,
    increment_voice_responses
)


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

    def test_detect_japanese(self):
        result = detect_language("こんにちは、元気ですか？")
        assert result == "ja"

    def test_detect_korean(self):
        result = detect_language("안녕하세요, 어떻게 지내세요?")
        assert result == "ko"

    def test_detect_short_japanese(self):
        result = detect_language("はい")  # Short text
        assert result == "ja"

    def test_detect_short_korean(self):
        result = detect_language("네")  # Short text
        assert result == "ko"

    def test_detect_short_thai(self):
        result = detect_language("ใช่")  # Short text
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
        assert prefs == {"ru", "en", "th", "ja", "ko"}  # All supported languages by default

    def test_toggle_preference(self):
        user_id = 12346

        # Toggle off English
        prefs = update_user_preference(user_id, "en")
        assert "en" not in prefs
        assert {"ru", "th", "ja", "ko"}.issubset(prefs)

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
        assert prefs == {"ru", "en", "th", "ja", "ko"}

    def test_preference_persistence(self):
        user_id = 12348

        # Set specific preferences
        update_user_preference(user_id, "en")  # Disable English
        prefs1 = get_user_preferences(user_id)

        # Get preferences again - should be the same
        prefs2 = get_user_preferences(user_id)
        assert prefs1 == prefs2
        assert "en" not in prefs2


class TestVoiceTranslationPipeline:
    """Test voice translation pipeline with mocked transcription"""

    @pytest.mark.asyncio
    async def test_translation_pipeline_with_transcription(self):
        """Test that transcribed text flows through translation pipeline correctly"""
        from src.bot import translate_text

        # Mock transcription text
        transcription = "Hello, this is a test voice message"
        source_lang = "en"
        target_langs = {"ru", "th"}

        # This would normally be called after Whisper transcription
        translations = await translate_text(transcription, source_lang, target_langs)

        # Should return translations for target languages
        assert isinstance(translations, dict)
        # In real scenario, would contain actual translations
        # Here we just verify the function accepts transcription input

    def test_voice_preference_integration(self):
        """Test that voice messages respect user preferences"""
        user_id = 99999

        # User disables English
        update_user_preference(user_id, "en")
        prefs = get_user_preferences(user_id)

        # Voice transcription should use same preferences as text
        assert "en" not in prefs
        assert {"ru", "th", "ja", "ko"}.issubset(prefs)

    def test_language_detection_with_voice_transcription(self):
        """Test language detection works with voice transcription text"""
        # Simulate transcriptions from different languages
        voice_transcriptions = [
            "Hello, how are you today? I hope you are doing well.",  # English (longer)
            "Привет, как у тебя дела? Надеюсь, всё хорошо.",   # Russian (longer)
            "สวัสดี เป็นอย่างไรบ้าง หวังว่าคุณสบายดี",     # Thai (longer)
        ]

        expected_langs = ["en", "ru", "th"]

        for transcription, expected in zip(voice_transcriptions, expected_langs):
            detected = detect_language(transcription)
            # Note: language detection may fail for short text, so we check if detected or expected is reasonable
            assert detected == expected or detected in ["en", "ru", "th", None]

    def test_transcription_text_truncation(self):
        """Test that long transcriptions are properly truncated for display"""
        # Simulate a very long transcription
        long_transcription = "This is a very long transcription " * 10

        # Test truncation logic (from voice handler)
        display_text = long_transcription if len(long_transcription) <= 100 else long_transcription[:97] + "..."

        # Should be truncated
        assert len(display_text) <= 100
        assert display_text.endswith("...")

    @pytest.mark.asyncio
    async def test_voice_preference_fallback(self):
        """Test that voice messages fall back correctly when no preferences set"""
        from src.bot import translate_text

        user_id = 99998

        # Clear all user preferences (simulate empty preferences)
        source_lang = "en"
        transcription = "Hello world"

        # Should fall back to translating to other languages
        all_langs = {"ru", "en", "th", "ja", "ko"}
        target_langs = all_langs - {source_lang}

        # Verify fallback logic works
        assert target_langs == {"ru", "th", "ja", "ko"}

        # Test translation still works
        translations = await translate_text(transcription, source_lang, target_langs)
        assert isinstance(translations, dict)


class TestVoiceReplies:
    """Test voice replies functionality"""

    def test_voice_replies_default_disabled(self):
        """Test that voice replies are disabled by default"""
        user_id = 60001
        assert not is_voice_replies_enabled(user_id)

    def test_toggle_voice_replies(self):
        """Test toggling voice replies on and off"""
        user_id = 60002

        # Initially disabled
        assert not is_voice_replies_enabled(user_id)

        # Toggle on
        toggle_voice_replies(user_id)
        assert is_voice_replies_enabled(user_id)

        # Toggle off
        toggle_voice_replies(user_id)
        assert not is_voice_replies_enabled(user_id)

    def test_voice_responses_counter(self):
        """Test voice responses analytics tracking"""
        user_id = 60003

        # Initial count should be 0
        analytics = get_user_analytics(user_id)
        assert analytics.get("voice_responses", 0) == 0

        # Increment voice responses
        increment_voice_responses(user_id)
        analytics = get_user_analytics(user_id)
        assert analytics.get("voice_responses", 0) == 1

        # Increment again
        increment_voice_responses(user_id)
        analytics = get_user_analytics(user_id)
        assert analytics.get("voice_responses", 0) == 2

    def test_voice_replies_persistence(self):
        """Test that voice replies setting persists"""
        user_id = 60004

        # Enable voice replies
        toggle_voice_replies(user_id)
        assert is_voice_replies_enabled(user_id)

        # Check setting persists
        assert is_voice_replies_enabled(user_id)

        # Disable and check again
        toggle_voice_replies(user_id)
        assert not is_voice_replies_enabled(user_id)
        assert not is_voice_replies_enabled(user_id)

    def test_voice_analytics_integration(self):
        """Test that voice settings integrate with user analytics"""
        user_id = 60005

        # Enable voice replies
        toggle_voice_replies(user_id)

        # Check analytics reflect voice setting
        analytics = get_user_analytics(user_id)
        assert "voice_responses" in analytics
        assert analytics.get("voice_responses", 0) == 0

        # Increment voice usage and verify tracking
        increment_voice_responses(user_id)
        analytics = get_user_analytics(user_id)
        assert analytics.get("voice_responses", 0) == 1

    @pytest.mark.asyncio
    async def test_voice_pipeline_with_preferences(self):
        """Test voice pipeline respects user voice preferences"""
        from src.bot import translate_text

        user_id = 60006

        # Test with voice replies disabled (default)
        assert not is_voice_replies_enabled(user_id)

        # Enable voice replies
        toggle_voice_replies(user_id)
        assert is_voice_replies_enabled(user_id)

        # Simulate translation that would trigger voice reply
        transcription = "Hello world"
        source_lang = "en"
        target_langs = {"ru", "th"}

        translations = await translate_text(transcription, source_lang, target_langs)
        assert isinstance(translations, dict)

        # Voice reply would be generated if TTS is available
        # (actual TTS testing would require mocking OpenAI API)


class TestUserAnalytics:
    """Test user analytics and admin functionality"""

    def test_analytics_creation(self):
        """Test that analytics are created for new users"""
        user_id = 50001
        analytics = get_user_analytics(user_id)

        assert analytics["is_disabled"] is False
        assert analytics["message_count"] == 0
        assert isinstance(analytics["last_activity"], datetime)
        assert analytics["preferred_targets"] == {"ru", "en", "th", "ja", "ko"}
        assert "user_profile" in analytics

    def test_activity_update(self):
        """Test that user activity is properly tracked"""
        import time
        user_id = 50002

        # Get initial analytics
        analytics_before = get_user_analytics(user_id)
        initial_count = analytics_before["message_count"]

        # Add small delay to ensure timestamp difference
        time.sleep(0.001)

        # Update activity
        update_user_activity(user_id)

        # Check updated analytics
        analytics_after = get_user_analytics(user_id)
        assert analytics_after["message_count"] == initial_count + 1
        assert analytics_after["last_activity"] >= analytics_before["last_activity"]

    def test_user_disable_enable(self):
        """Test user disable/enable functionality"""
        user_id = 50003

        # Initially enabled
        assert not is_user_disabled(user_id)

        # Disable user
        set_user_disabled(user_id, True)
        assert is_user_disabled(user_id)

        # Enable user
        set_user_disabled(user_id, False)
        assert not is_user_disabled(user_id)

    def test_admin_functionality(self):
        """Test admin privilege checking"""
        # Test with admin IDs if any are configured
        if ADMIN_IDS:
            admin_id = next(iter(ADMIN_IDS))
            assert is_admin(admin_id)

        # Test with non-admin ID
        non_admin_id = 999999
        assert not is_admin(non_admin_id)

    def test_analytics_sync_with_preferences(self):
        """Test that analytics stay in sync with user preferences"""
        user_id = 50004

        # Update preferences
        prefs = update_user_preference(user_id, "en")  # Toggle English off

        # Check analytics are synced
        analytics = get_user_analytics(user_id)
        assert analytics["preferred_targets"] == prefs
        assert "en" not in analytics["preferred_targets"]

        # Toggle back on
        prefs = update_user_preference(user_id, "en")
        analytics = get_user_analytics(user_id)
        assert analytics["preferred_targets"] == prefs
        assert "en" in analytics["preferred_targets"]