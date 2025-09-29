"""
Voice and audio message handlers
"""
import logging
import shutil
from aiogram import F
from aiogram.types import Message
from ..core.app import bot, config, audit_logger
from ..services.analytics import is_user_disabled
from ..services.voice import download_and_convert_audio, transcribe_audio
from ..services.translation import process_translation

logger = logging.getLogger(__name__)


def register_handlers(dp):
    """Register voice handlers"""
    dp.message.register(voice_handler, F.voice | F.audio)


async def voice_handler(message: Message):
    """Handle voice and audio messages"""
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