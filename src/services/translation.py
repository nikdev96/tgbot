"""
Translation service with text translation and voice response capabilities

Features:
- Adaptive localization (not literal translation)
- Auto style detection (casual/formal/neutral)
- Cultural adaptation with glossary support
- Context-aware translations
"""
import asyncio
import hashlib
import logging
import re
import shutil
import tempfile
import time
from pathlib import Path
from typing import AsyncGenerator, Dict, Set, Optional, Literal, Tuple
from aiogram.types import Message, FSInputFile
from aiogram.exceptions import TelegramBadRequest
from openai import AsyncOpenAI

from ..core.app import openai_client, config, audit_logger
from ..core.constants import SUPPORTED_LANGUAGES, DEFAULT_LANGUAGES
from ..core.cache import get_translation_cache, get_persistent_tts_cache, normalize_text_for_cache, increment_cache_stat
from ..services.analytics import (
    is_user_disabled, update_user_activity, get_user_preferences,
    is_voice_replies_enabled, increment_voice_responses
)
from ..services.language import detect_language
from ..services.model_manager import get_model_manager
from ..utils.formatting import escape_markdown

logger = logging.getLogger(__name__)

# Get cache instances
translation_cache = get_translation_cache()
persistent_tts_cache = get_persistent_tts_cache()

# Style detection and adaptation constants
TextStyle = Literal["casual", "formal", "neutral"]

STYLE_INSTRUCTIONS: Dict[str, str] = {
    "casual": "Use informal language, slang equivalents, keep the playful/friendly tone. Match casual expressions with natural equivalents in target language.",
    "formal": "Use formal language, polite forms, professional vocabulary. Maintain respectful tone appropriate for business or official contexts.",
    "neutral": "Use natural everyday language with balanced formality. Standard conversational tone."
}

# Casual text indicators
CASUAL_WORDS_RU = {'хах', 'ахах', 'блин', 'чё', 'ваще', 'круто', 'норм', 'лол', 'кек', 'пон', 'ок', 'окей', 'ага', 'угу', 'ну', 'чел', 'братан', 'бро'}
CASUAL_WORDS_EN = {'lol', 'lmao', 'omg', 'btw', 'gonna', 'wanna', 'gotta', 'yeah', 'nope', 'yep', 'cool', 'awesome', 'dude', 'bro', 'sup', 'hey'}
CASUAL_WORDS_TH = {'555', 'จ้า', 'ค่ะ', 'นะคะ', 'ชิมิ', 'อิอิ'}
CASUAL_WORDS_VI = {'haha', 'hihi', 'ơi', 'nhé', 'nha', 'á', 'ạ', 'dạ'}

ALL_CASUAL_WORDS = CASUAL_WORDS_RU | CASUAL_WORDS_EN | CASUAL_WORDS_TH | CASUAL_WORDS_VI

# Formal text indicators
FORMAL_WORDS_RU = {'уважаемый', 'уважаемая', 'господин', 'госпожа', 'прошу', 'благодарю', 'искренне', 'с уважением'}
FORMAL_WORDS_EN = {'dear', 'sincerely', 'regards', 'respectfully', 'kindly', 'hereby', 'pursuant', 'acknowledge'}
FORMAL_WORDS_TH = {'เรียน', 'กราบเรียน', 'ขอแสดงความนับถือ', 'ด้วยความเคารพ'}
FORMAL_WORDS_VI = {'kính', 'thưa', 'trân trọng', 'xin'}

ALL_FORMAL_WORDS = FORMAL_WORDS_RU | FORMAL_WORDS_EN | FORMAL_WORDS_TH | FORMAL_WORDS_VI


def detect_text_style(text: str) -> TextStyle:
    """Auto-detect text style for translation adaptation.

    Analyzes text for casual/formal indicators:
    - Casual: emojis, multiple punctuation, slang words, informal markers
    - Formal: proper punctuation, formal vocabulary, structured sentences
    - Neutral: balanced, everyday language

    Args:
        text: Text to analyze

    Returns:
        Detected style: "casual", "formal", or "neutral"
    """
    # Guard against None or empty text
    if not text or not text.strip():
        return "neutral"

    text_lower = text.lower()

    # Casual indicators
    casual_signs = [
        # Multiple punctuation marks (!! or ??)
        len(re.findall(r'[!?]{2,}', text)) > 0,
        # Emojis (common ranges)
        bool(re.search(r'[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF\U0001F1E0-\U0001F1FF\U00002702-\U000027B0\U0001F900-\U0001F9FF]', text)),
        # Casual words in any supported language
        any(word in text_lower for word in ALL_CASUAL_WORDS),
        # Russian-style emoticons ))) or (((
        text.count(')') > 2 or text.count('(') > 2,
        # Lowercase start (informal)
        text and text[0].islower() and len(text) > 3,
        # All caps words (HAHA, WOW)
        bool(re.search(r'\b[A-ZА-Я]{3,}\b', text)),
    ]

    # Formal indicators
    formal_signs = [
        # Proper sentence structure (capital start, period end)
        text and text[0].isupper() and text.rstrip().endswith('.'),
        # Formal vocabulary
        any(word in text_lower for word in ALL_FORMAL_WORDS),
        # Long text (usually more formal)
        len(text) > 200,
        # Structured dates or numbers
        bool(re.search(r'\d{2}[./]\d{2}[./]\d{4}', text)),
        # No emojis in long text
        len(text) > 50 and not re.search(r'[\U0001F600-\U0001F64F]', text),
    ]

    casual_score = sum(casual_signs)
    formal_score = sum(formal_signs)

    if casual_score >= 2:
        return "casual"
    if formal_score >= 2:
        return "formal"
    return "neutral"


STYLE_NOTES_COMPACT: Dict[str, str] = {
    "casual": "Informal, slang OK, playful tone.",
    "formal": "Formal, polite, professional vocabulary.",
    "neutral": "Natural conversational tone.",
}


def build_localization_prompt(
    text: str,
    source_lang: str,
    target_langs: Set[str],
    context: Optional[str] = None,
    style: Optional[TextStyle] = None
) -> str:
    """Build compact adaptive localization prompt with marker output format."""
    if source_lang not in SUPPORTED_LANGUAGES:
        raise ValueError(f"Unsupported source language: {source_lang}")

    valid_target_langs = {lang for lang in target_langs if lang in SUPPORTED_LANGUAGES}
    invalid_langs = target_langs - valid_target_langs
    if invalid_langs:
        logger.warning(f"Ignoring unsupported target languages: {invalid_langs}")

    if not valid_target_langs:
        raise ValueError(f"No valid target languages provided. Invalid: {target_langs}")

    if style is None:
        style = detect_text_style(text)

    target_langs_list = sorted(list(valid_target_langs))

    # Language-specific hints only for languages that need them
    lang_hints = []
    for lang in target_langs_list:
        if lang == "th":
            lang_hints.append("Thai: use ครับ/ค่ะ based on formality.")
        elif lang == "vi":
            lang_hints.append("Vietnamese: use appropriate pronouns.")

    hints_line = (" " + " ".join(lang_hints)) if lang_hints else ""
    context_line = f"\nContext: {context}" if context else ""
    langs_str = ", ".join(SUPPORTED_LANGUAGES[lang]["name"] for lang in target_langs_list)
    output_markers = "\n".join(
        f"[{lang.upper()}]translation[/{lang.upper()}]" for lang in target_langs_list
    )

    prompt = (
        f"Localize for native speakers. Style: {style}. Preserve meaning, tone, emojis.\n"
        f"{STYLE_NOTES_COMPACT[style]}{hints_line}{context_line}\n"
        f"Source: {SUPPORTED_LANGUAGES[source_lang]['name']} → {langs_str}\n\n"
        f"Output EXACTLY in this format (no JSON, no extra text):\n"
        f"{output_markers}\n\n"
        f"TEXT: {text}"
    )

    return prompt


def parse_marker_response(content: str, target_langs: Set[str]) -> Dict[str, str]:
    """Parse [XX]...[/XX] marker format from model response."""
    translations = {}
    for lang_code in target_langs:
        tag = lang_code.upper()
        start_tag = f"[{tag}]"
        end_tag = f"[/{tag}]"
        if start_tag in content and end_tag in content:
            start_idx = content.index(start_tag) + len(start_tag)
            end_idx = content.index(end_tag)
            translation = content[start_idx:end_idx].strip()
            if translation:
                translations[lang_code] = translation
    return translations


async def translate_text(text: str, source_lang: str, target_langs: Set[str], context: Optional[str] = None) -> Dict[str, str]:
    """Translate text to target languages with adaptive localization.

    Uses style-aware prompt for natural, culturally-adapted translations
    instead of literal word-for-word translation.

    Args:
        text: Text to translate
        source_lang: Source language code
        target_langs: Set of target language codes
        context: Optional previous messages context for better translation

    Returns:
        Dictionary mapping language codes to translated text
    """
    start_time = time.time()

    # Input validation
    if not text or not text.strip():
        logger.warning("Empty text provided for translation")
        return {}

    text = text.strip()

    if source_lang in target_langs:
        target_langs = target_langs - {source_lang}

    if not target_langs:
        return {}

    # Detect style early for logging
    style = detect_text_style(text)

    # Normalize text for better cache hits
    normalized_text = normalize_text_for_cache(text)

    # Check cache first (include context and style in cache key)
    context_hash = hashlib.md5(context.encode()).hexdigest()[:8] if context else ""
    cache_key = hashlib.md5(f"{normalized_text}:{source_lang}:{','.join(sorted(target_langs))}:{context_hash}:{style}".encode()).hexdigest()
    if cache_key in translation_cache:
        increment_cache_stat("translation", hit=True)
        elapsed_ms = (time.time() - start_time) * 1000
        logger.info(f"Translation: {source_lang}→{list(target_langs)}, chars={len(text)}, style={style}, time={elapsed_ms:.0f}ms, cached=True")
        return translation_cache[cache_key]

    # Track cache miss
    increment_cache_stat("translation", hit=False)

    # Build adaptive localization prompt
    prompt = build_localization_prompt(text, source_lang, target_langs, context, style)

    # Get current model from model manager
    model_manager = get_model_manager()
    current_model = model_manager.get_current_model()

    # Initialize content for error handling
    content = ""

    for attempt in range(config.translation.max_retries):
        try:
            response = await openai_client.chat.completions.create(
                model=current_model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=config.translation.max_tokens,
                temperature=0.3,
            )

            content = response.choices[0].message.content.strip()

            # Parse marker format response
            translations = parse_marker_response(content, target_langs)

            # Validate completeness
            missing_langs = target_langs - set(translations.keys())
            if missing_langs:
                logger.warning(f"Incomplete translation. Requested: {len(target_langs)}, Got: {len(translations)}, Missing: {missing_langs}")
                if not translations:
                    if attempt < config.translation.max_retries - 1:
                        await asyncio.sleep(config.translation.retry_delay_base ** attempt)
                        continue
                    return {}

            # Cache successful translations
            translation_cache[cache_key] = translations

            # Log translation metrics
            elapsed_ms = (time.time() - start_time) * 1000
            logger.info(
                f"Translation: {source_lang}→{list(target_langs)}, "
                f"chars={len(text)}, style={style}, "
                f"time={elapsed_ms:.0f}ms, cached=False, "
                f"model={current_model}"
            )
            return translations

        except Exception as e:
            logger.error(f"OpenAI API error (attempt {attempt + 1}): {e}")
            if attempt < config.translation.max_retries - 1:
                await asyncio.sleep(config.translation.retry_delay_base ** attempt)
                continue
            return {}


async def translate_text_stream(
    text: str,
    source_lang: str,
    target_langs: Set[str],
    context: Optional[str] = None
) -> AsyncGenerator[Tuple[str, str], None]:
    """Async generator that yields (lang_code, translation) as each language completes.

    On cache hit yields all translations immediately. On cache miss streams from
    the API and yields each language as its closing marker is received.
    """
    if not text or not text.strip():
        return

    text = text.strip()

    if source_lang in target_langs:
        target_langs = target_langs - {source_lang}

    if not target_langs:
        return

    style = detect_text_style(text)
    normalized_text = normalize_text_for_cache(text)
    context_hash = hashlib.md5(context.encode()).hexdigest()[:8] if context else ""
    cache_key = hashlib.md5(
        f"{normalized_text}:{source_lang}:{','.join(sorted(target_langs))}:{context_hash}:{style}".encode()
    ).hexdigest()

    if cache_key in translation_cache:
        increment_cache_stat("translation", hit=True)
        for lang_code, translation in translation_cache[cache_key].items():
            yield lang_code, translation
        return

    increment_cache_stat("translation", hit=False)

    prompt = build_localization_prompt(text, source_lang, target_langs, context, style)

    model_manager = get_model_manager()
    current_model = model_manager.get_current_model()

    start_time = time.time()
    buffer = ""
    found_langs: Set[str] = set()
    translations: Dict[str, str] = {}

    try:
        stream = await openai_client.chat.completions.create(
            model=current_model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=config.translation.max_tokens,
            temperature=0.3,
            stream=True,
        )

        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                buffer += chunk.choices[0].delta.content

            for lang_code in target_langs:
                if lang_code in found_langs:
                    continue
                tag = lang_code.upper()
                start_tag = f"[{tag}]"
                end_tag = f"[/{tag}]"
                if start_tag in buffer and end_tag in buffer:
                    start_idx = buffer.index(start_tag) + len(start_tag)
                    end_idx = buffer.index(end_tag)
                    translation = buffer[start_idx:end_idx].strip()
                    if translation:
                        found_langs.add(lang_code)
                        translations[lang_code] = translation
                        yield lang_code, translation

        if translations:
            translation_cache[cache_key] = translations

        elapsed_ms = (time.time() - start_time) * 1000
        missing = target_langs - found_langs
        if missing:
            logger.warning(f"Stream translation incomplete. Missing: {missing}")
        logger.info(
            f"Translation stream: {source_lang}→{list(target_langs)}, "
            f"chars={len(text)}, style={style}, "
            f"time={elapsed_ms:.0f}ms, model={current_model}"
        )

    except Exception as e:
        logger.error(f"Streaming translation error: {e}")
        missing = target_langs - found_langs
        if missing:
            try:
                fallback = await translate_text(text, source_lang, missing, context)
                for lang_code, translation in fallback.items():
                    if lang_code not in found_langs:
                        translations[lang_code] = translation
                        yield lang_code, translation
            except Exception as fb_err:
                logger.error(f"Fallback translation error: {fb_err}")


async def generate_tts_audio(text: str) -> Optional[Path]:
    """Generate TTS audio file using OpenAI with persistent caching"""
    # Check persistent cache first
    cached_path = persistent_tts_cache.get(text)
    if cached_path:
        # Return a copy for temporary use
        temp_dir = Path(tempfile.mkdtemp())
        temp_path = temp_dir / f"tts_copy_{cached_path.name}"
        shutil.copy2(cached_path, temp_path)
        return temp_path

    try:
        # Generate speech using OpenAI TTS
        response = await openai_client.audio.speech.create(
            model=config.tts.model,
            voice=config.tts.voice,
            input=text,
            response_format="opus"  # Better compression for Telegram
        )

        # Save to persistent cache
        cached_path = persistent_tts_cache.set(text, response.content)

        # Return a copy for temporary use
        temp_dir = Path(tempfile.mkdtemp())
        temp_path = temp_dir / f"tts_copy_{cached_path.name}"
        shutil.copy2(cached_path, temp_path)

        logger.info(f"TTS generated and cached for: {text[:50]}...")
        return temp_path

    except Exception as e:
        logger.error(f"TTS generation error: {e}")
        return None


async def generate_parallel_voice_responses(message: Message, user_id: int, translations: Dict[str, str]):
    """Generate TTS responses in parallel for much faster processing"""
    # Filter out too long translations
    valid_translations = {}
    for lang_code, translation in translations.items():
        if len(translation) > config.tts.max_characters:
            lang_info = SUPPORTED_LANGUAGES[lang_code]
            await message.reply(f"🎤 {lang_info['flag']} Голосовой ответ на {lang_info['name']} слишком длинный.")
        else:
            valid_translations[lang_code] = translation

    if not valid_translations:
        return

    # Generate all TTS audio files in parallel
    async def generate_single_tts(lang_code: str, translation: str):
        try:
            tts_audio_path = await generate_tts_audio(translation)
            return lang_code, tts_audio_path, None
        except Exception as e:
            return lang_code, None, e

    # Start all TTS generations in parallel
    tts_tasks = [
        generate_single_tts(lang_code, translation)
        for lang_code, translation in valid_translations.items()
    ]

    # Wait for all TTS generations to complete
    tts_results = await asyncio.gather(*tts_tasks, return_exceptions=True)

    # Send voice messages and cleanup
    temp_dirs_to_cleanup = []
    successful_responses = 0

    for result in tts_results:
        if isinstance(result, Exception):
            logger.error(f"TTS parallel generation error: {result}")
            continue

        lang_code, tts_audio_path, error = result

        if error:
            lang_info = SUPPORTED_LANGUAGES[lang_code]
            logger.error(f"TTS error for user {user_id} in {lang_code}: {error}")
            await message.reply(f"🎤 Ошибка создания голосового ответа на {lang_info['name']}.")
            continue

        if tts_audio_path:
            try:
                temp_dirs_to_cleanup.append(tts_audio_path.parent)

                # Create caption with language name
                lang_info = SUPPORTED_LANGUAGES[lang_code]
                caption = f"{lang_info['flag']} {lang_info['name']}"

                # Send voice message
                voice_input = FSInputFile(tts_audio_path, filename=f"voice_{lang_code}.ogg")
                await message.answer_voice(voice_input, caption=caption)

                successful_responses += 1
                logger.info(f"Voice response sent to user {user_id} in {lang_code}")

            except Exception as e:
                lang_info = SUPPORTED_LANGUAGES[lang_code]
                logger.error(f"Voice message send error for {lang_code}: {e}")
                await message.reply(f"🎤 Ошибка отправки голосового ответа на {lang_info['name']}.")

    # Cleanup all temp directories
    for temp_dir in temp_dirs_to_cleanup:
        if temp_dir and temp_dir.exists():
            try:
                shutil.rmtree(temp_dir, ignore_errors=True)
            except Exception as e:
                logger.warning(f"Failed to cleanup TTS temp directory {temp_dir}: {e}")

    # Update analytics for successful responses
    if successful_responses > 0:
        await increment_voice_responses(user_id)
        logger.info(f"Parallel voice responses completed for user {user_id}: {successful_responses} sent")


async def process_translation(message: Message, text: str, source_type: str = "text", early_response_msg=None):
    """Common translation processing for text and voice with early response support"""
    from ..core.app import db

    user_id = message.from_user.id

    # Check if user is disabled
    if await is_user_disabled(user_id):
        audit_logger.warning(f"BLOCKED_ACCESS: Disabled user {user_id} attempted translation: {text[:50]}...")
        await message.reply(
            "❌ Access disabled. Contact support if you believe this is an error."
        )
        return

    # Check input text length
    if len(text) > config.translation.max_input_characters:
        max_chars = config.translation.max_input_characters
        await message.reply(
            f"❌ Text too long ({len(text)} characters). Maximum allowed: {max_chars} characters."
        )
        return

    # Update user activity
    await update_user_activity(user_id, message.from_user)

    source_lang = detect_language(text)
    if not source_lang:
        await message.reply(
            "❌ Language not supported or couldn't be detected.\n\n"
            "**Supported languages:**\n"
            "🇷🇺 Russian: \"Привет, как дела?\"\n"
            "🇺🇸 English: \"Hello, how are you?\"\n"
            "🇹🇭 Thai: \"สวัสดี เป็นอย่างไรบ้าง\"\n"
            "🇸🇦 Arabic: \"مرحبا، كيف حالك؟\"\n"
            "🇨🇳 Chinese: \"你好，你好吗？\"\n"
            "🇻🇳 Vietnamese: \"Xin chào, bạn khỏe không?\"\n\n"
            "_Note: French, German, Spanish and other languages are not yet supported._",
            parse_mode="Markdown"
        )
        return

    target_langs = await get_user_preferences(message.from_user.id)

    # Filter out invalid language codes
    target_langs = {lang for lang in target_langs if lang in SUPPORTED_LANGUAGES}

    # If user has no preferences, use default languages
    if not target_langs:
        target_langs = DEFAULT_LANGUAGES - {source_lang}
    else:
        # Remove source language from user preferences
        if source_lang in target_langs:
            target_langs = target_langs - {source_lang}

        # If after removing source lang there are no targets, don't translate at all
        if not target_langs:
            await message.reply(
                f"✅ Message detected in {SUPPORTED_LANGUAGES[source_lang]['name']}.\n\n"
                f"💡 You only have {SUPPORTED_LANGUAGES[source_lang]['name']} selected for translation.\n"
                f"Use /settings to add more languages."
            )
            return

    try:
        # Get context from previous messages (only for private chats)
        context = None
        if message.chat.type == "private":
            try:
                context_messages = await db.get_user_context(user_id, limit=3)
                if context_messages:
                    context_parts = []
                    for msg in context_messages:
                        lang_info = SUPPORTED_LANGUAGES.get(msg["language"], {"name": msg["language"]})
                        context_parts.append(f"[{lang_info['name']}]: {msg['text']}")
                    context = "\n".join(context_parts)
            except Exception as e:
                logger.warning(f"Could not get context for user {user_id}: {e}")

        if early_response_msg is None:
            status_msg = await message.answer("🔄 Translating...")
        else:
            status_msg = early_response_msg

        translations = await translate_text(text, source_lang, target_langs, context=context)

        await status_msg.delete()

        # Save message to context history
        try:
            target_langs_str = ",".join(sorted(target_langs))
            await db.save_user_message(user_id, text, source_lang, target_langs_str)
        except Exception as e:
            logger.warning(f"Could not save message to context: {e}")

        if not translations:
            await message.reply("❌ Translation failed. Please try again.")
            return

        # For voice without early_response_msg: show transcription now
        if source_type == "voice" and early_response_msg is None:
            source_info = SUPPORTED_LANGUAGES[source_lang]
            max_len = config.translation.display_truncate_length
            display_text = text if len(text) <= max_len else text[:max_len-3] + "..."
            escaped_text = escape_markdown(display_text)
            await message.answer(
                f"🎤 {source_info['flag']} Transcribed ({source_info['name']}):\n"
                f"_{escaped_text}_",
                parse_mode="Markdown"
            )

        for lang_code, translation in translations.items():
            await message.answer(translation)

        # Generate and send voice response if enabled (PARALLEL TTS)
        if await is_voice_replies_enabled(user_id) and translations:
            await generate_parallel_voice_responses(message, user_id, translations)

    except Exception as e:
        logger.error(f"Translation error: {e}")
        if early_response_msg:
            try:
                await early_response_msg.delete()
            except TelegramBadRequest:
                pass
        await message.reply("❌ An error occurred. Please try again.")