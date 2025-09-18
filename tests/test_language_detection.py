import pytest
from src.bot import detect_language


class TestLanguageDetection:
    """Test cases for language detection functionality."""

    def test_detect_english(self):
        """Test detection of English text."""
        text = "Hello, how are you today? This is a test message in English."
        result = detect_language(text)
        assert result == "en"

    def test_detect_russian(self):
        """Test detection of Russian text."""
        text = "Привет, как дела? Это тестовое сообщение на русском языке."
        result = detect_language(text)
        assert result == "ru"

    def test_detect_thai(self):
        """Test detection of Thai text."""
        text = "สวัสดี เป็นอย่างไรบ้าง? นี่คือข้อความทดสอบภาษาไทย"
        result = detect_language(text)
        assert result == "th"

    def test_unsupported_language(self):
        """Test that unsupported languages return None."""
        text = "Bonjour, comment allez-vous?"  # French
        result = detect_language(text)
        assert result is None

    def test_empty_text(self):
        """Test that empty text returns None."""
        result = detect_language("")
        assert result is None

    def test_very_short_text(self):
        """Test behavior with very short text."""
        result = detect_language("Hi")
        # Short text might not be detected reliably, so we accept both en and None
        assert result in ["en", None]

    def test_mixed_language_text(self):
        """Test mixed language text detection."""
        text = "Hello привет สวัสดี"
        result = detect_language(text)
        # Mixed language detection should return one of the supported languages or None
        assert result in ["en", "ru", "th", None]