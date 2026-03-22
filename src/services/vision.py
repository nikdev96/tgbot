"""
Vision service for extracting text from images using GPT-4o
"""
import asyncio
import base64
import logging
from typing import Optional

from ..core.app import openai_client
from ..services.model_manager import get_model_manager

logger = logging.getLogger(__name__)


async def extract_text_from_photo(image_bytes: bytes) -> Optional[str]:
    """Extract text from image using GPT-4o vision. Returns extracted text or None on error."""
    model = get_model_manager().get_current_model()
    image_b64 = base64.b64encode(image_bytes).decode("utf-8")

    for attempt in range(3):
        try:
            response = await asyncio.wait_for(
                openai_client.chat.completions.create(
                    model=model,
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:image/jpeg;base64,{image_b64}"
                                    },
                                },
                                {
                                    "type": "text",
                                    "text": (
                                        "Extract all text visible in this image. "
                                        "Return only the extracted text, nothing else. "
                                        "If there is no text in the image, return an empty string."
                                    ),
                                },
                            ],
                        }
                    ],
                    max_tokens=1024,
                ),
                timeout=45,
            )
            return response.choices[0].message.content.strip()

        except asyncio.TimeoutError:
            logger.error(f"Vision API timeout (attempt {attempt + 1})")
        except Exception as e:
            logger.error(f"Vision API error (attempt {attempt + 1}): {e}")

        if attempt < 2:
            await asyncio.sleep(2 ** attempt)

    return None
