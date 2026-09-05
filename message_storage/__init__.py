"""
Shared message storage module for WhiteCat Bot.
Provides conversation context management that can be used across different features.

All features share ONE ConversationManager instance (get_conversation_manager)
so each message is stored once and both the AI chat and summary pipelines read
from the same rolling window.
"""
from .conversation_manager import ConversationManager, extract_sender_info

MAX_MESSAGES = 250

_shared_manager: ConversationManager | None = None


def get_conversation_manager() -> ConversationManager:
    """Return the process-wide shared ConversationManager instance."""
    global _shared_manager
    if _shared_manager is None:
        _shared_manager = ConversationManager(max_messages=MAX_MESSAGES)
    return _shared_manager


__all__ = ['ConversationManager', 'get_conversation_manager', 'extract_sender_info', 'MAX_MESSAGES']
