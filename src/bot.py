import asyncio
import logging
import os
from typing import Dict, Set

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from dotenv import load_dotenv
from langdetect import detect, LangDetectException
from openai import AsyncOpenAI

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4")

if not TELEGRAM_BOT_TOKEN or not OPENAI_API_KEY:
    raise ValueError("TELEGRAM_BOT_TOKEN and OPENAI_API_KEY must be set")

bot = Bot(token=TELEGRAM_BOT_TOKEN)
dp = Dispatcher()
openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)

SUPPORTED_LANGUAGES = {
    "ru": {"name": "Russian", "flag": "🇷🇺"},
    "en": {"name": "English", "flag": "🇺🇸"},
    "th": {"name": "Thai", "flag": "🇹🇭"}
}

# TODO: Replace with persistent storage (database/redis)
user_preferences: Dict[int, Set[str]] = {}

def get_user_preferences(user_id: int) -> Set[str]:
    """Get user's enabled translation languages"""
    if user_id not in user_preferences:
        # Default: enable all languages except source
        user_preferences[user_id] = {"ru", "en", "th"}
    return user_preferences[user_id]

def update_user_preference(user_id: int, lang_code: str) -> Set[str]:
    """Toggle language preference for user"""
    prefs = get_user_preferences(user_id)
    if lang_code in prefs:
        prefs.discard(lang_code)
    else:
        prefs.add(lang_code)

    # Auto-fallback: if all disabled, enable the other two
    if not prefs:
        all_langs = set(SUPPORTED_LANGUAGES.keys())
        prefs.update(all_langs)

    user_preferences[user_id] = prefs
    return prefs

def detect_language(text: str) -> str:
    """Detect language with fallback"""
    try:
        detected = detect(text)
        return detected if detected in SUPPORTED_LANGUAGES else None
    except LangDetectException:
        logger.warning(f"Language detection failed for: {text[:50]}...")
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

                    # Find language code by name
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
        status = "✅" if lang_code in prefs else "☐"
        text = f"{status} {info['flag']} {info['name']}"
        buttons.append([InlineKeyboardButton(
            text=text,
            callback_data=f"toggle_{lang_code}"
        )])

    return InlineKeyboardMarkup(inline_keyboard=buttons)

@dp.message(Command("start"))
async def start_handler(message: Message):
    """Welcome message with instructions"""
    text = (
        "🌍 **Translation Bot**\n\n"
        "I translate between Russian 🇷🇺, English 🇺🇸, and Thai 🇹🇭!\n\n"
        "**How it works:**\n"
        "• Send any text in supported languages\n"
        "• I'll detect the language and translate to your enabled targets\n"
        "• Use /menu to customize which languages you want\n\n"
        "**Default:** I translate to all other languages\n"
        "Try sending: \"Hello, how are you?\""
    )
    await message.reply(text, parse_mode="Markdown")

@dp.message(Command("menu"))
async def menu_handler(message: Message):
    """Show language preferences menu"""
    prefs = get_user_preferences(message.from_user.id)
    enabled = [SUPPORTED_LANGUAGES[lang]["name"] for lang in prefs]

    text = (
        "⚙️ **Translation Preferences**\n\n"
        f"**Currently enabled:** {', '.join(enabled)}\n\n"
        "Toggle languages below:"
    )

    keyboard = build_preferences_keyboard(message.from_user.id)
    await message.reply(text, reply_markup=keyboard, parse_mode="Markdown")

@dp.callback_query(F.data.startswith("toggle_"))
async def toggle_preference(callback: CallbackQuery):
    """Handle language preference toggle"""
    lang_code = callback.data.split("_")[1]

    if lang_code not in SUPPORTED_LANGUAGES:
        await callback.answer("Invalid language")
        return

    prefs = update_user_preference(callback.from_user.id, lang_code)
    enabled = [SUPPORTED_LANGUAGES[lang]["name"] for lang in prefs]

    # Update keyboard
    keyboard = build_preferences_keyboard(callback.from_user.id)

    text = (
        "⚙️ **Translation Preferences**\n\n"
        f"**Currently enabled:** {', '.join(enabled)}\n\n"
        "Toggle languages below:"
    )

    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")
    await callback.answer(f"✅ Updated preferences: {', '.join(enabled)}")

@dp.message(F.voice)
async def voice_handler(message: Message):
    """Handle voice messages - not implemented"""
    # TODO: Implement voice translation
    # 1. Download voice file: file = await bot.get_file(message.voice.file_id)
    # 2. Get file content: file_path = file.file_path; file_content = await bot.download_file(file_path)
    # 3. Send to Whisper: transcription = await openai_client.audio.transcriptions.create(model="whisper-1", file=file_content)
    # 4. Process transcription: await process_translation(message, transcription.text)

    await message.reply(
        "🎤 Voice translation isn't available yet.\n"
        "Please send text messages for now!"
    )

@dp.message(F.text)
async def text_handler(message: Message):
    """Handle text translation"""
    text = message.text.strip()

    if not text:
        await message.reply("Please send a non-empty message.")
        return

    # Detect language
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

    # Get user preferences
    target_langs = get_user_preferences(message.from_user.id)
    if source_lang in target_langs:
        target_langs = target_langs - {source_lang}

    if not target_langs:
        # Fallback: translate to other languages
        all_langs = set(SUPPORTED_LANGUAGES.keys())
        target_langs = all_langs - {source_lang}

    # Translate
    try:
        status_msg = await message.reply("🔄 Translating...")

        translations = await translate_text(text, source_lang, target_langs)

        await status_msg.delete()

        if not translations:
            await message.reply("❌ Translation failed. Please try again.")
            return

        # Send translations
        for lang_code, translation in translations.items():
            lang_info = SUPPORTED_LANGUAGES[lang_code]
            response = f"{lang_info['flag']} {lang_info['name']}:\n{translation}"
            await message.reply(response)

    except Exception as e:
        logger.error(f"Translation error: {e}")
        try:
            await status_msg.delete()
        except:
            pass
        await message.reply("❌ An error occurred. Please try again.")

async def main():
    """Start the bot"""
    logger.info("Starting Translation Bot...")
    try:
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"Bot error: {e}")
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())