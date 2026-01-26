"""Registry for managing AI handler triggers."""

import logging
from typing import List, Optional, Tuple
from telegram import Message
from .triggers import BaseTrigger, load_triggers_from_env

logger = logging.getLogger(__name__)


class TriggerRegistry:
    """
    Manages AI handler triggers with priority-based checking.

    Triggers are checked in priority order until one matches.
    """

    def __init__(self):
        """Initialize trigger registry and load triggers from environment."""
        self.triggers: List[BaseTrigger] = []
        self._bot_username: Optional[str] = None
        self._bot_id: Optional[int] = None
        self._identity_initialized = False

        # Auto-load triggers
        self._load_triggers()

    def _load_triggers(self) -> None:
        """Load triggers from environment configuration."""
        self.triggers = load_triggers_from_env()

        if not self.triggers:
            logger.warning("[AI] No triggers loaded - AI handler will not respond to any messages")

    async def initialize_bot_identity(self, bot) -> None:
        """
        Initialize bot identity for reply/mention triggers.

        Args:
            bot: Telegram bot instance
        """
        if self._identity_initialized:
            return

        try:
            bot_info = await bot.get_me()
            self._bot_username = bot_info.username
            self._bot_id = bot_info.id

            # Share identity with all triggers
            for trigger in self.triggers:
                await trigger.set_bot_identity(self._bot_username, self._bot_id)

            logger.info(f"[AI] Bot identity initialized: @{self._bot_username} (ID: {self._bot_id})")
            self._identity_initialized = True

        except Exception as e:
            logger.error(f"[AI] Failed to initialize bot identity: {e}")

    async def check_triggers(self, message: Message) -> Optional[Tuple[BaseTrigger, str]]:
        """
        Check all triggers in priority order.

        Args:
            message: Telegram Message object

        Returns:
            Tuple of (trigger, user_message) if matched, None otherwise
        """
        if not message or not message.text:
            return None

        logger.debug(f"[AI] Checking {len(self.triggers)} triggers...")

        for trigger in self.triggers:
            try:
                if await trigger.should_trigger(message):
                    logger.info(f"[AI] ✓ Trigger matched: {trigger}")

                    # Extract user message
                    user_message = trigger.extract_user_message(message.text)
                    if user_message is not None:
                        return (trigger, user_message)
                    else:
                        logger.debug(f"[AI] Trigger {trigger} matched but no valid message extracted")
                        return (trigger, "")  # Empty message = show help

            except Exception as e:
                logger.error(f"[AI] Error checking trigger {trigger}: {e}", exc_info=True)

        logger.debug("[AI] No triggers matched")
        return None
