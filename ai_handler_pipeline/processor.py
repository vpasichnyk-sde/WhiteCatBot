"""Google Gemini API processor for AI handler."""
import logging
import os
from pathlib import Path
from typing import List, TYPE_CHECKING
from google import genai
from google.genai import types

if TYPE_CHECKING:
    from .conversation_manager import ConversationManager

logger = logging.getLogger(__name__)


def _load_system_instruction() -> str:
    """Load system instruction from file."""
    instruction_file = Path(__file__).parent / "system_instruction.txt"
    try:
        with open(instruction_file, "r", encoding="utf-8") as f:
            return f.read().strip()
    except Exception as e:
        logger.error(f"[AI] Failed to load system instruction from {instruction_file}: {e}")
        raise


# System instruction for WhiteCat personality
SYSTEM_INSTRUCTION = _load_system_instruction()


class GeminiProcessor:
    """Handles Google Gemini API interaction with chat sessions."""

    def __init__(self, conversation_manager: "ConversationManager"):
        """
        Initialize Gemini processor with API key and configuration.

        Args:
            conversation_manager: ConversationManager instance for history management
        """
        self.api_key = os.environ.get("GEMINI_API_KEY")
        if not self.api_key:
            logger.error("[AI] GEMINI_API_KEY not found in environment variables")
            raise ValueError("GEMINI_API_KEY is required")

        self.client = genai.Client(api_key=self.api_key)
        self.model = "gemini-2.0-flash-lite"
        self.conversation_manager = conversation_manager

        # Configure generation settings with Google Search tool
        self.generate_content_config = types.GenerateContentConfig(
            temperature=0.85,
            max_output_tokens=1024,
            tools=[types.Tool(google_search=types.GoogleSearch())],
            system_instruction=SYSTEM_INSTRUCTION,
        )

        logger.info("[AI] GeminiProcessor initialized with gemini-2.0-flash-lite and Google Search")

    async def process_message(self, chat_id: int, user_message: str) -> str:
        """
        Process user message with Gemini API using chat session and return response.

        Args:
            chat_id: Telegram chat ID (used to maintain separate conversations)
            user_message: The user's message text

        Returns:
            The AI-generated response text

        Raises:
            Exception: If API call fails
        """
        logger.info(f"[AI] Processing message for chat_id={chat_id}: {user_message[:50]}...")

        try:
            # Get conversation history from ConversationManager (rolling window of last 50 messages)
            history = self.conversation_manager.get_history(chat_id)

            logger.debug(f"[AI] Creating chat session with {len(history)} history messages")

            # Create chat session with history
            chat = self.client.chats.create(
                model=self.model,
                config=self.generate_content_config,
                history=history
            )

            # Send message and get response
            response = chat.send_message(user_message)
            response_text = response.text

            # Store both user message and model response in ConversationManager
            # This maintains the rolling window of last 50 messages
            self.conversation_manager.add_message(chat_id, "user", user_message)
            self.conversation_manager.add_message(chat_id, "model", response_text)

            logger.info(f"[AI] Response received for chat_id={chat_id}, length: {len(response_text)} characters")

            return response_text

        except Exception as e:
            logger.error(f"[AI] Error calling Gemini API for chat_id={chat_id}: {e}", exc_info=True)
            raise
