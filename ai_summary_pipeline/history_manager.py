"""
Message history manager for summary pipeline.
Stores all chat messages in memory with a rolling window.
"""

import logging
from collections import deque, defaultdict
from datetime import datetime
from threading import Lock
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


class HistoryManager:
    """
    Manages message history for multiple chats.

    Stores all text messages from chat with rolling window.
    Unlike ConversationManager (user/model pairs for AI context),
    this stores raw message metadata for summarization.
    Thread-safe for concurrent access from multiple chats.
    """

    def __init__(self, max_messages: int = 200):
        """
        Initialize the history manager.

        Args:
            max_messages: Maximum number of messages to store per chat (default: 200)
        """
        self.max_messages = max_messages
        # Use deque with maxlen for automatic rolling window
        self.histories: defaultdict[int, deque] = defaultdict(
            lambda: deque(maxlen=max_messages)
        )
        self.lock = Lock()
        logger.info(f"[SUMMARY] HistoryManager initialized with max_messages={max_messages}")

    def add_message(
        self,
        chat_id: int,
        user_id: int,
        username: str,
        text: str,
        timestamp: datetime,
        is_forwarded: bool = False
    ) -> None:
        """
        Add a message to the history.

        Args:
            chat_id: Telegram chat ID
            user_id: User ID (0 for forwarded with hidden sender)
            username: Username or first name
            text: Message text content
            timestamp: Message timestamp
            is_forwarded: Whether message was forwarded (default: False)
        """
        message = {
            "user_id": user_id,
            "username": username,
            "text": text,
            "timestamp": timestamp,
            "is_forwarded": is_forwarded
        }

        with self.lock:
            self.histories[chat_id].append(message)
            history_size = len(self.histories[chat_id])
            logger.debug(
                f"[SUMMARY] Stored message in chat {chat_id}, "
                f"history size: {history_size}/{self.max_messages}"
            )

    def get_history(self, chat_id: int, limit: int = 200) -> List[Dict[str, Any]]:
        """
        Retrieve message history for a specific chat.

        Args:
            chat_id: Telegram chat ID
            limit: Maximum number of messages to return (default: 200)

        Returns:
            List of message dictionaries (oldest to newest)
        """
        with self.lock:
            history = list(self.histories[chat_id])
            # Apply limit if specified (get last N messages)
            if limit and limit < len(history):
                history = history[-limit:]
            logger.debug(f"[SUMMARY] Retrieved {len(history)} messages for chat {chat_id}")
            return history

    def clear_chat(self, chat_id: int) -> None:
        """
        Clear message history for a specific chat.

        Args:
            chat_id: Telegram chat ID
        """
        with self.lock:
            if chat_id in self.histories:
                message_count = len(self.histories[chat_id])
                del self.histories[chat_id]
                logger.info(f"[SUMMARY] Cleared {message_count} messages from chat {chat_id}")
            else:
                logger.debug(f"[SUMMARY] No history to clear for chat {chat_id}")

    def get_stats(self) -> dict:
        """
        Get statistics about stored message histories.

        Returns:
            Dictionary with stats: total_chats, total_messages, avg_messages_per_chat
        """
        with self.lock:
            total_chats = len(self.histories)
            total_messages = sum(len(history) for history in self.histories.values())
            avg_messages = total_messages / total_chats if total_chats > 0 else 0

            return {
                "total_chats": total_chats,
                "total_messages": total_messages,
                "avg_messages_per_chat": round(avg_messages, 2),
                "max_messages_per_chat": self.max_messages
            }
