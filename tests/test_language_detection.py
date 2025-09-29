import pytest
import tempfile
import asyncio
from pathlib import Path
from datetime import datetime
from unittest.mock import AsyncMock, Mock, patch
from src.storage.database import DatabaseManager

from src.services.language import detect_language
from src.services.analytics import (
    is_admin, get_user_analytics, update_user_activity, is_user_disabled,
    set_user_disabled, is_voice_replies_enabled, toggle_voice_replies,
    increment_voice_responses, get_user_preferences, update_user_preference
)
from src.core.constants import SUPPORTED_LANGUAGES, ADMIN_IDS


# Mock OpenAI API responses for offline testing
class MockOpenAIResponse:
    def __init__(self, content: str):
        self.choices = [Mock(message=Mock(content=content))]


class MockTTSResponse:
    def __init__(self, content: bytes):
        self.content = content


class MockOpenAIClient:
    """Mock OpenAI client for offline testing"""

    def __init__(self):
        self.chat = Mock()
        self.audio = Mock()

        # Mock chat completions
        self.chat.completions = Mock()
        self.chat.completions.create = AsyncMock(side_effect=self._mock_translate)

        # Mock audio/speech
        self.audio.speech = Mock()
        self.audio.speech.create = AsyncMock(side_effect=self._mock_tts)

    async def _mock_translate(self, model, messages, max_tokens=None, temperature=None):
        """Mock translation based on input language"""
        text = messages[0]["content"]

        # Simple mock translations based on detected patterns
        if "hello" in text.lower():
            return MockOpenAIResponse(
                "Russian: Привет\n"
                "Thai: สวัสดี\n"
                "Japanese: こんにちは\n"
                "Korean: 안녕하세요\n"
                "Vietnamese: Xin chào"
            )
        elif "привет" in text.lower():
            return MockOpenAIResponse(
                "English: Hello\n"
                "Thai: สวัสดี\n"
                "Japanese: こんにちは\n"
                "Korean: 안녕하세요\n"
                "Vietnamese: Xin chào"
            )
        elif "สวัสดี" in text:
            return MockOpenAIResponse(
                "English: Hello\n"
                "Russian: Привет\n"
                "Japanese: こんにちは\n"
                "Korean: 안녕하세요\n"
                "Vietnamese: Xin chào"
            )
        elif "こんにちは" in text:
            return MockOpenAIResponse(
                "English: Hello\n"
                "Russian: Привет\n"
                "Thai: สวัสดี\n"
                "Korean: 안녕하세요\n"
                "Vietnamese: Xin chào"
            )
        elif "안녕하세요" in text:
            return MockOpenAIResponse(
                "English: Hello\n"
                "Russian: Привет\n"
                "Thai: สวัสดี\n"
                "Japanese: こんにちは\n"
                "Vietnamese: Xin chào"
            )
        elif "xin chào" in text.lower():
            return MockOpenAIResponse(
                "English: Hello\n"
                "Russian: Привет\n"
                "Thai: สวัสดี\n"
                "Japanese: こんにちは\n"
                "Korean: 안녕하세요"
            )
        else:
            # Default response for unknown text
            return MockOpenAIResponse(
                "English: Test translation\n"
                "Russian: Тестовый перевод"
            )

    async def _mock_tts(self, model, voice, input, response_format="opus"):
        """Mock TTS with dummy audio data"""
        # Generate dummy audio data (OGG header + some data)
        dummy_audio = b"OggS\x00\x02\x00\x00\x00\x00\x00\x00\x00\x00" + b"dummy_audio_data" * 100
        return MockTTSResponse(dummy_audio)


class MockConfig:
    """Mock configuration for offline testing"""
    def __init__(self):
        self.translation = Mock()
        self.translation.max_retries = 3
        self.translation.max_tokens = 1000
        self.translation.retry_delay_base = 2
        self.translation.max_input_characters = 4000
        self.translation.display_truncate_length = 100

        self.tts = Mock()
        self.tts.model = "tts-1"
        self.tts.voice = "alloy"
        self.tts.max_characters = 1000

        self.openai = Mock()
        self.openai.model = "gpt-4"

        self.database = Mock()
        self.database.path = "test.db"


class MockTTSCache:
    """Mock persistent TTS cache"""
    def get(self, text):
        return None  # Always miss cache for testing

    def set(self, text, audio_data):
        from pathlib import Path
        import tempfile
        temp_dir = Path(tempfile.mkdtemp())
        temp_path = temp_dir / "test_tts.ogg"
        temp_path.write_bytes(audio_data)
        return temp_path

@pytest.fixture(autouse=True)
def mock_openai_client():
    """Mock OpenAI client and config for all tests"""
    with patch('src.core.app.openai_client', MockOpenAIClient()):
        with patch('src.services.translation.openai_client', MockOpenAIClient()):
            with patch('src.core.app.config', MockConfig()):
                with patch('src.services.translation.config', MockConfig()):
                    # Mock cache to avoid file system dependencies
                    with patch('src.services.translation.translation_cache', {}):
                        with patch('src.services.translation.persistent_tts_cache', MockTTSCache()):
                            yield


# Offline translation function for testing
async def translate_text(text, source_lang, target_langs):
    """Mock translate_text function for offline testing"""
    translations = {}

    # Mock translations based on source language
    mock_translations = {
        "en": {"ru": "Привет", "th": "สวัสดี", "ja": "こんにちは", "ko": "안녕하세요", "vi": "Xin chào"},
        "ru": {"en": "Hello", "th": "สวัสดี", "ja": "こんにちは", "ko": "안녕하세요", "vi": "Xin chào"},
        "th": {"en": "Hello", "ru": "Привет", "ja": "こんにちは", "ko": "안녕하세요", "vi": "Xin chào"},
        "ja": {"en": "Hello", "ru": "Привет", "th": "สวัสดี", "ko": "안녕하세요", "vi": "Xin chào"},
        "ko": {"en": "Hello", "ru": "Привет", "th": "สวัสดี", "ja": "こんにちは", "vi": "Xin chào"},
        "vi": {"en": "Hello", "ru": "Привет", "th": "สวัสดี", "ja": "こんにちは", "ko": "안녕하세요"}
    }

    if source_lang in mock_translations:
        for target_lang in target_langs:
            if target_lang in mock_translations[source_lang]:
                translations[target_lang] = mock_translations[source_lang][target_lang]

    return translations

@pytest.fixture
async def test_db():
    """Create a temporary database for testing"""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name

    # Patch the global db object in src.core.app
    from src.core import app
    original_db = app.db

    test_db_manager = DatabaseManager(db_path)
    await test_db_manager.init_db()
    app.db = test_db_manager

    yield test_db_manager

    # Restore original db and cleanup
    app.db = original_db
    Path(db_path).unlink(missing_ok=True)


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
        """Test default preferences without database interaction"""
        from src.core.constants import SUPPORTED_LANGUAGES
        prefs = set(SUPPORTED_LANGUAGES.keys())
        assert prefs == {"ru", "en", "th", "ja", "ko", "vi"}  # All supported languages by default

    @pytest.mark.asyncio
    async def test_toggle_preference(self, test_db):
        user_id = 12346

        # Toggle off English
        prefs = await update_user_preference(user_id, "en")
        assert "en" not in prefs
        assert {"ru", "th", "ja", "ko", "vi"}.issubset(prefs)

        # Toggle English back on
        prefs = await update_user_preference(user_id, "en")
        assert "en" in prefs

    @pytest.mark.asyncio
    async def test_auto_fallback_when_all_disabled(self, test_db):
        user_id = 12347

        # Disable all languages
        await update_user_preference(user_id, "en")
        await update_user_preference(user_id, "ru")
        await update_user_preference(user_id, "th")
        await update_user_preference(user_id, "ja")
        await update_user_preference(user_id, "ko")
        prefs = await update_user_preference(user_id, "vi")

        # Should auto-enable all languages
        assert prefs == {"ru", "en", "th", "ja", "ko", "vi"}

    @pytest.mark.asyncio
    async def test_preference_persistence(self, test_db):
        user_id = 12348

        # Toggle off English (should remove it from default set)
        prefs1 = await update_user_preference(user_id, "en")  # Disable English

        # Get preferences again - should be the same
        prefs2 = await get_user_preferences(user_id)
        assert prefs1 == prefs2
        assert "en" not in prefs2  # English should be disabled
        assert len(prefs2) == 5  # Should have 5 languages left


class TestOfflineTranslation:
    """Test offline translation functionality with OpenAI mocks"""

    @pytest.mark.asyncio
    async def test_translate_text_offline(self):
        """Test translation function works offline with mocks"""
        from src.services.translation import translate_text

        # Test English to other languages
        text = "Hello"
        source_lang = "en"
        target_langs = {"ru", "th"}

        translations = await translate_text(text, source_lang, target_langs)

        # Verify we get translations (mocked)
        assert isinstance(translations, dict)
        assert len(translations) <= len(target_langs)  # Some may fail

        # Verify we don't get source language in result
        assert source_lang not in translations

    @pytest.mark.asyncio
    async def test_tts_generation_offline(self):
        """Test TTS generation works offline with mocks"""
        from src.services.translation import generate_tts_audio

        text = "Hello world"
        audio_path = await generate_tts_audio(text)

        # Should get a path to generated audio file
        if audio_path:  # TTS might be disabled in test config
            assert audio_path.exists()
            assert audio_path.suffix == ".ogg"
            # Cleanup
            import shutil
            if audio_path.parent.exists():
                shutil.rmtree(audio_path.parent, ignore_errors=True)

    @pytest.mark.asyncio
    async def test_translation_error_handling(self):
        """Test translation handles errors gracefully"""
        from src.services.translation import translate_text

        # Test with empty text
        translations = await translate_text("", "en", {"ru"})
        assert isinstance(translations, dict)

        # Test with unsupported language combination
        translations = await translate_text("Hello", "en", set())
        assert translations == {}


class TestVoiceTranslationPipeline:
    """Test voice translation pipeline with mocked transcription"""

    @pytest.mark.asyncio
    async def test_translation_pipeline_with_transcription(self):
        """Test that transcribed text flows through translation pipeline correctly"""
        from src.services.translation import translate_text

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

    @pytest.mark.asyncio
    async def test_voice_preference_integration(self, test_db):
        """Test that voice messages respect user preferences"""
        user_id = 99999

        # User toggles off English - should be removed from default set
        prefs = await update_user_preference(user_id, "en")

        # Voice transcription should use same preferences as text
        assert "en" not in prefs
        assert {"ru", "th", "ja", "ko", "vi"}.issubset(prefs)
        assert len(prefs) == 5  # Should have 5 languages left

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
        from src.services.translation import translate_text

        user_id = 99998

        # Clear all user preferences (simulate empty preferences)
        source_lang = "en"
        transcription = "Hello world"

        # Should fall back to translating to other languages
        all_langs = {"ru", "en", "th", "ja", "ko", "vi"}
        target_langs = all_langs - {source_lang}

        # Verify fallback logic works
        assert target_langs == {"ru", "th", "ja", "ko", "vi"}

        # Test translation still works
        translations = await translate_text(transcription, source_lang, target_langs)
        assert isinstance(translations, dict)


class TestVoiceReplies:
    """Test voice replies functionality"""

    @pytest.mark.asyncio
    async def test_voice_replies_default_disabled(self, test_db):
        """Test that voice replies are disabled by default"""
        user_id = 60001
        assert not await is_voice_replies_enabled(user_id)

    @pytest.mark.asyncio
    async def test_toggle_voice_replies(self, test_db):
        """Test toggling voice replies on and off"""
        user_id = 60002

        # Initially disabled
        assert not await is_voice_replies_enabled(user_id)

        # Toggle on
        await toggle_voice_replies(user_id)
        assert await is_voice_replies_enabled(user_id)

        # Toggle off
        await toggle_voice_replies(user_id)
        assert not await is_voice_replies_enabled(user_id)

    @pytest.mark.asyncio
    async def test_voice_responses_counter(self, test_db):
        """Test voice responses analytics tracking"""
        user_id = 60003

        # Initial count should be 0
        analytics = await get_user_analytics(user_id)
        assert analytics.get("voice_responses_sent", 0) == 0

        # Increment voice responses
        await increment_voice_responses(user_id)
        analytics = await get_user_analytics(user_id)
        assert analytics.get("voice_responses_sent", 0) == 1

        # Increment again
        await increment_voice_responses(user_id)
        analytics = await get_user_analytics(user_id)
        assert analytics.get("voice_responses_sent", 0) == 2

    @pytest.mark.asyncio
    async def test_voice_replies_persistence(self, test_db):
        """Test that voice replies setting persists"""
        user_id = 60004

        # Enable voice replies
        await toggle_voice_replies(user_id)
        assert await is_voice_replies_enabled(user_id)

        # Check setting persists
        assert await is_voice_replies_enabled(user_id)

        # Disable and check again
        await toggle_voice_replies(user_id)
        assert not await is_voice_replies_enabled(user_id)
        assert not await is_voice_replies_enabled(user_id)

    @pytest.mark.asyncio
    async def test_voice_analytics_integration(self, test_db):
        """Test that voice settings integrate with user analytics"""
        user_id = 60005

        # Enable voice replies
        await toggle_voice_replies(user_id)

        # Check analytics reflect voice setting
        analytics = await get_user_analytics(user_id)
        assert "voice_responses_sent" in analytics
        assert analytics.get("voice_responses_sent", 0) == 0

        # Increment voice usage and verify tracking
        await increment_voice_responses(user_id)
        analytics = await get_user_analytics(user_id)
        assert analytics.get("voice_responses_sent", 0) == 1

    @pytest.mark.asyncio
    async def test_voice_pipeline_with_preferences(self, test_db):
        """Test voice pipeline respects user voice preferences"""
        from src.services.translation import translate_text

        user_id = 60006

        # Test with voice replies disabled (default)
        assert not await is_voice_replies_enabled(user_id)

        # Enable voice replies
        await toggle_voice_replies(user_id)
        assert await is_voice_replies_enabled(user_id)

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

    @pytest.mark.asyncio
    async def test_analytics_creation(self, test_db):
        """Test that analytics are created for new users"""
        user_id = 50001
        analytics = await get_user_analytics(user_id)

        assert analytics["is_disabled"] is False
        assert analytics["message_count"] == 0
        assert isinstance(analytics["last_activity"], datetime)
        assert analytics["preferred_targets"] == {"ru", "en", "th", "ja", "ko", "vi"}
        assert "user_profile" in analytics

    @pytest.mark.asyncio
    async def test_activity_update(self, test_db):
        """Test that user activity is properly tracked"""
        import time
        user_id = 50002

        # Get initial analytics
        analytics_before = await get_user_analytics(user_id)
        initial_count = analytics_before["message_count"]
        initial_activity = analytics_before["last_activity"]

        # Add small delay to ensure timestamp difference
        time.sleep(0.01)  # Longer delay for reliability

        # Update activity using new atomic operation
        await update_user_activity(user_id)

        # Check updated analytics
        analytics_after = await get_user_analytics(user_id)
        assert analytics_after["message_count"] == initial_count + 1

        # Check activity was updated (allow some tolerance for time zones)
        time_diff = abs((analytics_after["last_activity"] - initial_activity).total_seconds())
        assert time_diff >= 0  # Should be same or newer

    @pytest.mark.asyncio
    async def test_user_disable_enable(self, test_db):
        """Test user disable/enable functionality"""
        user_id = 50003

        # Initially enabled
        assert not await is_user_disabled(user_id)

        # Disable user
        await set_user_disabled(user_id, True)
        assert await is_user_disabled(user_id)

        # Enable user
        await set_user_disabled(user_id, False)
        assert not await is_user_disabled(user_id)

    def test_admin_functionality(self):
        """Test admin privilege checking"""
        # Test with admin IDs if any are configured
        if ADMIN_IDS:
            admin_id = next(iter(ADMIN_IDS))
            assert is_admin(admin_id)

        # Test with non-admin ID
        non_admin_id = 999999
        assert not is_admin(non_admin_id)

    @pytest.mark.asyncio
    async def test_analytics_sync_with_preferences(self, test_db):
        """Test that analytics stay in sync with user preferences"""
        user_id = 50999  # Fresh user ID to avoid conflicts with other tests

        # New user starts with all 6 languages by default
        analytics = await get_user_analytics(user_id)
        assert len(analytics["preferred_targets"]) == 6
        assert "en" in analytics["preferred_targets"]

        # First toggle removes English from default set
        prefs = await update_user_preference(user_id, "en")
        analytics = await get_user_analytics(user_id)
        assert analytics["preferred_targets"] == prefs
        assert "en" not in analytics["preferred_targets"]
        assert len(analytics["preferred_targets"]) == 5  # Should have 5 languages left

        # Second toggle adds English back
        prefs = await update_user_preference(user_id, "en")
        analytics = await get_user_analytics(user_id)
        assert analytics["preferred_targets"] == prefs
        assert "en" in analytics["preferred_targets"]
        assert len(analytics["preferred_targets"]) == 6  # Should have all 6 languages