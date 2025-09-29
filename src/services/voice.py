"""
Voice processing service for audio transcription and file handling
"""
import asyncio
import logging
import shutil
import tempfile
from pathlib import Path
from typing import Optional

from ..core.app import bot, openai_client, config

logger = logging.getLogger(__name__)


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