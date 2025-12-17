"""
Main entry point for the Translation Bot
"""
import asyncio
import logging
import signal
import sys

logger = logging.getLogger(__name__)


async def shutdown(sig, loop, bot):
    """Graceful shutdown handler"""
    logger.info(f"Received exit signal {sig.name}...")

    # Cancel all running tasks
    tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    logger.info(f"Cancelling {len(tasks)} outstanding tasks")

    for task in tasks:
        task.cancel()

    await asyncio.gather(*tasks, return_exceptions=True)

    # Close bot session
    logger.info("Closing bot session")
    await bot.session.close()

    # Stop event loop
    loop.stop()
    logger.info("Shutdown complete")


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

    # Register middleware
    from .middlewares import RateLimitMiddleware, UserCheckMiddleware
    dp.message.middleware(UserCheckMiddleware())
    dp.message.middleware(RateLimitMiddleware())
    dp.callback_query.middleware(UserCheckMiddleware())
    logger.info("Middleware registered successfully")

    # Register handlers
    from . import handlers
    handlers.register_all_handlers(dp)

    # Get event loop and register signal handlers
    loop = asyncio.get_event_loop()

    # Register signal handlers for graceful shutdown
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(
            sig,
            lambda s=sig: asyncio.create_task(shutdown(s, loop, bot))
        )

    logger.info("Signal handlers registered for graceful shutdown")

    try:
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"Bot error: {e}")
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())