import asyncio
import logging
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Dict, Set, Optional, List
from cachetools import TTLCache
import hashlib


import re
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, User
from dotenv import load_dotenv
from langdetect import detect, LangDetectException
from openai import AsyncOpenAI

# Load environment variables
load_dotenv()

# Configure logging with proper level
log_level = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, log_level),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
    ]
)
logger = logging.getLogger(__name__)

# Create audit logger for admin actions
audit_logger = logging.getLogger("audit")
audit_logger.setLevel(logging.INFO)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")
OPENAI_TTS_MODEL = os.getenv("OPENAI_TTS_MODEL", "tts-1")
OPENAI_TTS_VOICE = os.getenv("OPENAI_TTS_VOICE", "alloy")
ADMIN_USER_ID = os.getenv("ADMIN_USER_ID")

if not TELEGRAM_BOT_TOKEN or not OPENAI_API_KEY:
    raise ValueError("TELEGRAM_BOT_TOKEN and OPENAI_API_KEY must be set")

if ADMIN_USER_ID:
    ADMIN_IDS = {int(uid.strip()) for uid in ADMIN_USER_ID.split(',') if uid.strip().isdigit()}
else:
    ADMIN_IDS = set()
    logger.warning("No ADMIN_USER_ID configured - admin features disabled")

bot = Bot(token=TELEGRAM_BOT_TOKEN)
dp = Dispatcher()
openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)

# Load configuration
from .config import load_config
config = load_config()

# Initialize database manager
from .storage.database import DatabaseManager
db = DatabaseManager(config.database.path)

# Initialize response cache (TTL: 1 hour)
translation_cache = TTLCache(maxsize=1000, ttl=3600)
tts_cache = TTLCache(maxsize=500, ttl=1800)  # 30 min for audio

SUPPORTED_LANGUAGES = {
    "ru": {"name": "Russian", "flag": "🇷🇺"},
    "en": {"name": "English", "flag": "🇺🇸"},
    "th": {"name": "Thai", "flag": "🇹🇭"},
    "ja": {"name": "Japanese", "flag": "🇯🇵"},
    "ko": {"name": "Korean", "flag": "🇰🇷"},
    "vi": {"name": "Vietnamese", "flag": "🇻🇳"}
}

# === USER MANAGEMENT FUNCTIONS ===

async def get_user_analytics(user_id: int, user: Optional[User] = None) -> Dict:
    """Get or create user analytics entry from database"""
    user_profile = None
    if user:
        user_profile = {
            "username": user.username,
            "first_name": user.first_name,
            "last_name": user.last_name,
        }
    return await db.get_user_analytics(user_id, user_profile)

async def update_user_activity(user_id: int, user: Optional[User] = None):
    """Update user activity timestamp and message count"""
    analytics = await get_user_analytics(user_id, user)
    analytics["last_activity"] = datetime.now()
    analytics["message_count"] += 1

    # Update user profile if provided
    if user:
        analytics["user_profile"] = {
            "username": user.username,
            "first_name": user.first_name,
            "last_name": user.last_name,
        }

    # Save to database
    await db.update_user_analytics(user_id, analytics)

def is_admin(user_id: int) -> bool:
    """Check if user is admin"""
    return user_id in ADMIN_IDS

async def is_user_disabled(user_id: int) -> bool:
    """Check if user is disabled"""
    analytics = await get_user_analytics(user_id)
    return analytics["is_disabled"]

async def set_user_disabled(user_id: int, disabled: bool) -> bool:
    """Enable/disable user access (async)"""
    analytics = await get_user_analytics(user_id)
    analytics["is_disabled"] = disabled
    action = "disabled" if disabled else "enabled"
    audit_logger.info(f"ADMIN_ACTION: User {user_id} has been {action}")

    # Save to database
    await db.update_user_analytics(user_id, analytics)
    return not disabled

async def is_voice_replies_enabled(user_id: int) -> bool:
    """Check if user has voice replies enabled"""
    analytics = await get_user_analytics(user_id)
    return analytics["voice_replies_enabled"]

async def toggle_voice_replies(user_id: int) -> bool:
    """Toggle voice replies preference for user"""
    analytics = await get_user_analytics(user_id)
    analytics["voice_replies_enabled"] = not analytics["voice_replies_enabled"]
    enabled = analytics["voice_replies_enabled"]
    logger.info(f"User {user_id} voice replies {'enabled' if enabled else 'disabled'}")

    # Save to database
    await db.update_user_analytics(user_id, analytics)
    return enabled

async def increment_voice_responses(user_id: int):
    """Increment voice response counter for analytics"""
    analytics = await get_user_analytics(user_id)
    analytics["voice_responses_sent"] += 1
    await db.update_user_analytics(user_id, analytics)

async def get_user_preferences(user_id: int) -> Set[str]:
    """Get user's enabled translation languages from database"""
    return await db.get_user_preferences(user_id)

async def update_user_preference(user_id: int, lang_code: str) -> Set[str]:
    """Toggle language preference for user in database"""
    prefs = await get_user_preferences(user_id)
    if lang_code in prefs:
        prefs.discard(lang_code)
    else:
        prefs.add(lang_code)

    if not prefs:
        prefs.update(set(SUPPORTED_LANGUAGES.keys()))

    await db.update_user_preferences(user_id, prefs)
    return prefs

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
        has_japanese = bool(re.search(r'[\u3040-\u309f\u30a0-\u30ff\u4e00-\u9faf]', text))
        has_korean = bool(re.search(r'[가-힣\u1100-\u11ff\u3130-\u318f\uac00-\ud7af]', text))
        has_thai = bool(re.search(r'[\u0e00-\u0e7f]', text))
        has_vietnamese = bool(re.search(r'[àáảãạầấẩẫậèéẻẽẹềếểễệìíỉĩịòóỏõọồốổỗộùúủũụừứửữựỳýỷỹỵđĐ]', text))

        script_count = sum([has_cyrillic, has_latin, has_japanese, has_korean, has_thai, has_vietnamese])
        if script_count > 1:
            return None  # Mixed languages

        # Cyrillic script - Russian
        if has_cyrillic:
            return 'ru'

        # Japanese: Hiragana, Katakana, Kanji
        if has_japanese:
            return 'ja'

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
        has_japanese = bool(re.search(r'[\u3040-\u309f\u30a0-\u30ff\u4e00-\u9faf]', text))
        has_korean = bool(re.search(r'[가-힣\u1100-\u11ff\u3130-\u318f\uac00-\ud7af]', text))
        has_thai = bool(re.search(r'[\u0e00-\u0e7f]', text))
        has_vietnamese = bool(re.search(r'[àáảãạầấẩẫậèéẻẽẹềếểễệìíỉĩịòóỏõọồốổỗộùúủũụừứửữựỳýỷỹỵđĐ]', text))

        script_count = sum([has_cyrillic, has_latin, has_japanese, has_korean, has_thai, has_vietnamese])
        if script_count > 1:
            return None

        if has_cyrillic:
            return 'ru'
        elif has_japanese:
            return 'ja'
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

async def download_and_convert_audio(file_path: str, output_format: str = "wav") -> Path:
    """Download and convert audio file to specified format"""
    try:
        from pydub import AudioSegment
    except ImportError:
        raise ImportError("pydub is required for audio processing. Install with: pip install pydub")

    temp_dir = Path(tempfile.mkdtemp())

    try:
        # Download file from Telegram
        downloaded_file = await bot.download_file(file_path)

        # Save original file
        original_path = temp_dir / "original.ogg"
        with open(original_path, "wb") as f:
            f.write(downloaded_file.read())

        # Convert to target format using pydub
        audio = AudioSegment.from_file(original_path)

        # Optimize: skip conversion if already in optimal format
        if (audio.channels == 1 and
            audio.frame_rate == config.audio.input_sample_rate and
            output_format == "wav"):
            # Audio is already optimal, just rename
            converted_path = temp_dir / f"converted.{output_format}"
            original_path.rename(converted_path)
            logger.info(f"Audio already optimal, skipped conversion: {converted_path}")
        else:
            converted_path = temp_dir / f"converted.{output_format}"
            # Export with optimal settings for Whisper
            audio.export(
                converted_path,
                format=output_format,
                parameters=["-ac", "1", "-ar", str(config.audio.input_sample_rate)]  # mono, configured rate
            )
            logger.info(f"Audio converted: {original_path} -> {converted_path}")

        return converted_path

    except Exception as e:
        logger.error(f"Audio conversion failed: {e}")
        # Cleanup on error
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise

async def transcribe_audio(audio_path: Path) -> str:
    """Transcribe audio using OpenAI Whisper with retry logic"""
    for attempt in range(config.openai.max_retries):
        try:
            with open(audio_path, "rb") as audio_file:
                transcription = await openai_client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    language=None  # Auto-detect language
                )

            return transcription.text.strip()

        except Exception as e:
            logger.error(f"Whisper transcription error (attempt {attempt + 1}): {e}")
            if attempt < 2:
                await asyncio.sleep(2 ** attempt)
                continue
            raise

async def generate_tts_audio(text: str) -> Optional[Path]:
    """Generate TTS audio using OpenAI Audio API with retry logic"""
    if len(text) > config.tts.max_characters:
        logger.warning(f"TTS text too long ({len(text)} chars), max is {config.tts.max_characters}")
        return None

    # Check TTS cache first
    tts_cache_key = hashlib.md5(f"{text}:{config.tts.voice}:{config.tts.speed}".encode()).hexdigest()
    if tts_cache_key in tts_cache:
        logger.info(f"TTS cache hit for: {text[:50]}...")
        # Return cached file path (copy to new temp location)
        cached_path = tts_cache[tts_cache_key]
        if cached_path and cached_path.exists():
            temp_dir = Path(tempfile.mkdtemp())
            new_path = temp_dir / cached_path.name
            import shutil
            shutil.copy2(cached_path, new_path)
            return new_path

    temp_dir = Path(tempfile.mkdtemp())
    mp3_path = temp_dir / "tts_output.mp3"
    ogg_path = temp_dir / "tts_output.ogg"

    try:
        # Generate TTS audio with OpenAI
        for attempt in range(config.openai.max_retries):
            try:
                logger.info(f"Generating TTS audio (attempt {attempt + 1}) for text: {text[:50]}...")
                tts_start = datetime.now()

                response = await openai_client.audio.speech.create(
                    model=config.tts.model,
                    voice=config.tts.voice,
                    input=text,
                    speed=config.tts.speed
                )

                tts_duration = (datetime.now() - tts_start).total_seconds()
                logger.info(f"TTS generated in {tts_duration:.2f}s")

                # Save MP3 response
                with open(mp3_path, "wb") as f:
                    f.write(response.content)

                break

            except Exception as e:
                logger.error(f"TTS generation error (attempt {attempt + 1}): {e}")
                if attempt < 2 and ("429" in str(e) or "5" in str(e)[:1]):
                    await asyncio.sleep(2 ** attempt)
                    continue
                raise

        # Convert MP3 to OGG/Opus for Telegram using ffmpeg
        try:
            from pydub import AudioSegment
        except ImportError:
            raise ImportError("pydub is required for TTS audio processing")

        audio = AudioSegment.from_mp3(mp3_path)

        # Export as OGG/Opus for Telegram voice messages
        audio.export(
            ogg_path,
            format="ogg",
            codec="libopus",
            parameters=["-ac", "1", "-ar", str(config.audio.output_sample_rate)]  # mono, configured rate
        )

        logger.info(f"TTS audio converted: {mp3_path} -> {ogg_path}")

        # Cache successful TTS result
        tts_cache[tts_cache_key] = ogg_path
        logger.info(f"TTS cached for: {text[:50]}...")

        return ogg_path

    except Exception as e:
        logger.error(f"TTS processing failed: {e}")
        # Cleanup on error
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)
        return None

async def generate_parallel_voice_responses(message: Message, user_id: int, translations: Dict[str, str]):
    """Generate TTS responses in parallel for much faster processing"""
    import shutil
    from aiogram.types import FSInputFile

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

async def build_preferences_keyboard(user_id: int) -> InlineKeyboardMarkup:
    """Build inline keyboard for language preferences"""
    prefs = await get_user_preferences(user_id)
    buttons = []

    for lang_code, info in SUPPORTED_LANGUAGES.items():
        status = "✅" if lang_code in prefs else "❌"
        text = f"{status} {info['flag']} {info['name']}"
        buttons.append([InlineKeyboardButton(
            text=text,
            callback_data=f"toggle_{lang_code}"
        )])

    # Add voice replies toggle
    voice_enabled = await is_voice_replies_enabled(user_id)
    voice_status = "✅" if voice_enabled else "❌"
    voice_text = f"{voice_status} 🎤 Voice replies"
    buttons.append([InlineKeyboardButton(
        text=voice_text,
        callback_data="toggle_voice_replies"
    )])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


async def build_admin_dashboard_keyboard() -> InlineKeyboardMarkup:
    """Build admin dashboard keyboard (async)"""
    buttons = [
        [InlineKeyboardButton(text="🔄 Refresh", callback_data="admin_refresh")],
    ]

    # Get all users from database
    all_users = await db.get_all_users()
    for user_data in all_users:
        user_id = user_data["user_id"]
        profile = user_data["user_profile"]
        raw_username = profile["username"] or profile["first_name"] or f"User {user_id}"
        # Limit button text length to prevent callback_data issues
        button_username = raw_username[:15] + "..." if len(raw_username) > 15 else raw_username
        status = "🔴" if user_data["is_disabled"] else "🟢"

        if user_data["is_disabled"]:
            buttons.append([InlineKeyboardButton(
                text=f"✅ Enable {button_username}",
                callback_data=f"admin_enable_{user_id}"
            )])
        else:
            buttons.append([InlineKeyboardButton(
                text=f"❌ Disable {button_username}",
                callback_data=f"admin_disable_{user_id}"
            )])

    return InlineKeyboardMarkup(inline_keyboard=buttons)

def escape_markdown(text: str) -> str:
    """Escape special Markdown characters"""
    special_chars = ["_", "*", "[", "]", "(", ")", "~", "`", ">", "#", "+", "-", "=", "|", "{", "}", ".", "!"]
    for char in special_chars:
        text = text.replace(char, f"\\{char}")
    return text


async def format_admin_dashboard() -> str:
    """Format admin dashboard text (async)"""
    all_users = await db.get_all_users()

    total_users = len(all_users)
    active_users = sum(1 for u in all_users if not u["is_disabled"])
    disabled_users = total_users - active_users
    voice_enabled_users = sum(1 for u in all_users if u["voice_replies_enabled"])
    total_voice_responses = sum(u["voice_responses_sent"] for u in all_users)

    text = (
        "🔧 Admin Dashboard\n\n"
        f"Total Users: {total_users}\n"
        f"Active: {active_users} | Disabled: {disabled_users}\n"
        f"Voice Replies: {voice_enabled_users} users | {total_voice_responses} sent\n\n"
        "User Summary:\n"
    )

    for user_data in sorted(all_users, key=lambda x: x["user_id"]):
        user_id = user_data["user_id"]
        profile = user_data["user_profile"]
        raw_username = profile["username"] or profile["first_name"] or f"User {user_id}"
        username = escape_markdown(raw_username)
        status = "🔴 Disabled" if user_data["is_disabled"] else "🟢 Active"
        prefs = escape_markdown(", ".join(user_data["preferred_targets"]))
        last_activity = user_data["last_activity"].strftime("%Y-%m-%d %H:%M")
        msg_count = user_data["message_count"]
        voice_replies = "🎤 ON" if user_data["voice_replies_enabled"] else "🎤 OFF"
        voice_sent = user_data["voice_responses_sent"]

        text += (
            f"\n{username} ({user_id})\n"
            f"Status: {status}\n"
            f"Languages: {prefs}\n"
            f"Messages: {msg_count} | Voice: {voice_replies} ({voice_sent} sent)\n"
            f"Last: {last_activity}\n"
        )

    return text

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
            "🇰🇷 Korean: \"안녕하세요, 어떻게 지내세요?\"\n\n"
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

@dp.message(Command("start"))
async def start_handler(message: Message):
    """Welcome message with instructions"""
    user_id = message.from_user.id

    # Check if user is disabled
    if await is_user_disabled(user_id):
        audit_logger.warning(f"BLOCKED_ACCESS: Disabled user {user_id} attempted /start")
        await message.reply(
            "❌ Access disabled. Contact support if you believe this is an error."
        )
        return

    # Update user activity
    await update_user_activity(user_id, message.from_user)

    text = (
        "🌍 **Translation Bot**\n\n"
        "I translate between 6 languages: 🇷🇺 Russian, 🇺🇸 English, 🇹🇭 Thai, 🇯🇵 Japanese, 🇰🇷 Korean, and 🇻🇳 Vietnamese!\n\n"
        "**How it works:**\n"
        "• Send text or voice messages in supported languages\n"
        "• I'll detect the language and translate to your enabled targets\n"
        "• Use /menu to customize which languages you want\n\n"
        "**Voice messages:** Send voice notes and I'll transcribe + translate!\n\n"
        "**Default:** I translate to all other languages\n"
        "Try sending: \"Hello, how are you?\" or \"こんにちは\" or \"Привет!\" or \"Xin chào!\""
    )

    # Add quick menu button
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚙️ Menu", callback_data="show_menu")]
    ])

    await message.reply(text, parse_mode="Markdown", reply_markup=keyboard)

@dp.message(Command("menu"))
async def menu_handler(message: Message):
    """Show language preferences menu"""
    user_id = message.from_user.id

    # Check if user is disabled
    if await is_user_disabled(user_id):
        audit_logger.warning(f"BLOCKED_ACCESS: Disabled user {user_id} attempted /menu")
        await message.reply(
            "❌ Access disabled. Contact support if you believe this is an error."
        )
        return

    # Update user activity
    await update_user_activity(user_id, message.from_user)

    prefs = await get_user_preferences(user_id)
    enabled = [SUPPORTED_LANGUAGES[lang]["name"] for lang in prefs]

    text = (
        "⚙️ **Translation Preferences**\n\n"
        f"**Currently enabled:** {', '.join(enabled)}\n\n"
        "Toggle languages below:"
    )

    try:
        keyboard = await build_preferences_keyboard(user_id)
    except Exception as e:
        logger.error(f"Error building preferences keyboard: {e}")
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Settings", callback_data="menu")]])
    await message.reply(text, reply_markup=keyboard, parse_mode="Markdown")

@dp.message(Command("admin"))
async def admin_handler(message: Message):
    """Show admin dashboard (admin only)"""
    user_id = message.from_user.id

    if not is_admin(user_id):
        audit_logger.warning(f"UNAUTHORIZED_ACCESS: Non-admin user {user_id} attempted to access /admin")
        await message.reply("❌ Access denied. Admin privileges required.")
        return

    audit_logger.info(f"ADMIN_ACCESS: Admin {user_id} accessed dashboard")

    try:
        text = await format_admin_dashboard()
    except Exception as e:
        logger.error(f"Error formatting admin dashboard: {e}")
        text = "❌ Error loading dashboard data"
    try:
        keyboard = await build_admin_dashboard_keyboard()
    except Exception as e:
        logger.error(f"Error building admin keyboard: {e}")
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔄 Refresh", callback_data="admin_refresh")]])

    await message.reply(text, reply_markup=keyboard)

@dp.callback_query(F.data == "show_menu")
async def show_menu_callback(callback: CallbackQuery):
    """Handle show menu button press"""
    user_id = callback.from_user.id

    # Check if user is disabled
    if await is_user_disabled(user_id):
        await callback.answer("❌ Access disabled", show_alert=True)
        return

    # Update user activity
    await update_user_activity(user_id, callback.from_user)

    prefs = await get_user_preferences(user_id)
    enabled = [SUPPORTED_LANGUAGES[lang]["name"] for lang in prefs]

    text = (
        "⚙️ **Language Preferences**\n\n"
        f"**Currently enabled:** {', '.join(enabled) if enabled else 'None'}\n\n"
        "Select languages to enable/disable for translation:"
    )

    keyboard = await build_preferences_keyboard(user_id)

    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=keyboard)
    await callback.answer()

@dp.callback_query(F.data.startswith("toggle_"))
async def toggle_preference(callback: CallbackQuery):
    """Handle language preference and voice replies toggle"""
    user_id = callback.from_user.id
    toggle_data = callback.data.split("_", 1)[1]  # Get everything after "toggle_"

    # Check if user is disabled
    if await is_user_disabled(user_id):
        await callback.answer("❌ Access disabled", show_alert=True)
        return

    # Update user activity
    await update_user_activity(user_id, callback.from_user)

    if toggle_data == "voice_replies":
        # Handle voice replies toggle
        voice_enabled = await toggle_voice_replies(user_id)
        prefs = await get_user_preferences(user_id)
        enabled = [SUPPORTED_LANGUAGES[lang]["name"] for lang in prefs]

        status_msg = "enabled" if voice_enabled else "disabled"
        callback_msg = f"✅ Voice replies {status_msg}"
    else:
        # Handle language preference toggle
        lang_code = toggle_data
        if lang_code not in SUPPORTED_LANGUAGES:
            await callback.answer("Invalid language")
            return

        prefs = await update_user_preference(user_id, lang_code)
        enabled = [SUPPORTED_LANGUAGES[lang]["name"] for lang in prefs]
        callback_msg = f"✅ Updated preferences: {', '.join(enabled)}"

    keyboard = await build_preferences_keyboard(user_id)

    text = (
        "⚙️ **Translation Preferences**\n\n"
        f"**Currently enabled:** {', '.join(enabled)}\n\n"
        "Toggle languages below:"
    )

    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")
    await callback.answer(callback_msg)

@dp.callback_query(F.data.startswith("admin_"))
async def admin_callback(callback: CallbackQuery):
    """Handle admin dashboard callbacks"""
    user_id = callback.from_user.id

    if not is_admin(user_id):
        await callback.answer("❌ Access denied", show_alert=True)
        return

    action_parts = callback.data.split("_")
    action = action_parts[1]

    if action == "refresh":
        audit_logger.info(f"ADMIN_ACTION: Admin {user_id} refreshed dashboard")
        text = await format_admin_dashboard()
        keyboard = await build_admin_dashboard_keyboard()
        try:
            await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")
            await callback.answer("✅ Dashboard refreshed")
        except Exception as e:
            if "message is not modified" in str(e):
                await callback.answer("✅ Dashboard already up to date")
            else:
                logger.error(f"Error refreshing dashboard: {e}"); await callback.answer("❌ Error refreshing dashboard")

    elif action in ["enable", "disable"]:
        target_user_id = int(action_parts[2])
        disabled = action == "disable"

        # Update user status
        success = await set_user_disabled(target_user_id, disabled)
        action_text = "disabled" if disabled else "enabled"

        audit_logger.info(f"ADMIN_ACTION: Admin {user_id} {action_text} user {target_user_id}")

        # Refresh dashboard
        text = await format_admin_dashboard()
        keyboard = await build_admin_dashboard_keyboard()
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")
        await callback.answer(f"✅ User {target_user_id} {action_text}")

@dp.message(F.voice | F.audio)
async def voice_handler(message: Message):
    """Handle voice and audio messages"""
    import shutil

    user_id = message.from_user.id

    # Check if user is disabled
    if await is_user_disabled(user_id):
        audit_logger.warning(f"BLOCKED_ACCESS: Disabled user {user_id} attempted voice message")
        await message.reply(
            "❌ Access disabled. Contact support if you believe this is an error."
        )
        return

    status_msg = await message.reply("🎤 Processing voice message...")
    temp_dir = None

    try:
        # Get file info
        if message.voice:
            file_info = await bot.get_file(message.voice.file_id)
            duration = message.voice.duration
        elif message.audio:
            file_info = await bot.get_file(message.audio.file_id)
            duration = message.audio.duration
        else:
            await status_msg.edit_text("❌ Unsupported audio format.")
            return

        # Check duration using config
        max_duration = config.audio.max_duration_seconds
        if duration and duration > max_duration:
            minutes = max_duration // 60
            await status_msg.edit_text(f"❌ Audio too long. Please send messages under {minutes} minutes.")
            return

        await status_msg.edit_text("🔄 Downloading audio...")

        # Check if pydub and ffmpeg are available
        try:
            # Download and convert audio
            audio_path = await download_and_convert_audio(file_info.file_path)
            temp_dir = audio_path.parent
        except ImportError as e:
            await status_msg.edit_text("❌ Audio processing not available. pydub is required.")
            logger.error(f"pydub import error: {e}")
            return
        except Exception as e:
            if "ffmpeg" in str(e).lower():
                await status_msg.edit_text("❌ Audio processing requires FFmpeg. Please install FFmpeg first.")
                logger.error(f"FFmpeg error: {e}")
                return
            else:
                await status_msg.edit_text("❌ Audio processing failed. Please try again.")
                logger.error(f"Audio processing error: {e}")
                return

        await status_msg.edit_text("🗣️ Transcribing audio...")

        # Transcribe using Whisper
        try:
            transcription = await transcribe_audio(audio_path)
        except Exception as e:
            await status_msg.edit_text("❌ Could not transcribe audio. Please try again with clearer speech.")
            logger.error(f"Transcription error: {e}")
            return

        if not transcription.strip():
            await status_msg.edit_text("❌ Could not transcribe audio. Please try again with clearer speech.")
            return

        await status_msg.delete()

        # Process translation using existing logic
        await process_translation(message, transcription, source_type="voice")

    except Exception as e:
        logger.error(f"Voice processing error: {e}")
        try:
            await status_msg.edit_text("❌ Couldn't process voice message. Please try again.")
        except:
            await message.reply("❌ Couldn't process voice message. Please try again.")

    finally:
        # Cleanup temporary files
        if temp_dir and temp_dir.exists():
            try:
                shutil.rmtree(temp_dir, ignore_errors=True)
                logger.info(f"Cleaned up temp directory: {temp_dir}")
            except Exception as e:
                logger.warning(f"Failed to cleanup temp directory {temp_dir}: {e}")

@dp.message(F.text)
async def text_handler(message: Message):
    """Handle text translation"""
    user_id = message.from_user.id
    text = message.text.strip()

    # Check if user is disabled
    if await is_user_disabled(user_id):
        audit_logger.warning(f"BLOCKED_ACCESS: Disabled user {user_id} attempted text message: {text[:50]}...")
        await message.reply(
            "❌ Access disabled. Contact support if you believe this is an error."
        )
        return

    if not text:
        await message.reply("Please send a non-empty message.")
        return

    await process_translation(message, text, source_type="text")

async def main():
    """Start the bot"""
    logger.info("Starting Translation Bot with voice support...")

    # Initialize database
    try:
        await db.init_db()
        logger.info("Database initialized successfully")

        # Add Vietnamese to existing users
        await db.add_vietnamese_to_existing_users()
        logger.info("Vietnamese language added to existing users")
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        return

    try:
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"Bot error: {e}")
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())