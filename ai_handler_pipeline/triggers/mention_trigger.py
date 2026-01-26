"""Mention-based trigger for AI handler."""

import logging
from typing import Optional
from telegram import Message, MessageEntity
from . import BaseTrigger

logger = logging.getLogger(__name__)


class MentionTrigger(BaseTrigger):
    """Trigger when bot is mentioned via @username."""

    TRIGGER_NAME = "AI_MENTION"
    DEFAULT_PRIORITY = 70  # Higher than reply (more explicit)

    async def should_trigger(self, message: Message) -> bool:
        """Check if message mentions the bot."""
        if not message.entities:
            return False

        if not self._bot_username:
            logger.warning("[AI] MentionTrigger: bot_username not initialized")
            return False

        # Check for @username mentions
        for entity in message.entities:
            if entity.type in [MessageEntity.MENTION, MessageEntity.TEXT_MENTION]:
                # Extract mentioned username
                if entity.type == MessageEntity.MENTION:
                    # Extract mention from message text
                    mention_text = message.text[entity.offset:entity.offset + entity.length]
                    # Remove @ symbol and compare
                    mentioned_username = mention_text.lstrip('@')

                    if mentioned_username.lower() == self._bot_username.lower():
                        logger.debug(f"[AI] Bot mention detected: {mention_text}")
                        return True

                elif entity.type == MessageEntity.TEXT_MENTION:
                    # Direct user mention (has .user property)
                    if entity.user and entity.user.id == self._bot_id:
                        logger.debug(f"[AI] Bot text mention detected")
                        return True

        return False

    def extract_user_message(self, message_text: str) -> Optional[str]:
        """
        Extract user message by removing bot mention.

        Args:
            message_text: Full message text

        Returns:
            Message with @bot_username removed
        """
        if not message_text:
            return ""

        text = message_text.strip()

        # Remove @bot_username from text
        if self._bot_username:
            mention_str = f"@{self._bot_username}"
            text = text.replace(mention_str, "").strip()

        return text
