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

        # Perform automatic cleanup on startup
        logger.info("Running automatic cleanup on startup...")
        deleted_users = await db.delete_inactive_users(days=3)
        deleted_files, deleted_size = await db.clear_tts_cache(days=3)
        logger.info(f"Cleanup complete: {deleted_users} users, {deleted_files} cache files ({deleted_size:.2f} MB)")
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