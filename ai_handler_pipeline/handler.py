"""AI handler pipeline logic for Telegram bot."""
import logging
from telegram.constants import ChatAction
from pipeline import PipelineHandler, PipelineContext
from .processor import GeminiProcessor
from .trigger_registry import TriggerRegistry
from .conversation_manager import ConversationManager

logger = logging.getLogger(__name__)


class AIProcessingHandler(PipelineHandler):
    """Pipeline handler for AI-powered message processing using Google Gemini."""

    def __init__(self):
        """Initialize AI processing handler with Gemini processor and trigger registry."""
        super().__init__()

        # Initialize conversation manager (rolling window of 50 messages per chat)
        self.conversation_manager = ConversationManager(max_messages=50)

        try:
            self.processor = GeminiProcessor(self.conversation_manager)
            logger.info("[AI] AIProcessingHandler initialized successfully")
        except Exception as e:
            logger.error(f"[AI] Failed to initialize GeminiProcessor: {e}", exc_info=True)
            self.processor = None

        # Initialize trigger registry
        self.trigger_registry = TriggerRegistry()

    async def should_process(self, ctx: PipelineContext) -> bool:
        """
        Check if message should be processed by AI handler.

        Args:
            ctx: Pipeline context containing message info

        Returns:
            True if any trigger matches, False otherwise
        """
        if not ctx.message_text:
            return False

        # Check if processor is initialized
        if self.processor is None:
            return False

        # Initialize bot identity on first message (lazy loading)
        if not self.trigger_registry._identity_initialized:
            await self.trigger_registry.initialize_bot_identity(ctx.context.bot)

        # Check triggers
        trigger_result = await self.trigger_registry.check_triggers(ctx.message)

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

            # Process message with AI (rolling window of last 50 messages maintained)
            logger.info(f"[AI] Calling Gemini API for user message: {user_message[:50]}...")
            response = await self.processor.process_message(chat_id, user_message)

            # Reply to user
            await message.reply_text(response)
            logger.info(f"[AI] Response sent to user {message.from_user.id}")

        except Exception as e:
            logger.error(f"[AI] Error processing message: {e}", exc_info=True)
            await message.reply_text(
                "Sorry, I encountered an error processing your request. "
                "Please try again later."
            )

        # Always stop pipeline after processing AI message
        ctx.stop()
