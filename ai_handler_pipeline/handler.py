"""AI handler pipeline logic for Telegram bot."""
import logging
from datetime import datetime
from telegram.constants import ChatAction
from pipeline import PipelineHandler, PipelineContext
from message_storage import get_conversation_manager, extract_sender_info
from .processor import GeminiProcessor
from .trigger_registry import TriggerRegistry

logger = logging.getLogger(__name__)


class AIProcessingHandler(PipelineHandler):
    """Pipeline handler for AI-powered message processing using Google Gemini."""

    def __init__(self):
        """Initialize AI processing handler with Gemini processor and trigger registry."""
        super().__init__()

        # Shared conversation storage (single rolling window used by all features)
        self.conversation_manager = get_conversation_manager()

        try:
            self.processor = GeminiProcessor(self.conversation_manager)
            logger.info("[AI] AIProcessingHandler initialized successfully")
        except Exception as e:
            logger.error(f"[AI] Failed to initialize GeminiProcessor: {e}", exc_info=True)
            self.processor = None

        # Initialize trigger registry
        self.trigger_registry = TriggerRegistry()

        # Bot username (lazy-loaded)
        self.bot_username = None

    async def should_process(self, ctx: PipelineContext) -> bool:
        """
        Store ALL messages passively, return True only if triggered.

        This implements passive listening: the bot stores all text messages
        in the conversation history but only responds when explicitly triggered.

        Args:
            ctx: Pipeline context containing message info

        Returns:
            True if message triggered AI response, False otherwise
        """
        message = ctx.message
        if not message:
            return False

        # Extract text from message (message.text takes priority over caption)
        text = message.text or message.caption
        if not text:
            return False

        # Check if processor is initialized
        if self.processor is None:
            return False

        # Initialize bot identity on first message (lazy loading)
        if not self.trigger_registry._identity_initialized:
            await self.trigger_registry.initialize_bot_identity(ctx.context.bot)
            if self.bot_username is None:
                try:
                    bot_info = await ctx.context.bot.get_me()
                    self.bot_username = bot_info.username
                except Exception as e:
                    logger.error(f"[AI] Failed to get bot username: {e}")
                    self.bot_username = "WhiteCat"

        # Check triggers
        trigger_result = await self.trigger_registry.check_triggers(message)

        # Store message for passive listening (all user messages), unless an
        # earlier handler (e.g. summary) already stored it this pipeline run
        if not ctx.data.get('message_stored'):
            user_id, username, is_forwarded = extract_sender_info(message)
            try:
                self.conversation_manager.add_message(
                    chat_id=message.chat.id,
                    user_id=user_id,
                    username=username,
                    text=text,
                    timestamp=message.date,
                    role="user",
                    is_bot=False,
                    is_trigger=bool(trigger_result),
                    is_forwarded=is_forwarded
                )
                ctx.data['message_stored'] = True
                logger.debug(f"[AI] Stored message from @{username} in chat {message.chat.id}")
            except Exception as e:
                logger.error(f"[AI] Failed to store message: {e}")

        # Return True only if triggered (reactive response)
        if trigger_result:
            # Store trigger result in context for process() to use
            ctx.data['ai_trigger'] = trigger_result[0]
            ctx.data['ai_user_message'] = trigger_result[1]
            return True

        return False

    async def process(self, ctx: PipelineContext) -> None:
        """
        Process message with AI and reply to user.

        Args:
            ctx: Pipeline context containing message and bot info
        """
        message = ctx.message

        # Retrieve trigger data from context
        trigger = ctx.data.get('ai_trigger')
        user_message = ctx.data.get('ai_user_message')

        if user_message is None:
            # Shouldn't happen, but safety check
            logger.error("[AI] No user message in context data")
            ctx.stop()
            return

        logger.info(f"[AI] Processing message from user {message.from_user.id}")
        logger.info(f"[AI] Triggered by: {trigger}")

        # Validate message not empty
        if not user_message:
            logger.info("[AI] Empty message received, replying with help text")
            await message.reply_text(
                "Meow! I can't help you without a message, friend.\n"
                "Please tell me something after the command, in a reply, or when mentioning me.\n"
                "Example: /cat What is the weather today?"
            )
            ctx.stop()
            return

        try:
            # Show typing indicator
            await ctx.context.bot.send_chat_action(
                chat_id=message.chat_id,
                action=ChatAction.TYPING
            )

            # Get chat ID
            chat_id = message.chat.id

            # Process message with AI (rolling window of last 250 messages maintained).
            # The triggering message was already stored in should_process(); it is
            # sent to Gemini as the live prompt (with @username attribution), so it
            # must be excluded from history to avoid the model seeing it twice.
            _, username, _ = extract_sender_info(message)
            logger.info(f"[AI] Calling Gemini API for user message: {user_message[:50]}...")
            response = await self.processor.process_message(
                chat_id,
                user_message,
                username=username,
                exclude_last_from_history=ctx.data.get('message_stored', False)
            )

            # Reply to user
            await message.reply_text(response)
            logger.info(f"[AI] Response sent to user {message.from_user.id}")

            # Capture bot's message immediately after sending
            try:
                self.conversation_manager.add_message(
                    chat_id=chat_id,
                    user_id=0,  # Bot user ID placeholder
                    username=self.bot_username or "WhiteCat",
                    text=response,
                    timestamp=datetime.now(),
                    role="model",
                    is_bot=True,
                    is_trigger=False
                )
                logger.debug(f"[AI] Stored bot response in chat {chat_id}")
            except Exception as e:
                logger.error(f"[AI] Failed to store bot message: {e}")

        except Exception as e:
            logger.error(f"[AI] Error processing message: {e}", exc_info=True)
            await message.reply_text(
                "Sorry, I encountered an error processing your request. "
                "Please try again later."
            )

        # Always stop pipeline after processing AI message
        ctx.stop()
