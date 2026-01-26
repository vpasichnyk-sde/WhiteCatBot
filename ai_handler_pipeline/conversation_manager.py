"""
Conversation context manager for AI handler.
Stores conversation history per chat in memory with a rolling window.
"""

import logging
from collections import deque, defaultdict
from threading import Lock
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class ConversationManager:
    """
    Manages conversation context for multiple chats.

    Stores the last N messages per chat in memory using a rolling window.
    Thread-safe for concurrent access from multiple chats.
    """

    def __init__(self, max_messages: int = 50):
        """
        Initialize the conversation manager.

        Args:
            max_messages: Maximum number of messages to store per chat (default: 50)
        """
        self.max_messages = max_messages
        self.conversations: Dict[int, deque] = defaultdict(lambda: deque(maxlen=max_messages))
        self.lock = Lock()
        logger.info(f"ConversationManager initialized with max_messages={max_messages}")

    def add_message(self, chat_id: int, role: str, content: str) -> None:
        """
        Add a message to the conversation history.

        Args:
            chat_id: Telegram chat ID
            role: Message role ("user" or "model")
            content: Message content/text
        """
        if role not in ("user", "model"):
            raise ValueError(f"Invalid role: {role}. Must be 'user' or 'model'")

        message = {
            "role": role,
            "parts": [content]
        }

        with self.lock:
            self.conversations[chat_id].append(message)
            history_size = len(self.conversations[chat_id])
            logger.debug(
                f"Added {role} message to chat {chat_id}, "
                f"history size: {history_size}/{self.max_messages}"
            )

    def get_history(self, chat_id: int) -> List[dict]:
        """
        Retrieve conversation history for a specific chat.

        Args:
            chat_id: Telegram chat ID

        Returns:
            List of message dicts in Gemini API format:
            [{"role": "user"/"model", "parts": [text]}, ...]
        """
        with self.lock:
            history = list(self.conversations[chat_id])
            logger.debug(f"Retrieved {len(history)} messages for chat {chat_id}")
            return history

    def clear_chat(self, chat_id: int) -> None:
        """
        Clear conversation history for a specific chat.

        Args:
            chat_id: Telegram chat ID
        """
        with self.lock:
            if chat_id in self.conversations:
                message_count = len(self.conversations[chat_id])
                del self.conversations[chat_id]
                logger.info(f"Cleared {message_count} messages from chat {chat_id}")
            else:
                logger.debug(f"No history to clear for chat {chat_id}")

    def get_stats(self) -> dict:
        """
        Get statistics about stored conversations.

        Returns:
            Dictionary with stats: total_chats, total_messages, avg_messages_per_chat
        """
        with self.lock:
            total_chats = len(self.conversations)
            total_messages = sum(len(history) for history in self.conversations.values())
            avg_messages = total_messages / total_chats if total_chats > 0 else 0

            return {
                "total_chats": total_chats,
                "total_messages": total_messages,
                "avg_messages_per_chat": round(avg_messages, 2),
                "max_messages_per_chat": self.max_messages
            }
