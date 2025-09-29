"""
Translation service with text translation and voice response capabilities
"""
import asyncio
import hashlib
import logging
import shutil
import tempfile
from pathlib import Path
from typing import Dict, Set, Optional
from aiogram.types import Message, FSInputFile
from openai import AsyncOpenAI

from ..core.app import openai_client, config, audit_logger
from ..core.constants import SUPPORTED_LANGUAGES
from ..core.cache import get_translation_cache, get_persistent_tts_cache
from ..services.analytics import (
    is_user_disabled, update_user_activity, get_user_preferences,
    is_voice_replies_enabled, increment_voice_responses
)
from ..services.language import detect_language
from ..utils.formatting import escape_markdown

logger = logging.getLogger(__name__)

# Get cache instances
translation_cache = get_translation_cache()
persistent_tts_cache = get_persistent_tts_cache()


async def translate_text(text: str, source_lang: str, target_langs: Set[str]) -> Dict[str, str]:
    """Translate text to target languages with retry logic"""
    if source_lang in target_langs:
        target_langs = target_langs - {source_lang}

    if not target_langs:
        return {}

    # Check cache first
    cache_key = hashlib.md5(f"{text}:{source_lang}:{sorted(target_langs)}".encode()).hexdigest()
    if cache_key in translation_cache:
        logger.info(f"Cache hit for translation: {text[:50]}...")
        return translation_cache[cache_key]

    target_names = [SUPPORTED_LANGUAGES[lang]["name"] for lang in target_langs]
    prompt = f"""Translate this {SUPPORTED_LANGUAGES[source_lang]["name"]} text into {', '.join(target_names)}.

Provide only the translations, one per line:
{chr(10).join(f'{SUPPORTED_LANGUAGES[lang]["name"]}: [translation]' for lang in target_langs)}

Text: {text}"""

    for attempt in range(config.translation.max_retries):
        try:
            response = await openai_client.chat.completions.create(
                model=config.openai.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=config.translation.max_tokens,
                temperature=0.3
            )

            content = response.choices[0].message.content.strip()
            translations = {}

            for line in content.split('\n'):
                if ':' in line:
                    lang_name, translation = line.split(':', 1)
                    lang_name = lang_name.strip()
                    translation = translation.strip()

                    for code, info in SUPPORTED_LANGUAGES.items():
                        if info["name"] == lang_name and code in target_langs:
                            translations[code] = translation
                            break

            # Cache successful translations
            translation_cache[cache_key] = translations
            logger.info(f"Translation cached for: {text[:50]}...")
            return translations

        except Exception as e:
            logger.error(f"OpenAI API error (attempt {attempt + 1}): {e}")
            if attempt < config.translation.max_retries - 1:
                await asyncio.sleep(config.translation.retry_delay_base ** attempt)
                continue
            return {}


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
                await message.reply_voice(voice_input, caption=caption)

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


async def process_translation(message: Message, text: str, source_type: str = "text"):
    """Common translation processing for text and voice"""
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
            "🇯🇵 Japanese: \"こんにちは、元気ですか？\"\n"
            "🇰🇷 Korean: \"안녕하세요, 어떻게 지내세요?\"\n"
            "🇻🇳 Vietnamese: \"Xin chào, bạn khỏe không?\"\n\n"
            "_Note: French, German, Spanish and other languages are not yet supported._",
            parse_mode="Markdown"
        )
        return

    target_langs = await get_user_preferences(message.from_user.id)
    if source_lang in target_langs:
        target_langs = target_langs - {source_lang}

    if not target_langs:
        all_langs = set(SUPPORTED_LANGUAGES.keys())
        target_langs = all_langs - {source_lang}

    try:
        # Send instant status message
        status_msg = await message.reply("🔄 Translating...")

        # Start translation
        translations = await translate_text(text, source_lang, target_langs)

        # Delete status message
        try:
            await status_msg.delete()
        except:
            pass  # Ignore if deletion fails

        if not translations:
            await message.reply("❌ Translation failed. Please try again.")
            return

        # Send source info for voice messages
        if source_type == "voice":
            source_info = SUPPORTED_LANGUAGES[source_lang]
            # Truncate long transcriptions for display
            max_len = config.translation.display_truncate_length
            display_text = text if len(text) <= max_len else text[:max_len-3] + "..."
            escaped_text = escape_markdown(display_text)
            await message.reply(
                f"🎤 {source_info['flag']} Transcribed ({source_info['name']}):\n"
                f"_{escaped_text}_",
                parse_mode="Markdown"
            )

        # Send translations
        for lang_code, translation in translations.items():
            lang_info = SUPPORTED_LANGUAGES[lang_code]
            response = f"{lang_info['flag']} {lang_info['name']}:\n{translation}"
            await message.reply(response)

        # Generate and send voice response if enabled (PARALLEL TTS)
        if await is_voice_replies_enabled(user_id) and translations:
            await generate_parallel_voice_responses(message, user_id, translations)

    except Exception as e:
        logger.error(f"Translation error: {e}")
        try:
            await status_msg.delete()
        except:
            pass
        await message.reply("❌ An error occurred. Please try again.")