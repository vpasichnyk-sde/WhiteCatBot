"""
Trigger system for AI handler.
Auto-discovery of trigger types with priority-based checking.
"""

import os
import logging
import importlib
import inspect
from abc import ABC, abstractmethod
from typing import Optional, List, Type
from pathlib import Path
from telegram import Message

logger = logging.getLogger(__name__)


class BaseTrigger(ABC):
    """Base class for all AI handler triggers."""

    # Subclasses should define these
    TRIGGER_NAME = None           # e.g., "AI_COMMAND"
    DEFAULT_PRIORITY = 50         # 0-100, higher checked first
    DEFAULT_ENABLED = True        # Default enabled state

    def __init__(self):
        self.priority = self.DEFAULT_PRIORITY
        self.enabled = self.DEFAULT_ENABLED
        self._bot_username = None
        self._bot_id = None

    async def set_bot_identity(self, bot_username: str, bot_id: int) -> None:
        """Store bot identity for mention/reply checks."""
        self._bot_username = bot_username
        self._bot_id = bot_id

    @abstractmethod
    async def should_trigger(self, message: Message) -> bool:
        """
        Check if this trigger matches the message.

        Args:
            message: Telegram Message object

        Returns:
            True if trigger matches, False otherwise
        """
        pass

    @abstractmethod
    def extract_user_message(self, message_text: str) -> Optional[str]:
        """
        Extract user message from triggered text.

        Args:
            message_text: Full message text

        Returns:
            Extracted user message (command removed), or None if invalid
        """
        pass

    def __str__(self) -> str:
        return self.__class__.__name__


def discover_triggers() -> List[Type[BaseTrigger]]:
    """
    Automatically discover all trigger classes in triggers/ folder.

    Returns:
        List of trigger classes (not instances)
    """
    triggers = []
    current_dir = Path(__file__).parent

    # Get all .py files in triggers/ except __init__.py
    for file_path in current_dir.glob("*.py"):
        if file_path.name.startswith("_"):
            continue

        module_name = file_path.stem
        try:
            # Import from ai_handler_pipeline.triggers.module_name
            module = importlib.import_module(f"ai_handler_pipeline.triggers.{module_name}")

            # Find all classes that inherit from BaseTrigger
            for name, obj in inspect.getmembers(module, inspect.isclass):
                if (issubclass(obj, BaseTrigger) and
                    obj is not BaseTrigger and
                    obj.__module__ == module.__name__):
                    triggers.append(obj)
                    logger.debug(f"Discovered trigger: {obj.__name__} from {module_name}")

        except Exception as e:
            logger.error(f"Could not load trigger from {module_name}: {e}")

    return triggers


def load_triggers_from_env() -> List[BaseTrigger]:
    """
    Load and initialize triggers based on environment variables.

    Each trigger can define:
    - TRIGGER_NAME: For env var generation (e.g., "AI_COMMAND")
    - DEFAULT_PRIORITY: Priority value (0-100, higher checked first)
    - DEFAULT_ENABLED: Default enabled state

    Environment variables:
    - {TRIGGER_NAME}_ENABLED: Set to "false" to disable

    Returns:
        List of initialized trigger instances (sorted by priority, highest first)
    """
    trigger_classes = discover_triggers()

    if not trigger_classes:
        logger.warning("No triggers found in ai_handler_pipeline/triggers/")
        return []

    initialized_triggers = []

    logger.info("[AI] Auto-discovering AI triggers...")

    for trigger_class in trigger_classes:
        try:
            trigger = trigger_class()

            # Load config from environment if TRIGGER_NAME is defined
            if hasattr(trigger_class, 'TRIGGER_NAME') and trigger_class.TRIGGER_NAME:
                trigger_name = trigger_class.TRIGGER_NAME

                # Check if trigger is disabled
                enabled_env = f"{trigger_name}_ENABLED"
                if os.getenv(enabled_env, "true").lower() == "false":
                    logger.info(f"[AI]   ⊘ Skipping {trigger} (disabled via {enabled_env})")
                    continue

            initialized_triggers.append(trigger)
            logger.info(f"[AI]   ✓ Loaded {trigger} (priority: {trigger.priority})")

        except Exception as e:
            logger.error(f"[AI]   ✗ Failed to initialize {trigger_class.__name__}: {e}")

    # Sort by priority (highest first)
    initialized_triggers.sort(key=lambda t: t.priority, reverse=True)

    logger.info(f"[AI] Total triggers loaded: {len(initialized_triggers)}")
    return initialized_triggers


__all__ = ['BaseTrigger', 'discover_triggers', 'load_triggers_from_env']
