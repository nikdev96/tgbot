"""
Voice and audio message handlers with forced ffmpeg fallback for Python 3.13
"""
import logging
import shutil
from aiogram import F
from aiogram.types import Message
from ..core.app import bot, config, audit_logger
from ..services.analytics import is_user_disabled
from ..services.translation import process_translation

logger = logging.getLogger(__name__)

# Force use of ffmpeg version due to Python 3.13 audioop issue
try:
    from ..services.voice_fix import download_and_convert_audio_ffmpeg as download_and_convert_audio, transcribe_audio
    logger.info("Using ffmpeg fallback for audio processing (Python 3.13 compatibility)")
except ImportError as e:
    logger.error(f"Failed to import ffmpeg fallback: {e}")
    raise


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

    # Check if user is in an active room
    from ..services.room_manager import RoomManager
    active_room = await RoomManager.get_active_room(user_id)

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

        await status_msg.edit_text("🔄 Processing audio...")

        # PARALLEL OPTIMIZATION: Download+convert and prepare for transcription in one step
        try:
            # Start download and conversion
            audio_path = await download_and_convert_audio(file_info.file_path)
            temp_dir = audio_path.parent
            logger.info(f"Audio processed successfully: {audio_path}")

            # Immediately start transcription (no extra status update delay)
            transcription = await transcribe_audio(audio_path)
            logger.info(f"Transcription successful: {len(transcription)} characters")

        except Exception as e:
            if "ffmpeg" in str(e).lower():
                await status_msg.edit_text("❌ Audio processing requires FFmpeg. Please install FFmpeg first.")
                logger.error(f"FFmpeg error: {e}")
                return
            elif "transcription" in str(e).lower() or "whisper" in str(e).lower():
                await status_msg.edit_text("❌ Could not transcribe audio. Please try again with clearer speech.")
                logger.error(f"Transcription error: {e}")
                return
            else:
                await status_msg.edit_text("❌ Audio processing failed. Please try again.")
                logger.error(f"Audio processing error: {e}")
                return

        if not transcription.strip():
            await status_msg.edit_text("❌ Could not transcribe audio. Please try again with clearer speech.")
            return

        # EARLY RESPONSE: Show transcription immediately
        from ..services.language import detect_language
        from ..core.constants import SUPPORTED_LANGUAGES
        from ..utils.formatting import escape_markdown

        source_lang = detect_language(transcription)
        if source_lang:
            source_info = SUPPORTED_LANGUAGES[source_lang]
            max_len = 200
            display_text = transcription if len(transcription) <= max_len else transcription[:max_len-3] + "..."
            escaped_text = escape_markdown(display_text)
            await status_msg.edit_text(
                f"🎤 {source_info['flag']} Transcribed ({source_info['name']}):\n"
                f"_{escaped_text}_\n\n"
                f"🔄 Translating...",
                parse_mode="Markdown"
            )
        else:
            await status_msg.delete()

        # If user is in a room, handle as room message
        if active_room:
            logger.info(f"🔍 DEBUG: User {user_id} in room {active_room.code}, calling handle_room_message")
            await status_msg.delete()
            await RoomManager.handle_room_message(message, active_room, transcription)
            logger.info(f"🔍 DEBUG: handle_room_message completed for user {user_id}")
            return

        # Process translation using existing logic (now with early transcription shown)
        await process_translation(message, transcription, source_type="voice", early_response_msg=status_msg)

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
