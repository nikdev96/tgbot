"""
Main entry point for the Translation Bot
"""
import asyncio
import logging

logger = logging.getLogger(__name__)


async def main():
    """Start the bot"""
    logger.info("Starting Translation Bot with voice support...")

    # Import core components
    from .core.app import bot, dp, db

    # Initialize database
    try:
        await db.init_db()
        logger.info("Database initialized successfully")

        # Add Vietnamese to existing users
        await db.add_vietnamese_to_existing_users()
        logger.info("Vietnamese language added to existing users")
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        return

    # Register handlers
    from . import handlers
    handlers.register_all_handlers(dp)

    try:
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"Bot error: {e}")
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())