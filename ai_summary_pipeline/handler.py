"""Summary pipeline handler logic for Telegram bot."""
import logging
from telegram.constants import ChatAction
from pipeline import PipelineHandler, PipelineContext
from .history_manager import HistoryManager
from .summary_processor import SummaryProcessor

logger = logging.getLogger(__name__)

# Constants
MESSAGE_HISTORY_LIMIT = 200  # Both storage maxlen and summary limit

# Trigger keywords (case-insensitive CONTAINS check)
DEFAULT_TRIGGER_KEYWORDS = [
    "/summarize",
    "/summary",
    "/самарі"
]


class SummaryProcessingHandler(PipelineHandler):
    """Pipeline handler for chat summarization using Google Gemini."""

    def __init__(self):
        """Initialize summary processing handler with history manager and processor."""
        super().__init__()

        # Initialize history manager (rolling window of 200 messages per chat)
        self.history_manager = HistoryManager(max_messages=MESSAGE_HISTORY_LIMIT)

        try:
            self.summary_processor = SummaryProcessor()
            logger.info("[SUMMARY] SummaryProcessingHandler initialized successfully")
        except Exception as e:
            logger.error(f"[SUMMARY] Failed to initialize SummaryProcessor: {e}", exc_info=True)
            self.summary_processor = None

    async def should_process(self, ctx: PipelineContext) -> bool:
        """
        Store ALL text messages (except triggers), return True only if triggered.

        This method:
        1. Extracts text from message.text or message.caption
        2. Checks if message contains trigger keywords
        3. Stores message in history ONLY if it's NOT a trigger (to exclude "/summary" commands from summaries)
        4. Returns True only if trigger keyword found

        Args:
            ctx: Pipeline context containing message info

        Returns:
            True if message contains trigger keyword, False otherwise
        """
        message = ctx.message
        if not message:
            return False

        # Check if processor is initialized
        if self.summary_processor is None:
            return False

        # Extract text (message.text > message.caption)
        text = None
        if message.text:
            text = message.text
        elif message.caption:
            text = message.caption

        # Skip non-text messages (stickers, voice, photos without captions, etc.)
        if not text:
            return False

        # Check trigger keywords FIRST (case-insensitive CONTAINS)
        text_lower = text.lower()
        is_trigger = False
        for keyword in DEFAULT_TRIGGER_KEYWORDS:
            if keyword.lower() in text_lower:
                logger.info(f"[SUMMARY] Trigger keyword '{keyword}' found in chat {message.chat.id}")
                is_trigger = True
                break

        # Store message in history ONLY if it's NOT a trigger
        # This prevents "/summary" commands from appearing in the summary itself
        if not is_trigger:
            # Extract user info (handle forwarded messages)
            is_forwarded = bool(message.forward_origin)
            if is_forwarded:
                # Try to get original sender info
                username = "Forwarded"
                user_id = 0
                # Try to extract original sender if available
                if hasattr(message.forward_origin, 'sender_user') and message.forward_origin.sender_user:
                    orig_user = message.forward_origin.sender_user
                    username = orig_user.username or orig_user.first_name or "Forwarded"
                    user_id = orig_user.id
            else:
                # Regular message
                username = message.from_user.username or message.from_user.first_name
                user_id = message.from_user.id

            # Store message in history
            try:
                self.history_manager.add_message(
                    chat_id=message.chat.id,
                    user_id=user_id,
                    username=username,
                    text=text,
                    timestamp=message.date,
                    is_forwarded=is_forwarded
                )
            except Exception as e:
                logger.error(f"[SUMMARY] Failed to store message: {e}")

        return is_trigger

    async def process(self, ctx: PipelineContext) -> None:
        """
        Generate and send summary.

        Args:
            ctx: Pipeline context containing message and bot info
        """
        message = ctx.message
        chat_id = message.chat.id

        logger.info(f"[SUMMARY] Processing summary request for chat {chat_id}")

        try:
            # Show typing indicator
            await ctx.context.bot.send_chat_action(
                chat_id=chat_id,
                action=ChatAction.TYPING
            )

            # Get message history
            messages = self.history_manager.get_history(chat_id, limit=MESSAGE_HISTORY_LIMIT)

            if not messages:
                await message.reply_text("No messages to summarize yet.")
                ctx.stop()
                return

            logger.info(f"[SUMMARY] Generating summary from {len(messages)} messages")

            # Generate summary
            summary = await self.summary_processor.generate_summary(chat_id, messages)

            # Send summary
            await message.reply_text(summary)
            logger.info(f"[SUMMARY] Summary sent, length: {len(summary)} characters")

        except Exception as e:
            logger.error(f"[SUMMARY] Error generating summary: {e}", exc_info=True)
            await message.reply_text(
                "Sorry, I couldn't generate a summary. Please try again later."
            )

        # Stop pipeline
        ctx.stop()
