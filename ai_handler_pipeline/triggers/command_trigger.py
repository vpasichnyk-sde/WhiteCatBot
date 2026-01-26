"""Command-based trigger for AI handler."""

import logging
from typing import Optional
from telegram import Message
from . import BaseTrigger

logger = logging.getLogger(__name__)


class CommandTrigger(BaseTrigger):
    """Trigger on specific commands like /cat or /кіт."""

    TRIGGER_NAME = "AI_COMMAND"
    DEFAULT_PRIORITY = 80  # Higher than reply/mention (more explicit)

    def __init__(self, commands: Optional[list[str]] = None):
        """
        Initialize command trigger.

        Args:
            commands: List of commands to recognize (default: ['/cat', '/кіт'])
        """
        super().__init__()
        self.commands = commands or ['/cat', '/кіт']
        logger.debug(f"[AI] CommandTrigger initialized with commands: {self.commands}")

    async def should_trigger(self, message: Message) -> bool:
        """Check if message starts with any configured command."""
        if not message.text:
            return False

        text = message.text.strip()
        return any(text.startswith(cmd) for cmd in self.commands)

    def extract_user_message(self, message_text: str) -> Optional[str]:
        """
        Extract user message by removing command prefix.

        Args:
            message_text: Full message text

        Returns:
            User message with command removed, empty string if just command
        """
        text = message_text.strip()

        for cmd in self.commands:
            if text.startswith(cmd):
                # Remove command and strip whitespace
                user_msg = text[len(cmd):].strip()
                return user_msg  # Can be empty string (will trigger help message)

        return None
