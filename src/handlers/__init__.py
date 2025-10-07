"""
Event handlers for Telegram bot
"""
from aiogram import Dispatcher


def register_all_handlers(dp: Dispatcher):
    """Register all bot handlers"""
    from . import commands, callbacks, text, voice, room_commands

    # Register command handlers
    commands.register_handlers(dp)

    # Register callback handlers
    callbacks.register_handlers(dp)

    # Register room handlers
    room_commands.register_handlers(dp)

    # Register voice handlers
    voice.register_handlers(dp)

    # Register text handlers (should be last)
    text.register_handlers(dp)