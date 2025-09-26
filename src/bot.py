import asyncio
import logging
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Dict, Set, Optional, List


import re
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, User
from dotenv import load_dotenv
from langdetect import detect, LangDetectException
from openai import AsyncOpenAI

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
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

SUPPORTED_LANGUAGES = {
    "ru": {"name": "Russian", "flag": "🇷🇺"},
    "en": {"name": "English", "flag": "🇺🇸"},
    "th": {"name": "Thai", "flag": "🇹🇭"},
    "ja": {"name": "Japanese", "flag": "🇯🇵"},
    "ko": {"name": "Korean", "flag": "🇰🇷"}
}

# TODO: Replace with persistent storage (database/redis/SQLite)
user_preferences: Dict[int, Set[str]] = {}

# User analytics storage - TODO: Move to persistent storage (SQLite/Redis)
user_analytics: Dict[int, Dict] = {}

def get_user_analytics(user_id: int, user: Optional[User] = None) -> Dict:
    """Get or create user analytics entry"""
    if user_id not in user_analytics:
        user_analytics[user_id] = {
            "is_disabled": False,
            "preferred_targets": {"en"},  # Only English enabled by default
            "voice_replies_enabled": False,
            "message_count": 0,
            "voice_responses_sent": 0,
            "last_activity": datetime.now(),
            "user_profile": {
                "username": user.username if user else None,
                "first_name": user.first_name if user else None,
                "last_name": user.last_name if user else None,
            } if user else {"username": None, "first_name": None, "last_name": None}
        }
    return user_analytics[user_id]

def update_user_activity(user_id: int, user: Optional[User] = None):
    """Update user activity timestamp and message count"""
    analytics = get_user_analytics(user_id, user)
    analytics["last_activity"] = datetime.now()
    analytics["message_count"] += 1

    # Update user profile if provided
    if user:
        analytics["user_profile"] = {
            "username": user.username,
            "first_name": user.first_name,
            "last_name": user.last_name,
        }

def is_admin(user_id: int) -> bool:
    """Check if user is admin"""
    return user_id in ADMIN_IDS

def is_user_disabled(user_id: int) -> bool:
    """Check if user is disabled"""
    analytics = get_user_analytics(user_id)
    return analytics["is_disabled"]

def set_user_disabled(user_id: int, disabled: bool) -> bool:
    """Enable/disable user access"""
    analytics = get_user_analytics(user_id)
    analytics["is_disabled"] = disabled
    action = "disabled" if disabled else "enabled"
    audit_logger.info(f"ADMIN_ACTION: User {user_id} has been {action}")
    return not disabled

def is_voice_replies_enabled(user_id: int) -> bool:
    """Check if user has voice replies enabled"""
    analytics = get_user_analytics(user_id)
    return analytics["voice_replies_enabled"]

def toggle_voice_replies(user_id: int) -> bool:
    """Toggle voice replies preference for user"""
    analytics = get_user_analytics(user_id)
    analytics["voice_replies_enabled"] = not analytics["voice_replies_enabled"]
    enabled = analytics["voice_replies_enabled"]
    logger.info(f"User {user_id} voice replies {'enabled' if enabled else 'disabled'}")
    return enabled

def increment_voice_responses(user_id: int):
    """Increment voice response counter for analytics"""
    analytics = get_user_analytics(user_id)
    analytics["voice_responses_sent"] += 1

def get_user_preferences(user_id: int) -> Set[str]:
    """Get user's enabled translation languages"""
    if user_id not in user_preferences:
        user_preferences[user_id] = {"en"}  # Only English by default

    # Sync with analytics
    analytics = get_user_analytics(user_id)
    analytics["preferred_targets"] = user_preferences[user_id]

    return user_preferences[user_id]

def update_user_preference(user_id: int, lang_code: str) -> Set[str]:
    """Toggle language preference for user"""
    prefs = get_user_preferences(user_id)
    if lang_code in prefs:
        prefs.discard(lang_code)
    else:
        prefs.add(lang_code)

    if not prefs:
        all_langs = set(SUPPORTED_LANGUAGES.keys())
        prefs.update(all_langs)

    user_preferences[user_id] = prefs

    # Sync with analytics
    analytics = get_user_analytics(user_id)
    analytics["preferred_targets"] = prefs

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
                
        # Additional heuristics for Cyrillic text
        if re.search(r'[а-яё]', text.lower()):
            # Contains Cyrillic characters - likely Russian
            return 'ru'
            
        # Additional heuristics for English
        if re.search(r'^[a-zA-Z\s\.,\!\?\-]+$', text):
            # Contains only Latin characters and common punctuation
            return 'en'
            
        return None
        
    except LangDetectException:
        logger.warning(f"Language detection failed for: {text[:50]}...")
        # Fallback to heuristic detection
        if re.search(r'[а-яё]', text.lower()):
            return 'ru'
        elif re.search(r'^[a-zA-Z\s\.,\!\?\-]+$', text):
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
        converted_path = temp_dir / f"converted.{output_format}"

        # Export with optimal settings for Whisper
        audio.export(
            converted_path,
            format=output_format,
            parameters=["-ac", "1", "-ar", "16000"]  # mono, 16kHz
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
    for attempt in range(3):
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
    if len(text) > 500:
        logger.warning(f"TTS text too long ({len(text)} chars), skipping")
        return None

    temp_dir = Path(tempfile.mkdtemp())
    mp3_path = temp_dir / "tts_output.mp3"
    ogg_path = temp_dir / "tts_output.ogg"

    try:
        # Generate TTS audio with OpenAI
        for attempt in range(3):
            try:
                logger.info(f"Generating TTS audio (attempt {attempt + 1}) for text: {text[:50]}...")
                tts_start = datetime.now()

                response = await openai_client.audio.speech.create(
                    model=OPENAI_TTS_MODEL,
                    voice=OPENAI_TTS_VOICE,
                    input=text,
                    speed=1.0  # Normal speech speed (0.25 to 4.0, default 1.0)
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

        # Export as OGG/Opus at 48kHz mono for Telegram voice messages
        audio.export(
            ogg_path,
            format="ogg",
            codec="libopus",
            parameters=["-ac", "1", "-ar", "48000"]  # mono, 48kHz
        )

        logger.info(f"TTS audio converted: {mp3_path} -> {ogg_path}")
        return ogg_path

    except Exception as e:
        logger.error(f"TTS processing failed: {e}")
        # Cleanup on error
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)
        return None

async def translate_text(text: str, source_lang: str, target_langs: Set[str]) -> Dict[str, str]:
    """Translate text to target languages with retry logic"""
    if source_lang in target_langs:
        target_langs = target_langs - {source_lang}

    if not target_langs:
        return {}

    target_names = [SUPPORTED_LANGUAGES[lang]["name"] for lang in target_langs]
    prompt = f"""Translate this {SUPPORTED_LANGUAGES[source_lang]["name"]} text into {', '.join(target_names)}.

Provide only the translations, one per line:
{chr(10).join(f'{SUPPORTED_LANGUAGES[lang]["name"]}: [translation]' for lang in target_langs)}

Text: {text}"""

    for attempt in range(3):
        try:
            response = await openai_client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=500,
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

            return translations

        except Exception as e:
            logger.error(f"OpenAI API error (attempt {attempt + 1}): {e}")
            if attempt < 2:
                await asyncio.sleep(2 ** attempt)
                continue
            return {}

def build_preferences_keyboard(user_id: int) -> InlineKeyboardMarkup:
    """Build inline keyboard for language preferences"""
    prefs = get_user_preferences(user_id)
    buttons = []

    for lang_code, info in SUPPORTED_LANGUAGES.items():
        status = "✅" if lang_code in prefs else "❌"
        text = f"{status} {info['flag']} {info['name']}"
        buttons.append([InlineKeyboardButton(
            text=text,
            callback_data=f"toggle_{lang_code}"
        )])

    # Add voice replies toggle
    voice_enabled = is_voice_replies_enabled(user_id)
    voice_status = "✅" if voice_enabled else "❌"
    voice_text = f"{voice_status} 🎤 Voice replies"
    buttons.append([InlineKeyboardButton(
        text=voice_text,
        callback_data="toggle_voice_replies"
    )])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def build_admin_dashboard_keyboard() -> InlineKeyboardMarkup:
    """Build admin dashboard keyboard"""
    buttons = [
        [InlineKeyboardButton(text="🔄 Refresh", callback_data="admin_refresh")],
    ]

    # Add user management buttons for each user
    for user_id, analytics in user_analytics.items():
        profile = analytics["user_profile"]
        raw_username = profile["username"] or profile["first_name"] or f"User {user_id}"
        # Limit button text length to prevent callback_data issues
        button_username = raw_username[:15] + "..." if len(raw_username) > 15 else raw_username
        status = "🔴" if analytics["is_disabled"] else "🟢"

        if analytics["is_disabled"]:
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


def format_admin_dashboard() -> str:
    """Format admin dashboard text"""
    total_users = len(user_analytics)
    active_users = sum(1 for a in user_analytics.values() if not a["is_disabled"])
    disabled_users = total_users - active_users
    voice_enabled_users = sum(1 for a in user_analytics.values() if a["voice_replies_enabled"])
    total_voice_responses = sum(a["voice_responses_sent"] for a in user_analytics.values())

    text = (
        "🔧 Admin Dashboard\n\n"
        f"Total Users: {total_users}\n"
        f"Active: {active_users} | Disabled: {disabled_users}\n"
        f"Voice Replies: {voice_enabled_users} users | {total_voice_responses} sent\n\n"
        "User Summary:\n"
    )

    for user_id, analytics in sorted(user_analytics.items()):
        profile = analytics["user_profile"]
        raw_username = profile["username"] or profile["first_name"] or f"User {user_id}"
        # Limit button text length to prevent callback_data issues
        button_username = raw_username[:15] + "..." if len(raw_username) > 15 else raw_username
        username = escape_markdown(raw_username)
        status = "🔴 Disabled" if analytics["is_disabled"] else "🟢 Active"
        prefs = escape_markdown(", ".join(analytics["preferred_targets"]))
        last_activity = analytics["last_activity"].strftime("%Y-%m-%d %H:%M")
        msg_count = analytics["message_count"]
        voice_replies = "🎤 ON" if analytics["voice_replies_enabled"] else "🎤 OFF"
        voice_sent = analytics["voice_responses_sent"]

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
    if is_user_disabled(user_id):
        audit_logger.warning(f"BLOCKED_ACCESS: Disabled user {user_id} attempted translation: {text[:50]}...")
        await message.reply(
            "❌ Access disabled. Contact support if you believe this is an error."
        )
        return

    # Update user activity
    update_user_activity(user_id, message.from_user)

    source_lang = detect_language(text)
    if not source_lang:
        await message.reply(
            "❌ Couldn't detect the language.\n\n"
            "Supported languages:\n"
            "🇷🇺 Russian: \"Привет, как дела?\"\n"
            "🇺🇸 English: \"Hello, how are you?\"\n"
            "🇹🇭 Thai: \"สวัสดี เป็นอย่างไรบ้าง\""
        )
        return

    target_langs = get_user_preferences(message.from_user.id)
    if source_lang in target_langs:
        target_langs = target_langs - {source_lang}

    if not target_langs:
        all_langs = set(SUPPORTED_LANGUAGES.keys())
        target_langs = all_langs - {source_lang}

    try:
        status_msg = await message.reply("🔄 Translating...")
        translations = await translate_text(text, source_lang, target_langs)
        await status_msg.delete()

        if not translations:
            await message.reply("❌ Translation failed. Please try again.")
            return

        # Send source info for voice messages
        if source_type == "voice":
            source_info = SUPPORTED_LANGUAGES[source_lang]
            # Truncate long transcriptions for display
            display_text = text if len(text) <= 100 else text[:97] + "..."
            await message.reply(
                f"🎤 {source_info['flag']} Transcribed ({source_info['name']}):\n"
                f"_{display_text}_",
                parse_mode="Markdown"
            )

        # Send translations
        for lang_code, translation in translations.items():
            lang_info = SUPPORTED_LANGUAGES[lang_code]
            response = f"{lang_info['flag']} {lang_info['name']}:\n{translation}"
            await message.reply(response)

        # Generate and send voice response if enabled
        if is_voice_replies_enabled(user_id) and translations:
            import shutil
            from aiogram.types import FSInputFile

            # Send separate voice message for each language
            for lang_code, translation in translations.items():
                if len(translation) > 500:
                    lang_info = SUPPORTED_LANGUAGES[lang_code]
                    await message.reply(f"🎤 {lang_info['flag']} Голосовой ответ на {lang_info['name']} слишком длинный.")
                    continue

                temp_dir = None
                try:
                    # Generate TTS audio for this language
                    tts_audio_path = await generate_tts_audio(translation)
                    if tts_audio_path:
                        temp_dir = tts_audio_path.parent

                        # Create caption with language name
                        lang_info = SUPPORTED_LANGUAGES[lang_code]
                        caption = f"{lang_info['flag']} {lang_info['name']}"

                        # Send voice message
                        voice_input = FSInputFile(tts_audio_path, filename=f"voice_{lang_code}.ogg")
                        await message.reply_voice(voice_input, caption=caption)

                        logger.info(f"Voice response sent to user {user_id} in {lang_code}")

                except Exception as e:
                    lang_info = SUPPORTED_LANGUAGES[lang_code]
                    logger.error(f"TTS error for user {user_id} in {lang_code}: {e}")
                    await message.reply(f"🎤 Ошибка создания голосового ответа на {lang_info['name']}.")
                finally:
                    # Cleanup TTS temp files
                    if temp_dir and temp_dir.exists():
                        try:
                            shutil.rmtree(temp_dir, ignore_errors=True)
                        except Exception as e:
                            logger.warning(f"Failed to cleanup TTS temp directory {temp_dir}: {e}")

            # Update analytics once for all voice responses
            if translations:
                increment_voice_responses(user_id)
                logger.info(f"Voice responses completed for user {user_id}")

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
    if is_user_disabled(user_id):
        audit_logger.warning(f"BLOCKED_ACCESS: Disabled user {user_id} attempted /start")
        await message.reply(
            "❌ Access disabled. Contact support if you believe this is an error."
        )
        return

    # Update user activity
    update_user_activity(user_id, message.from_user)

    text = (
        "🌍 **Translation Bot**\n\n"
        "I translate between Russian 🇷🇺, English 🇺🇸, and Thai 🇹🇭!\n\n"
        "**How it works:**\n"
        "• Send text or voice messages in supported languages\n"
        "• I'll detect the language and translate to your enabled targets\n"
        "• Use /menu to customize which languages you want\n\n"
        "**Voice messages:** Send voice notes and I'll transcribe + translate!\n\n"
        "**Default:** I translate to all other languages\n"
        "Try sending: \"Hello, how are you?\""
    )
    await message.reply(text, parse_mode="Markdown")

@dp.message(Command("menu"))
async def menu_handler(message: Message):
    """Show language preferences menu"""
    user_id = message.from_user.id

    # Check if user is disabled
    if is_user_disabled(user_id):
        audit_logger.warning(f"BLOCKED_ACCESS: Disabled user {user_id} attempted /menu")
        await message.reply(
            "❌ Access disabled. Contact support if you believe this is an error."
        )
        return

    # Update user activity
    update_user_activity(user_id, message.from_user)

    prefs = get_user_preferences(user_id)
    enabled = [SUPPORTED_LANGUAGES[lang]["name"] for lang in prefs]

    text = (
        "⚙️ **Translation Preferences**\n\n"
        f"**Currently enabled:** {', '.join(enabled)}\n\n"
        "Toggle languages below:"
    )

    try:
        keyboard = build_preferences_keyboard(user_id)
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
        text = format_admin_dashboard()
    except Exception as e:
        logger.error(f"Error formatting admin dashboard: {e}")
        text = "❌ Error loading dashboard data"
    try:
        keyboard = build_admin_dashboard_keyboard()
    except Exception as e:
        logger.error(f"Error building admin keyboard: {e}")
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔄 Refresh", callback_data="admin_refresh")]])

    await message.reply(text, reply_markup=keyboard)

@dp.callback_query(F.data.startswith("toggle_"))
async def toggle_preference(callback: CallbackQuery):
    """Handle language preference and voice replies toggle"""
    user_id = callback.from_user.id
    toggle_data = callback.data.split("_", 1)[1]  # Get everything after "toggle_"

    # Check if user is disabled
    if is_user_disabled(user_id):
        await callback.answer("❌ Access disabled", show_alert=True)
        return

    # Update user activity
    update_user_activity(user_id, callback.from_user)

    if toggle_data == "voice_replies":
        # Handle voice replies toggle
        voice_enabled = toggle_voice_replies(user_id)
        prefs = get_user_preferences(user_id)
        enabled = [SUPPORTED_LANGUAGES[lang]["name"] for lang in prefs]

        status_msg = "enabled" if voice_enabled else "disabled"
        callback_msg = f"✅ Voice replies {status_msg}"
    else:
        # Handle language preference toggle
        lang_code = toggle_data
        if lang_code not in SUPPORTED_LANGUAGES:
            await callback.answer("Invalid language")
            return

        prefs = update_user_preference(user_id, lang_code)
        enabled = [SUPPORTED_LANGUAGES[lang]["name"] for lang in prefs]
        callback_msg = f"✅ Updated preferences: {', '.join(enabled)}"

    keyboard = build_preferences_keyboard(user_id)

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
        text = format_admin_dashboard()
        keyboard = build_admin_dashboard_keyboard()
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
        success = set_user_disabled(target_user_id, disabled)
        action_text = "disabled" if disabled else "enabled"

        audit_logger.info(f"ADMIN_ACTION: Admin {user_id} {action_text} user {target_user_id}")

        # Refresh dashboard
        text = format_admin_dashboard()
        keyboard = build_admin_dashboard_keyboard()
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")
        await callback.answer(f"✅ User {target_user_id} {action_text}")

@dp.message(F.voice | F.audio)
async def voice_handler(message: Message):
    """Handle voice and audio messages"""
    import shutil

    user_id = message.from_user.id

    # Check if user is disabled
    if is_user_disabled(user_id):
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

        # Check duration (limit to 10 minutes)
        if duration and duration > 600:
            await status_msg.edit_text("❌ Audio too long. Please send messages under 10 minutes.")
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
    if is_user_disabled(user_id):
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
    try:
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"Bot error: {e}")
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())