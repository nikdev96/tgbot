import asyncio
import logging
import os
from typing import Optional, Tuple

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message
from dotenv import load_dotenv
from langdetect import detect, LangDetectException
import openai
from openai import AsyncOpenAI

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4")

if not TELEGRAM_BOT_TOKEN or not OPENAI_API_KEY:
    raise ValueError("TELEGRAM_BOT_TOKEN and OPENAI_API_KEY must be set in environment")

bot = Bot(token=TELEGRAM_BOT_TOKEN)
dp = Dispatcher()
openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)

SUPPORTED_LANGUAGES = {
    "ru": "Russian",
    "en": "English",
    "th": "Thai"
}

LANGUAGE_FLAGS = {
    "ru": "🇷🇺",
    "en": "🇺🇸",
    "th": "🇹🇭"
}

def detect_language(text: str) -> Optional[str]:
    """Detect language of the input text. Returns language code or None if unsupported."""
    try:
        detected = detect(text)
        return detected if detected in SUPPORTED_LANGUAGES else None
    except LangDetectException:
        logger.warning(f"Failed to detect language for text: {text[:50]}...")
        return None

async def translate_text(text: str, source_lang: str) -> Optional[Tuple[str, str, str, str]]:
    """Translate text to the other two supported languages with retry logic.
    Returns tuple of (first_lang_code, first_translation, second_lang_code, second_translation)"""
    target_languages = [lang for lang in SUPPORTED_LANGUAGES if lang != source_lang]

    prompt = f"""Translate the following {SUPPORTED_LANGUAGES[source_lang]} text into {SUPPORTED_LANGUAGES[target_languages[0]]} and {SUPPORTED_LANGUAGES[target_languages[1]]}.

Provide only the translations, one per line, in this exact format:
{SUPPORTED_LANGUAGES[target_languages[0]]}: [translation]
{SUPPORTED_LANGUAGES[target_languages[1]]}: [translation]

Text to translate: {text}"""

    for attempt in range(3):
        try:
            response = await openai_client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=500,
                temperature=0.3
            )

            content = response.choices[0].message.content.strip()
            lines = content.split('\n')

            if len(lines) >= 2:
                first_translation = lines[0].split(': ', 1)[1] if ': ' in lines[0] else lines[0]
                second_translation = lines[1].split(': ', 1)[1] if ': ' in lines[1] else lines[1]

                return (target_languages[0], first_translation, target_languages[1], second_translation)

            return None
        except openai.RateLimitError:
            if attempt < 2:
                await asyncio.sleep(2 ** attempt)
                continue
            logger.error("Rate limit exceeded after retries")
            return None
        except Exception as e:
            logger.error(f"OpenAI API error (attempt {attempt + 1}): {e}")
            if attempt < 2:
                await asyncio.sleep(1)
                continue
            return None

    return None

@dp.message(Command("start"))
async def start_handler(message: Message):
    """Handle /start command."""
    welcome_text = (
        "🌍 Welcome to the Translation Bot!\n\n"
        "I can translate messages between:\n"
        "• Russian (Русский)\n"
        "• English\n"
        "• Thai (ไทย)\n\n"
        "Just send me a text message and I'll detect the language and translate it to the other two languages!"
    )
    await message.reply(welcome_text)

@dp.message(F.voice)
async def voice_handler(message: Message):
    """Handle voice messages - not implemented yet."""
    # TODO: Implement voice translation
    # 1. Download voice file: file = await bot.get_file(message.voice.file_id)
    # 2. Download file content: file_content = await bot.download_file(file.file_path)
    # 3. Send to OpenAI Whisper: transcription = await openai_client.audio.transcriptions.create(...)
    # 4. Translate transcribed text using existing translate_text function

    await message.reply(
        "🎤 Voice translation is not implemented yet.\n"
        "Please send text messages for now!"
    )

@dp.message(F.text)
async def text_handler(message: Message):
    """Handle text messages for translation."""
    text = message.text

    if not text or len(text.strip()) == 0:
        await message.reply("Please send a non-empty text message.")
        return

    detected_lang = detect_language(text)

    if not detected_lang:
        await message.reply(
            "❌ I couldn't detect the language or it's not supported.\n"
            "Try sending longer text. Examples:\n\n"
            "🇷🇺 Russian: \"Привет, как у тебя дела сегодня?\"\n"
            "🇺🇸 English: \"Hello, how are you doing today?\"\n"
            "🇹🇭 Thai: \"สวัสดี เป็นอย่างไรบ้าง วันนี้\""
        )
        return

    logger.info(f"Detected language: {detected_lang} for text: {text[:50]}...")

    try:
        translating_msg = await message.reply("🔄 Translating...")

        translations = await translate_text(text, detected_lang)

        if not translations:
            await translating_msg.delete()
            await message.reply("❌ Sorry, translation failed. Please try again later.")
            return

        first_lang_code, first_translation, second_lang_code, second_translation = translations

        first_message = f"{LANGUAGE_FLAGS[first_lang_code]} {SUPPORTED_LANGUAGES[first_lang_code]}:\n{first_translation}"
        second_message = f"{LANGUAGE_FLAGS[second_lang_code]} {SUPPORTED_LANGUAGES[second_lang_code]}:\n{second_translation}"

        await translating_msg.delete()
        await message.reply(first_message)
        await message.reply(second_message)

    except Exception as e:
        logger.error(f"Translation error: {e}")
        try:
            await translating_msg.delete()
        except:
            pass
        await message.reply("❌ An error occurred during translation. Please try again.")

async def main():
    """Main function to start the bot."""
    logger.info("Starting Translation Bot...")

    try:
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"Bot error: {e}")
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())