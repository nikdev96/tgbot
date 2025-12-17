"""
Language detection service
"""
import logging
import re
from langdetect import detect, LangDetectException
from ..core.constants import SUPPORTED_LANGUAGES

logger = logging.getLogger(__name__)


def detect_language(text: str) -> str:
    """Detect language with improved logic for Cyrillic languages"""

    # Language mapping for commonly misdetected languages
    LANGUAGE_MAPPING = {
        'mk': 'ru',  # Macedonian often confused with Russian
        'bg': 'ru',  # Bulgarian might also be confused
        'sr': 'ru',  # Serbian might also be confused
        'uk': 'ru',  # Ukrainian might also be confused
    }

    try:
        detected = detect(text)

        # If detected language is in supported languages, return it
        if detected in SUPPORTED_LANGUAGES:
            return detected

        # If detected language can be mapped to supported language, map it
        if detected in LANGUAGE_MAPPING:
            mapped_lang = LANGUAGE_MAPPING[detected]
            if mapped_lang in SUPPORTED_LANGUAGES:
                return mapped_lang

        # Additional heuristics for specific languages

        # Mixed language detection - if contains multiple scripts, return None
        has_cyrillic = bool(re.search(r'[а-яё]', text.lower()))
        has_latin = bool(re.search(r'[a-zA-Z]', text))
        has_arabic = bool(re.search(r'[\u0600-\u06ff\u0750-\u077f\u08a0-\u08ff\ufb50-\ufdff\ufe70-\ufeff]', text))
        has_korean = bool(re.search(r'[가-힣\u1100-\u11ff\u3130-\u318f\uac00-\ud7af]', text))
        has_thai = bool(re.search(r'[\u0e00-\u0e7f]', text))
        has_vietnamese = bool(re.search(r'[àáảãạầấẩẫậèéẻẽẹềếểễệìíỉĩịòóỏõọồốổỗộùúủũụừứửữựỳýỷỹỵđĐ]', text))

        script_count = sum([has_cyrillic, has_latin, has_arabic, has_korean, has_thai, has_vietnamese])
        if script_count > 1:
            return None  # Mixed languages

        # Cyrillic script - Russian
        if has_cyrillic:
            return 'ru'

        # Arabic: Arabic script (supports all Arabic ranges including extended)
        if has_arabic:
            return 'ar'

        # Korean: Hangul
        if has_korean:
            return 'ko'

        # Thai: Thai script
        if has_thai:
            return 'th'

        # Vietnamese: Latin with diacritics
        if has_vietnamese:
            return 'vi'

        # English detection - more sophisticated approach
        if has_latin:
            # Common English words that should always be detected as English
            common_english = [
                'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by',
                'hello', 'hi', 'yes', 'no', 'ok', 'okay', 'thanks', 'please', 'sorry',
                'what', 'where', 'when', 'why', 'how', 'who', 'which', 'that', 'this',
                'is', 'are', 'was', 'were', 'be', 'been', 'have', 'has', 'had', 'do', 'does', 'did',
                'can', 'could', 'should', 'would', 'will', 'shall', 'may', 'might', 'must'
            ]

            # Check if text contains common English words
            text_lower = text.lower()
            words = re.findall(r'\b[a-z]+\b', text_lower)
            if words and any(word in common_english for word in words):
                return 'en'

            # Check for English-like patterns
            if re.search(r'\b(ing|ed|er|est|ly|tion|sion)\b', text_lower):
                return 'en'

            # If text contains only basic Latin chars + numbers + punctuation and is not obviously other language
            if re.match(r'^[a-zA-Z0-9\s\.,\!\?\-@#$%&*()_+=\[\]{}|\\:";\'<>/`~]+$', text):
                # Exclude common non-English patterns
                if not re.search(r'\b(bon|jour|mer|ci|oui|non|je|tu|il|elle|nous|vous|ils|elles)\b', text_lower):
                    if len(text.strip()) >= 2:  # At least 2 characters
                        return 'en'

        return None

    except LangDetectException:
        logger.warning(f"Language detection failed for: {text[:50]}...")
        # Fallback to heuristic detection using same logic as above
        has_cyrillic = bool(re.search(r'[а-яё]', text.lower()))
        has_latin = bool(re.search(r'[a-zA-Z]', text))
        has_arabic = bool(re.search(r'[\u0600-\u06ff\u0750-\u077f\u08a0-\u08ff\ufb50-\ufdff\ufe70-\ufeff]', text))
        has_korean = bool(re.search(r'[가-힣\u1100-\u11ff\u3130-\u318f\uac00-\ud7af]', text))
        has_thai = bool(re.search(r'[\u0e00-\u0e7f]', text))
        has_vietnamese = bool(re.search(r'[àáảãạầấẩẫậèéẻẽẹềếểễệìíỉĩịòóỏõọồốổỗộùúủũụừứửữựỳýỷỹỵđĐ]', text))

        script_count = sum([has_cyrillic, has_latin, has_arabic, has_korean, has_thai, has_vietnamese])
        if script_count > 1:
            return None

        if has_cyrillic:
            return 'ru'
        elif has_arabic:
            return 'ar'
        elif has_korean:
            return 'ko'
        elif has_thai:
            return 'th'
        elif has_vietnamese:
            return 'vi'
        elif has_latin and len(text.strip()) >= 2:
            # Simple fallback for English - only for basic text
            if re.match(r'^[a-zA-Z0-9\s\.,\!\?\-]+$', text):
                return 'en'
        return None