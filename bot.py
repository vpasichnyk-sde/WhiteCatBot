#!/usr/bin/env python3
"""
whiteCat - Telegram bot for downloading videos from multiple services
Monitors group messages and downloads Instagram, TikTok, and other platform videos

VERSION 3: Multi-service architecture with plugin-based providers
"""

import os
import logging
import asyncio
from io import BytesIO
from typing import Optional

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes
from telegram.constants import ChatAction
from aiohttp import web

# Import multi-service system
from video_services import load_services_from_env
from service_router import ServiceRouter

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
BOT_USERNAME = os.getenv('BOT_USERNAME', '@white_cat_downloader_bot')

# Global service router (initialized in validate_config)
service_router: Optional[ServiceRouter] = None

# Constants
# Telegram bot file size limit is 2GB, but we use 100MB for memory/performance safety
# Increase this value if you need to download larger videos (max: 2000MB)
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB in bytes

# Cat emojis for error messages
CAT_EMOJIS = ["😺", "😸", "😹", "😻", "😼", "😽", "🙀", "😿", "😾", "🐱"]


def validate_config() -> None:
    """Validate required environment variables and initialize services."""
    global service_router

    if not TELEGRAM_BOT_TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN is not set in .env file")

    # Auto-discover and load services with their providers
    try:
        services = load_services_from_env()

        # Initialize service router
        service_router = ServiceRouter(services)

    except Exception as e:
        logger.error(f"Failed to load services: {e}")
        raise


async def download_video(video_url: str) -> Optional[tuple[BytesIO, Optional[str]]]:
    """
    Download video to memory.

    Args:
        video_url: Direct video URL

    Returns:
        Tuple of (BytesIO buffer, error_type) where error_type is:
        - None if successful
        - "too_large" if video exceeds size limit
        - "not_found" if video URL is invalid/not found (404)
        - "download_failed" for other errors
    """
    import requests

    try:
        logger.info(f"[DOWNLOAD] Starting video download from: {video_url[:100]}...")
        logger.info(f"[DOWNLOAD] Full URL: {video_url}")
        logger.info(f"[DOWNLOAD] Max file size limit: {MAX_FILE_SIZE} bytes ({MAX_FILE_SIZE / (1024*1024):.1f}MB)")

        logger.info(f"[DOWNLOAD] Initiating HTTP GET request with streaming...")
        response = requests.get(video_url, stream=True, timeout=30)
        logger.info(f"[DOWNLOAD] Response received - Status Code: {response.status_code}")
        logger.info(f"[DOWNLOAD] Response Headers: {dict(response.headers)}")

        # Check for 404 or other client errors
        if response.status_code == 404:
            logger.error(f"[DOWNLOAD] ✗ Video not found (404)")
            return None, "not_found"

        response.raise_for_status()

        # Check content length
        content_length = response.headers.get('content-length')
        if content_length:
            content_length_int = int(content_length)
            logger.info(f"[DOWNLOAD] Content-Length header: {content_length_int} bytes ({content_length_int / (1024*1024):.2f}MB)")
            if content_length_int > MAX_FILE_SIZE:
                logger.error(f"[DOWNLOAD] Video too large: {content_length_int} bytes (max {MAX_FILE_SIZE})")
                return None, "too_large"
        else:
            logger.warning(f"[DOWNLOAD] No Content-Length header present, will check size during download")

        # Download to memory
        logger.info(f"[DOWNLOAD] Starting chunked download (chunk_size=8192 bytes)...")
        video_buffer = BytesIO()
        downloaded = 0
        chunk_count = 0

        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                video_buffer.write(chunk)
                downloaded += len(chunk)
                chunk_count += 1

                # Log progress every 1MB
                if chunk_count % 128 == 0:  # 128 chunks * 8KB ≈ 1MB
                    logger.info(f"[DOWNLOAD] Progress: {downloaded} bytes ({downloaded / (1024*1024):.2f}MB) downloaded")

                # Check size while downloading
                if downloaded > MAX_FILE_SIZE:
                    logger.error(f"[DOWNLOAD] Video exceeded size limit during download: {downloaded} bytes")
                    return None, "too_large"

        video_buffer.seek(0)
        logger.info(f"[DOWNLOAD] ✓ Video downloaded successfully!")
        logger.info(f"[DOWNLOAD] Total size: {downloaded} bytes ({downloaded / (1024*1024):.2f}MB)")
        logger.info(f"[DOWNLOAD] Total chunks: {chunk_count}")
        return video_buffer, None

    except requests.HTTPError as e:
        if e.response and e.response.status_code == 404:
            logger.error(f"[DOWNLOAD] ✗ Video not found (404)")
            return None, "not_found"
        logger.error(f"[DOWNLOAD] ✗ HTTP error downloading video: {type(e).__name__}: {e}")
        return None, "download_failed"
    except requests.RequestException as e:
        logger.error(f"[DOWNLOAD] ✗ Error downloading video: {type(e).__name__}: {e}")
        return None, "download_failed"


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle incoming messages and process Instagram URLs.

    Args:
        update: Telegram update object
        context: Callback context
    """
    message = update.message

    logger.info(f"[HANDLER] ========== NEW MESSAGE RECEIVED ==========")
    logger.info(f"[HANDLER] Message ID: {message.message_id if message else 'None'}")
    logger.info(f"[HANDLER] Chat: {message.chat.title if message and message.chat.title else 'Private'} (ID: {message.chat.id if message else 'None'})")
    logger.info(f"[HANDLER] User: {message.from_user.full_name if message and message.from_user else 'Unknown'}")

    # Only process text messages
    if not message or not message.text:
        logger.info(f"[HANDLER] Message is not text, ignoring")
        return

    logger.info(f"[HANDLER] Message text: {message.text}")

    # Route URL to appropriate service
    if not service_router:
        logger.error("[HANDLER] ✗ Service router not initialized")
        return

    logger.info(f"[HANDLER] Routing message to service router...")
    result = service_router.get_video_url(message.text)
    if not result:
        logger.info(f"[HANDLER] No video URL found in message, ignoring")
        return  # No video URL found in any service, ignore message

    # Check if result indicates provider failure
    if result == "providers_failed":
        logger.warning(f"[HANDLER] ✗ URL matched but all providers failed")
        import random
        cat_emoji = random.choice(CAT_EMOJIS)
        error_msg = f"😿 Meow! I couldn't fetch this video. All my providers failed! The video might be private, deleted, or the URL might be incorrect. {cat_emoji}\n\n{BOT_USERNAME}"
        await message.reply_text(error_msg)
        return

    video_url, service_name, provider_num, provider_name = result
    logger.info(f"[HANDLER] ✓ Video URL obtained!")
    logger.info(f"[HANDLER] Service: {service_name}")
    logger.info(f"[HANDLER] Provider: #{provider_num} - {provider_name}")
    logger.info(f"[HANDLER] Video URL: {video_url}")

    try:
        # Show "uploading video" status
        await context.bot.send_chat_action(chat_id=message.chat_id, action=ChatAction.UPLOAD_VIDEO)

        # Download video
        logger.info(f"[HANDLER] Calling download_video()...")
        result = await download_video(video_url)

        if not result or result[0] is None:
            logger.warning(f"[HANDLER] ✗ Video download failed")
            import random
            cat_emoji = random.choice(CAT_EMOJIS)

            # Get error type
            error_type = result[1] if result else "download_failed"

            # Generate specific error message based on error type
            if error_type == "too_large":
                error_msg = f"😿 Meow! This video is too big for my tiny paws! Maximum size is {MAX_FILE_SIZE // (1024*1024)}MB. {cat_emoji}\n\n{BOT_USERNAME}"
            elif error_type == "not_found":
                error_msg = f"😿 Meow! I couldn't find this video. The URL might be incorrect or the video may have been deleted! {cat_emoji}\n\n{BOT_USERNAME}"
            else:
                error_msg = f"😿 Meow! Video download failed. Something went wrong! {cat_emoji}\n\n{BOT_USERNAME}"

            logger.info(f"[HANDLER] Sending error message to user (error_type: {error_type})...")
            await message.reply_text(error_msg)
            logger.info(f"[HANDLER] Error message sent")
            return

        video_buffer = result[0]

        logger.info(f"[HANDLER] ✓ Video downloaded successfully!")
        logger.info(f"[HANDLER] Buffer size: {video_buffer.getbuffer().nbytes} bytes")

        # Send video as reply with service and provider info
        caption = f"Downloaded by {BOT_USERNAME}\n{service_name} #{provider_num}"
        logger.info(f"[HANDLER] Sending video to Telegram (reply_video)...")
        logger.info(f"[HANDLER] Caption: {caption}")

        await message.reply_video(
            video=video_buffer,
            caption=caption
        )
        logger.info(f"[HANDLER] ✓ Video sent successfully to user!")
        logger.info(f"[HANDLER] Service: {service_name}, Provider #{provider_num}: {provider_name}")

        logger.info(f"[HANDLER] ========== MESSAGE PROCESSING COMPLETE ==========")

    except Exception as e:
        logger.error(f"[HANDLER] ✗ Error processing message: {type(e).__name__}: {e}", exc_info=True)
        import random
        cat_emoji = random.choice(CAT_EMOJIS)
        error_msg = f"😿 Oops! Something went wrong. This White Cat got confused! {cat_emoji}\n\n{BOT_USERNAME}"
        await message.reply_text(error_msg)


async def health_check_server():
    """
    Start a simple HTTP health check server for deployment platforms.

    This server provides a health check endpoint required by platforms like Render.com
    that need to verify the service is running. The server runs concurrently with the
    Telegram bot without interfering with bot operations.

    Environment Variables:
        PORT: HTTP port to bind to (default: 8080)

    Endpoints:
        GET /        : Returns 200 OK with bot status
        GET /health  : Returns 200 OK with detailed health info

    Usage:
        This function is automatically called when running on platforms that require
        HTTP endpoints (like Render.com web services). For local development or
        platforms that support background workers, this is optional.
    """
    logger.info("[HEALTH] Starting health check server...")

    async def handle_root(request):
        """Root endpoint - simple status check."""
        return web.Response(
            text="whiteCat Bot is running! 😺\nTelegram video downloader bot is active.",
            status=200
        )

    async def handle_health(request):
        """Health check endpoint - detailed status."""
        health_data = {
            "status": "healthy",
            "service": "whiteCat-bot",
            "version": "v3-multi-service",
            "services_loaded": len(service_router.services) if service_router else 0,
            "services": service_router.get_services() if service_router else []
        }
        return web.json_response(health_data, status=200)

    # Create aiohttp application
    app = web.Application()
    app.router.add_get('/', handle_root)
    app.router.add_get('/health', handle_health)

    # Get port from environment (Render provides PORT env var)
    port = int(os.getenv('PORT', 8080))

    # Create runner and start server
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()

    logger.info(f"[HEALTH] ✓ Health check server started on http://0.0.0.0:{port}")
    logger.info(f"[HEALTH]   - GET / (root status)")
    logger.info(f"[HEALTH]   - GET /health (detailed health check)")

    # Keep the server running
    try:
        await asyncio.Event().wait()  # Run forever
    except asyncio.CancelledError:
        logger.info("[HEALTH] Health check server shutting down...")
        await runner.cleanup()


async def run_bot():
    """
    Run the Telegram bot with polling.

    This function initializes the bot, validates configuration, loads services,
    and starts polling for Telegram updates. It's designed to run concurrently
    with the health check server.
    """
    logger.info("Starting whiteCat bot (v3 - Multi-service)...")

    # Validate configuration and load services
    validate_config()

    # Create application
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Register handler for all messages
    application.add_handler(MessageHandler(filters.ALL, handle_message))

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
    Main entry point - runs bot and health check server concurrently.

    This function starts both the Telegram bot (polling) and an HTTP health check
    server. Both run concurrently in the same process using asyncio.

    The health check server is optional but recommended for deployment platforms
    like Render.com that require HTTP endpoints. Set ENABLE_HEALTH_CHECK=false
    to disable it for local development or background worker deployments.
    """
    # Check if health check server should be enabled
    enable_health_check = os.getenv('ENABLE_HEALTH_CHECK', 'true').lower() == 'true'

    async def run_all():
        """Run bot and health check server concurrently."""
        tasks = [run_bot()]

        if enable_health_check:
            logger.info("[MAIN] Health check server enabled")
            tasks.append(health_check_server())
        else:
            logger.info("[MAIN] Health check server disabled (set ENABLE_HEALTH_CHECK=true to enable)")

        # Run all tasks concurrently
        await asyncio.gather(*tasks)

    try:
        asyncio.run(run_all())
    except KeyboardInterrupt:
        logger.info("Received exit signal, shutting down...")


if __name__ == '__main__':
    main()
