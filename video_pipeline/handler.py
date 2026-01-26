"""
VideoDownloadHandler - Downloads videos from supported platforms.

This handler detects video URLs in messages, downloads the video,
and replies with the downloaded content.
"""

import logging
import os
import random

from telegram.constants import ChatAction

from pipeline import PipelineContext, PipelineHandler
from video_pipeline.router import ServiceRouter
from video_pipeline.downloader import download_video
from video_pipeline.services import load_services_from_env

logger = logging.getLogger(__name__)

# Cat emojis for error messages
CAT_EMOJIS = ["😺", "😸", "😹", "😻", "😼", "😽", "🙀", "😿", "😾", "🐱"]


def get_random_cat_emoji() -> str:
    """Return a random cat emoji for error messages."""
    return random.choice(CAT_EMOJIS)


class VideoDownloadHandler(PipelineHandler):
    """
    Handler that downloads videos from supported platforms.

    Uses the ServiceRouter to detect video URLs and download them.
    On success, replies to the message with the downloaded video.
    """

    def __init__(self, stop_on_no_url: bool = False):
        """
        Initialize the VideoDownloadHandler.

        Args:
            stop_on_no_url: If True, stop pipeline if no video URL is found.
                           If False (default), continue to next handler.
        """
        super().__init__("VideoDownloadHandler")

        # Auto-discover and initialize services internally
        services = load_services_from_env()
        self.service_router = ServiceRouter(services)

        self.bot_username = os.getenv('BOT_USERNAME', '@white_cat_downloader_bot')
        self.stop_on_no_url = stop_on_no_url

    async def should_process(self, ctx: PipelineContext) -> bool:
        """Only process text messages."""
        return ctx.message_text is not None

    async def process(self, ctx: PipelineContext) -> None:
        """Process the message and download video if URL is found."""
        message = ctx.message
        text = ctx.message_text

        if not message or not text:
            return

        chat_name = message.chat.title or 'Private'
        user_name = message.from_user.full_name if message.from_user else 'Unknown'
        logger.info(f"[VIDEO] START msg={message.message_id} chat='{chat_name}'({message.chat.id}) user='{user_name}' text='{text}'")

        # Route URL to appropriate service
        logger.info(f"[VIDEO] Routing message to service router...")
        result = self.service_router.get_video_url(text)

        if not result:
            logger.info(f"[VIDEO] No video URL found in message")
            ctx.data['video_url_found'] = False
            if self.stop_on_no_url:
                ctx.stop()
            return

        # Check if result indicates provider failure
        if result == "providers_failed":
            logger.warning(f"[VIDEO] URL matched but all providers failed")
            cat_emoji = get_random_cat_emoji()
            error_msg = (
                f"😿 Meow! I couldn't fetch this video. All my providers failed! "
                f"The video might be private, deleted, or the URL might be incorrect. "
                f"{cat_emoji}\n\n{self.bot_username}"
            )
            await message.reply_text(error_msg)
            ctx.data['video_error'] = 'providers_failed'
            ctx.stop()
            return

        video_url, service_name, provider_num, provider_name = result
        logger.info(f"[VIDEO] Video URL obtained!")
        logger.info(f"[VIDEO] Service: {service_name}")
        logger.info(f"[VIDEO] Provider: #{provider_num} - {provider_name}")
        logger.info(f"[VIDEO] Video URL: {video_url}")

        # Store in context for other handlers
        ctx.data['video_url_found'] = True
        ctx.data['video_url'] = video_url
        ctx.data['service_name'] = service_name
        ctx.data['provider_num'] = provider_num
        ctx.data['provider_name'] = provider_name

        try:
            # Show "uploading video" status
            await ctx.context.bot.send_chat_action(
                chat_id=message.chat_id,
                action=ChatAction.UPLOAD_VIDEO
            )

            # Download video
            logger.info(f"[VIDEO] Calling download_video()...")
            download_result = await download_video(video_url)

            if not download_result or download_result[0] is None:
                logger.warning(f"[VIDEO] Video download failed")
                cat_emoji = get_random_cat_emoji()

                # Get error type
                error_type = download_result[1] if download_result else "download_failed"
                ctx.data['video_error'] = error_type

                # Generate specific error message based on error type
                if error_type == "too_large":
                    error_msg = f"😿 Meow! This video is too big for my tiny paws! {cat_emoji}\n\n{self.bot_username}"
                elif error_type == "not_found":
                    error_msg = (
                        f"😿 Meow! I couldn't find this video. The URL might be incorrect "
                        f"or the video may have been deleted! {cat_emoji}\n\n{self.bot_username}"
                    )
                else:
                    error_msg = f"😿 Meow! Video download failed. Something went wrong! {cat_emoji}\n\n{self.bot_username}"

                logger.info(f"[VIDEO] Sending error message (error_type: {error_type})...")
                await message.reply_text(error_msg)
                ctx.stop()
                return

            video_buffer = download_result[0]
            ctx.data['video_downloaded'] = True
            ctx.data['video_size'] = video_buffer.getbuffer().nbytes

            logger.info(f"[VIDEO] Video downloaded successfully!")
            logger.info(f"[VIDEO] Buffer size: {ctx.data['video_size']} bytes")

            # Send video as reply with service and provider info
            caption = f"Downloaded by {self.bot_username}\n{service_name} #{provider_num}"
            logger.info(f"[VIDEO] Sending video to Telegram... {caption}")

            await message.reply_video(
                video=video_buffer,
                caption=caption,
                read_timeout=120,
                write_timeout=120,
                connect_timeout=30
            )

            ctx.data['video_sent'] = True
            logger.info(f"[VIDEO] Video sent successfully! Service: {service_name}, Provider #{provider_num}: {provider_name}")

            # Stop pipeline after successful video send
            ctx.stop()

        except Exception as e:
            logger.error(f"[VIDEO] Error processing message: {type(e).__name__}: {e}", exc_info=True)
            cat_emoji = get_random_cat_emoji()
            error_msg = f"😿 Oops! Something went wrong. This White Cat got confused! {cat_emoji}\n\n{self.bot_username}"
            await message.reply_text(error_msg)
            ctx.data['video_error'] = str(e)
            ctx.stop()

        logger.info(f"[VIDEO] ========== VIDEO HANDLER END ==========")
