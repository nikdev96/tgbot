"""
Inline query handler for @botname translations in any chat
"""
import hashlib
import logging
from aiogram import F
from aiogram.types import (
    InlineQuery,
    InlineQueryResultArticle,
    InputTextMessageContent,
)

from ..core.constants import SUPPORTED_LANGUAGES
from ..services.language import detect_language
from ..services.analytics import get_user_preferences, is_user_disabled
from ..services.translation import translate_text

logger = logging.getLogger(__name__)


def register_handlers(dp):
    """Register inline query handlers"""
    dp.inline_query.register(inline_handler)


async def inline_handler(inline_query: InlineQuery):
    """Handle inline queries for translation"""
    user_id = inline_query.from_user.id
    query_text = inline_query.query.strip()

    # Check if user is disabled
    if await is_user_disabled(user_id):
        await inline_query.answer(
            results=[],
            cache_time=1,
            is_personal=True,
        )
        return

    # If empty query, show usage hint
    if not query_text:
        await inline_query.answer(
            results=[
                InlineQueryResultArticle(
                    id="help",
                    title="Type text to translate",
                    description="Enter text in any supported language to get translations",
                    input_message_content=InputTextMessageContent(
                        message_text="Use @botname followed by text to translate\n"
                        "Supported: 🇷🇺 Russian, 🇺🇸 English, 🇹🇭 Thai, 🇻🇳 Vietnamese"
                    ),
                )
            ],
            cache_time=300,
            is_personal=True,
        )
        return

    # Detect source language
    source_lang = detect_language(query_text)
    if not source_lang:
        await inline_query.answer(
            results=[
                InlineQueryResultArticle(
                    id="unsupported",
                    title="Language not supported",
                    description="Supported: Russian, English, Thai, Vietnamese",
                    input_message_content=InputTextMessageContent(
                        message_text="Supported languages: 🇷🇺 Russian, 🇺🇸 English, 🇹🇭 Thai, 🇻🇳 Vietnamese"
                    ),
                )
            ],
            cache_time=60,
            is_personal=True,
        )
        return

    # Get user's target languages
    target_langs = await get_user_preferences(user_id)
    target_langs = {lang for lang in target_langs if lang in SUPPORTED_LANGUAGES}

    # Remove source language from targets
    if source_lang in target_langs:
        target_langs = target_langs - {source_lang}

    if not target_langs:
        # If no targets after removing source, use all except source
        target_langs = set(SUPPORTED_LANGUAGES.keys()) - {source_lang}

    # Translate text
    try:
        translations = await translate_text(query_text, source_lang, target_langs)
    except Exception as e:
        logger.error(f"Inline translation error: {e}")
        await inline_query.answer(
            results=[
                InlineQueryResultArticle(
                    id="error",
                    title="Translation failed",
                    description="Please try again",
                    input_message_content=InputTextMessageContent(
                        message_text="Translation failed. Please try again."
                    ),
                )
            ],
            cache_time=1,
            is_personal=True,
        )
        return

    if not translations:
        await inline_query.answer(
            results=[
                InlineQueryResultArticle(
                    id="no_translation",
                    title="Could not translate",
                    description="Please try with different text",
                    input_message_content=InputTextMessageContent(
                        message_text="Could not translate this text."
                    ),
                )
            ],
            cache_time=1,
            is_personal=True,
        )
        return

    # Build results
    results = []
    source_info = SUPPORTED_LANGUAGES[source_lang]

    # Add option to send all translations together
    if len(translations) > 1:
        all_translations_text = f"{source_info['flag']} {query_text}\n\n"
        for lang_code, translation in sorted(translations.items()):
            lang_info = SUPPORTED_LANGUAGES[lang_code]
            all_translations_text += f"{lang_info['flag']} {translation}\n"

        result_id = hashlib.md5(f"all:{query_text}".encode()).hexdigest()
        results.append(
            InlineQueryResultArticle(
                id=result_id,
                title="All translations",
                description=f"Send all {len(translations)} translations",
                input_message_content=InputTextMessageContent(
                    message_text=all_translations_text.strip()
                ),
            )
        )

    # Add individual translation options
    for lang_code, translation in sorted(translations.items()):
        lang_info = SUPPORTED_LANGUAGES[lang_code]
        result_id = hashlib.md5(f"{lang_code}:{query_text}".encode()).hexdigest()

        # Show original with translation
        message_text = f"{source_info['flag']} {query_text}\n{lang_info['flag']} {translation}"

        results.append(
            InlineQueryResultArticle(
                id=result_id,
                title=f"{lang_info['flag']} {lang_info['name']}",
                description=translation[:100] + ("..." if len(translation) > 100 else ""),
                input_message_content=InputTextMessageContent(
                    message_text=message_text
                ),
            )
        )

    await inline_query.answer(
        results=results,
        cache_time=300,
        is_personal=True,
    )
    logger.info(f"Inline query processed for user {user_id}: {query_text[:50]}...")
