"""
Voice processing service with ffmpeg fallback for Python 3.13
"""
import asyncio
import logging
import shutil
import tempfile
import subprocess
from pathlib import Path
from typing import Optional

from ..core.app import bot, openai_client, config

logger = logging.getLogger(__name__)


async def download_and_convert_audio_ffmpeg(file_path: str, output_format: str = "wav") -> Path:
    """Download and convert audio file using ffmpeg directly"""
    temp_dir = Path(tempfile.mkdtemp())

    try:
        # Download file from Telegram
        downloaded_file = await bot.download_file(file_path)

        # Save original file
        original_path = temp_dir / "original.ogg"
        with open(original_path, "wb") as f:
            f.write(downloaded_file.read())

        # Convert using ffmpeg directly
        converted_path = temp_dir / f"converted.{output_format}"
        
        # Use ffmpeg to convert with optimal settings for Whisper
        cmd = [
            "ffmpeg", "-i", str(original_path),
            "-ac", "1",  # mono
            "-ar", str(config.audio.input_sample_rate),  # sample rate
            "-y",  # overwrite output
            str(converted_path)
        ]
        
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await process.communicate()
        
        if process.returncode != 0:
            logger.error(f"ffmpeg conversion failed: {stderr.decode()}")
            raise Exception(f"Audio conversion failed: {stderr.decode()}")
        
        logger.info(f"Audio converted with ffmpeg: {original_path} -> {converted_path}")
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
