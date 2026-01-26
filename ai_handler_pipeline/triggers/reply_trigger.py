"""Reply-based trigger for AI handler."""

import logging
from typing import Optional
from telegram import Message
from . import BaseTrigger

logger = logging.getLogger(__name__)


class ReplyTrigger(BaseTrigger):
    """Trigger when someone replies to bot's message."""

    TRIGGER_NAME = "AI_REPLY"
    DEFAULT_PRIORITY = 60  # Medium priority

    async def should_trigger(self, message: Message) -> bool:
        """Check if message is a reply to bot."""
        if not message.reply_to_message:
            return False

        if not self._bot_id:
            logger.warning("[AI] ReplyTrigger: bot_id not initialized")
            return False

        # Check if replying to a message from the bot
        is_reply_to_bot = message.reply_to_message.from_user.id == self._bot_id

        if is_reply_to_bot:
            logger.debug(f"[AI] Reply to bot detected from user {message.from_user.id}")

        return is_reply_to_bot

    def extract_user_message(self, message_text: str) -> Optional[str]:
        """
        Extract user message (entire text for replies).

        Args:
            message_text: Full message text

        Returns:
            Full message text as user message
        """
        return message_text.strip() if message_text else ""
