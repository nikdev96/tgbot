"""
Event handlers for Telegram bot
"""
from aiogram import Dispatcher


def register_all_handlers(dp: Dispatcher):
    """Register all bot handlers"""
    from . import commands, callbacks, text, voice, room_commands, inline_queries, reactions

    # Register command handlers (1)
    commands.register_handlers(dp)

    # Register inline query handlers (2)
    inline_queries.register_handlers(dp)

    # Register reaction handlers (3)
    reactions.register_handlers(dp)

    # Register callback handlers (4)
    callbacks.register_handlers(dp)

    # Register room handlers (5)
    room_commands.register_handlers(dp)

    # Register voice handlers (6)
    voice.register_handlers(dp)

    # Register photo handlers (7)
    from . import photo
    photo.register_photo_handlers(dp)

    # Register text handlers (8 - should be last as catch-all)
    text.register_handlers(dp)