"""
Photo message handler for OCR + translation
"""
import logging
from io import BytesIO

from aiogram import F
from aiogram.types import Message

from ..core.app import bot, audit_logger
from ..services.analytics import is_user_disabled
from ..services.translation import process_translation
from ..services.vision import extract_text_from_photo

logger = logging.getLogger(__name__)

MAX_PHOTO_SIZE = 20 * 1024 * 1024  # 20 MB


def register_photo_handlers(dp):
    """Register photo handlers"""
    dp.message.register(photo_handler, F.photo)


async def photo_handler(message: Message):
    """Handle photo messages: extract text via OCR then translate"""
    user_id = message.from_user.id

    if await is_user_disabled(user_id):
        audit_logger.warning(f"BLOCKED_ACCESS: Disabled user {user_id} attempted photo message")
        await message.reply("❌ Access disabled. Contact support if you believe this is an error.")
        return

    photo = message.photo[-1]

    if photo.file_size and photo.file_size > MAX_PHOTO_SIZE:
        await message.reply("❌ Photo is too large. Please send images under 20 MB.")
        return

    status_msg = await message.reply("🖼 Analyzing photo...")

    try:
        file_info = await bot.get_file(photo.file_id)
        buf = BytesIO()
        await bot.download_file(file_info.file_path, destination=buf)
        image_bytes = buf.getvalue()

        extracted_text = await extract_text_from_photo(image_bytes)

        if extracted_text is None:
            await status_msg.edit_text("❌ Failed to analyze photo. Please try again.")
            return

        if not extracted_text.strip():
            await status_msg.edit_text("❌ No text found in the photo.")
            return

        max_len = 200
        display = extracted_text if len(extracted_text) <= max_len else extracted_text[:max_len - 3] + "..."
        await status_msg.edit_text(f"🔤 Text: {display}\n\n🔄 Translating...")

        await process_translation(message, extracted_text, source_type="text", early_response_msg=status_msg)

    except Exception as e:
        logger.error(f"Photo processing error: {e}")
        try:
            await status_msg.edit_text("❌ Couldn't process photo. Please try again.")
        except Exception:
            await message.reply("❌ Couldn't process photo. Please try again.")
