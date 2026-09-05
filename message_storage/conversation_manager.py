"""
Conversation context manager for AI handler.
Stores conversation history per chat in memory with a rolling window.
"""

import logging
from collections import deque, defaultdict
from datetime import datetime
from threading import Lock
from typing import List, Dict, Any, Optional, Tuple
from google.genai import types

logger = logging.getLogger(__name__)


def extract_sender_info(message) -> Tuple[int, str, bool]:
    """
    Extract (user_id, username, is_forwarded) from a Telegram message.

    Forwarded messages are attributed to the original sender when Telegram
    exposes it (hidden-privacy forwards fall back to "Forwarded"/user_id 0).

    Args:
        message: Telegram Message object

    Returns:
        Tuple of (user_id, username, is_forwarded)
    """
    if message.forward_origin:
        user_id = 0
        username = "Forwarded"
        sender_user = getattr(message.forward_origin, 'sender_user', None)
        if sender_user:
            user_id = sender_user.id
            username = sender_user.username or sender_user.first_name or "Forwarded"
        return user_id, username, True

    user_id = message.from_user.id if message.from_user else 0
    username = "Unknown"
    if message.from_user:
        username = (
            message.from_user.username or
            message.from_user.first_name or
            f"User{message.from_user.id}"
        )
    return user_id, username, False


class ConversationManager:
    """
    Manages conversation context for multiple chats.

    Stores the last N messages per chat in memory using a rolling window.
    Messages stored with metadata (username, timestamp, etc.) and converted
    to Gemini API format on-demand.
    Thread-safe for concurrent access from multiple chats.
    """

    def __init__(self, max_messages: int = 250):
        """
        Initialize the conversation manager.

        Args:
            max_messages: Maximum number of messages to store per chat (default: 250)
        """
        self.max_messages = max_messages
        # Use deque with maxlen for automatic rolling window
        # Store dicts with metadata instead of types.Content directly
        self.conversations: defaultdict[int, deque] = defaultdict(
            lambda: deque(maxlen=max_messages)
        )
        self.lock = Lock()
        logger.info(f"[AI] ConversationManager initialized with max_messages={max_messages}")

    def add_message(
        self,
        chat_id: int,
        user_id: int,
        username: str,
        text: str,
        timestamp: datetime,
        role: str,
        is_bot: bool = False,
        is_trigger: bool = False,
        is_forwarded: bool = False
    ) -> None:
        """
        Add a message to the conversation history with full metadata.

        Args:
            chat_id: Telegram chat ID
            user_id: Telegram user ID
            username: User's display name (@username or first name)
            text: Message content/text
            timestamp: Message timestamp
            role: Message role ("user" or "model")
            is_bot: Whether message is from the bot (default: False)
            is_trigger: Whether this message triggered a response (default: False)
            is_forwarded: Whether message was forwarded (default: False)
        """
        if role not in ("user", "model"):
            raise ValueError(f"Invalid role: {role}. Must be 'user' or 'model'")

        # Store message with rich metadata
        message = {
            "user_id": user_id,
            "username": username,
            "text": text,
            "timestamp": timestamp,
            "role": role,
            "is_bot": is_bot,
            "is_trigger": is_trigger,
            "is_forwarded": is_forwarded
        }

        with self.lock:
            self.conversations[chat_id].append(message)
            history_size = len(self.conversations[chat_id])
            logger.debug(
                f"[AI] Added {role} message from @{username} to chat {chat_id}, "
                f"history size: {history_size}/{self.max_messages}"
            )

    def _format_message_for_gemini(self, msg: Dict[str, Any]) -> types.Content:
        """
        Convert stored message dict to Gemini API format.

        Args:
            msg: Message dictionary with metadata

        Returns:
            types.Content object for Gemini API
        """
        # Prepend username to user messages for context attribution
        if msg["role"] == "user" and not msg["is_bot"]:
            text = f"@{msg['username']}: {msg['text']}"
        else:
            # Bot messages without username prefix
            text = msg["text"]

        return types.Content(
            role=msg["role"],
            parts=[types.Part.from_text(text=text)]
        )

    def get_history(self, chat_id: int, exclude_last: bool = False) -> List[types.Content]:
        """
        Retrieve conversation history for a specific chat.

        Converts stored messages (with metadata) to Gemini API format.

        Args:
            chat_id: Telegram chat ID
            exclude_last: If True, omit the most recent message (used when the
                caller sends that message to Gemini separately as the live prompt)

        Returns:
            List of Content objects in google-genai format
        """
        with self.lock:
            raw_messages = list(self.conversations[chat_id])

            if exclude_last and raw_messages:
                raw_messages = raw_messages[:-1]

            # Convert each stored message to Gemini format
            history = [
                self._format_message_for_gemini(msg)
                for msg in raw_messages
            ]

            logger.debug(f"[AI] Retrieved {len(history)} messages for chat {chat_id}")
            return history

    def get_raw_history(
        self,
        chat_id: int,
        limit: Optional[int] = None,
        include_bot: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Retrieve raw message dicts for a specific chat (used by summarization).

        Args:
            chat_id: Telegram chat ID
            limit: If set, return only the last N matching messages
            include_bot: Whether to include the bot's own messages (default: False)

        Returns:
            List of message dictionaries (oldest to newest)
        """
        with self.lock:
            history = [
                msg for msg in self.conversations[chat_id]
                if include_bot or not msg["is_bot"]
            ]

        if limit and limit < len(history):
            history = history[-limit:]
        logger.debug(f"[STORAGE] Retrieved {len(history)} raw messages for chat {chat_id}")
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
                logger.info(f"[AI] Cleared {message_count} messages from chat {chat_id}")
            else:
                logger.debug(f"[AI] No history to clear for chat {chat_id}")

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
