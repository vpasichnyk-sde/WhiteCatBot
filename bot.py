#!/usr/bin/env python3
"""
whiteCat - Telegram bot for downloading videos from multiple services

A pipeline-based Telegram bot that automatically downloads videos from Instagram, TikTok,
and other platforms. Features auto-discovery of services and providers, modular handler
architecture, and priority-based provider fallback for maximum reliability.

Architecture:
  - Pipeline system: Extensible message processing chain
  - Auto-discovery: Services and providers are automatically detected at startup
  - Modular: Add new services by creating a folder with URL pattern and providers
  - Priority-based: Automatic fallback when providers fail
"""

import os
import logging
import asyncio
from typing import Optional

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes

# Import pipeline system
from pipeline import MessagePipeline, load_handlers_from_env

# Load environment variables early for logging configuration
load_dotenv()

# Configure logging with level from environment variable
LOG_LEVEL = os.getenv('LOG_LEVEL', 'WARNING').upper()
LOG_LEVEL_MAP = {
    'DEBUG': logging.DEBUG,
    'INFO': logging.INFO,
    'WARNING': logging.WARNING,
    'ERROR': logging.ERROR,
    'CRITICAL': logging.CRITICAL
}
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=LOG_LEVEL_MAP.get(LOG_LEVEL, logging.WARNING)
)
logger = logging.getLogger(__name__)

# Suppress verbose logging from external libraries
logging.getLogger('httpx').setLevel(logging.WARNING)
logging.getLogger('httpcore').setLevel(logging.WARNING)
logging.getLogger('telegram').setLevel(logging.WARNING)
logging.getLogger('telegram.ext').setLevel(logging.WARNING)

# Configuration from environment
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')

# Global message pipeline (initialized in validate_config)
message_pipeline: Optional[MessagePipeline] = None


def validate_config() -> None:
    """Validate required environment variables."""
    if not TELEGRAM_BOT_TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN is not set in .env file")

def init_pipeline() -> MessagePipeline:
    """Initialize and configure the message pipeline with handlers."""
    try:
        pipeline = MessagePipeline(stop_on_error=True)

        # OPTION 1: Auto-discovery (recommended for many handlers)
        # Automatically discovers all handlers in handlers/ directory
        # Handlers are sorted by priority and can be enabled/disabled via env vars
        handlers = load_handlers_from_env("handlers")
        for handler in handlers:
            pipeline.add_handler(handler)

        # OPTION 2: Manual registration (for fine-grained control)
        # Uncomment below and comment out Option 1 if you prefer explicit control
        # pipeline.add_handler(VideoDownloadHandler())

        logger.info(f"[PIPELINE] Initialized with {len(pipeline.handlers)} handlers")
        return pipeline

    except Exception as e:
        logger.error(f"Failed to initialize pipeline: {e}")
        raise

async def handle_message_pipeline(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle incoming messages using the pipeline architecture.

    Messages flow through each registered handler in order.
    Any handler can stop the pipeline by calling ctx.stop().

    Args:
        update: Telegram update object
        context: Callback context
    """
    if not message_pipeline:
        logger.error("[HANDLER] Pipeline not initialized")
        return

    message = update.message
    logger.info(f"[HANDLER] ========== NEW MESSAGE RECEIVED ==========")
    logger.info(f"[HANDLER] Message ID: {message.message_id if message else 'None'}")
    logger.info(f"[HANDLER] Chat: {message.chat.title if message and message.chat.title else 'Private'} (ID: {message.chat.id if message else 'None'})")
    logger.info(f"[HANDLER] User: {message.from_user.full_name if message and message.from_user else 'Unknown'}")

    # Run the message through the pipeline
    await message_pipeline.run(update, context)

    logger.info(f"[HANDLER] ========== MESSAGE PROCESSING COMPLETE ==========")

async def run_bot():
    """
    Run the Telegram bot with polling.
    """
    global message_pipeline

    logger.info("Starting whiteCat bot (v3 - Multi-service)...")

    # Validate configuration and initialize pipeline
    validate_config()
    message_pipeline = init_pipeline()

    # Create application
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Register handler for all messages (using pipeline architecture)
    application.add_handler(MessageHandler(filters.ALL, handle_message_pipeline))

    # Start bot
    logger.info("Bot started! Send video URLs (Instagram, TikTok, etc.) in Telegram groups.")
    logger.info("Press Ctrl+C to stop.")

    # Initialize and start the application
    await application.initialize()
    await application.start()
    await application.updater.start_polling(allowed_updates=Update.ALL_TYPES)

    # Keep running until stopped
    try:
        await asyncio.Event().wait()
    except asyncio.CancelledError:
        logger.info("Bot shutting down...")
    finally:
        await application.stop()
        await application.shutdown()


def main() -> None:
    """
    Main entry point - runs tasks concurrently.
    """

    async def run_all():
        """Run tasks concurrently."""
        tasks = [run_bot()]

        # Add more tasks here

        # Run all tasks concurrently
        await asyncio.gather(*tasks)

    try:
        asyncio.run(run_all())
    except KeyboardInterrupt:
        logger.info("Received exit signal, shutting down...")


if __name__ == '__main__':
    main()
