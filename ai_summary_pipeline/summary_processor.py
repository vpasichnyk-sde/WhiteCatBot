"""Google Gemini API processor for chat summarization."""
import logging
import os
from pathlib import Path
from typing import List, Dict, Any
from google import genai
from google.genai import types

logger = logging.getLogger(__name__)


def _load_system_instruction() -> str:
    """Load system instruction from file."""
    instruction_file = Path(__file__).parent / "system_instruction.txt"
    try:
        with open(instruction_file, "r", encoding="utf-8") as f:
            return f.read().strip()
    except Exception as e:
        logger.error(f"[SUMMARY] Failed to load system instruction from {instruction_file}: {e}")
        raise


# System instruction for summarization
SYSTEM_INSTRUCTION = _load_system_instruction()


class SummaryProcessor:
    """Handles Google Gemini API interaction for chat summarization."""

    def __init__(self):
        """
        Initialize Gemini processor with API key and configuration.
        """
        self.api_key = os.environ.get("GEMINI_API_KEY")
        if not self.api_key:
            logger.error("[SUMMARY] GEMINI_API_KEY not found in environment variables")
            raise ValueError("GEMINI_API_KEY is required")

        self.client = genai.Client(api_key=self.api_key)
        self.model = "gemini-2.0-flash-lite"

        # Configure generation settings for summarization
        # Lower temperature than chat (0.3 vs 0.85) for more factual summaries
        # No Google Search tool - summaries based only on provided messages
        self.generate_content_config = types.GenerateContentConfig(
            temperature=0.3,
            max_output_tokens=2048,
            system_instruction=SYSTEM_INSTRUCTION,
        )

        logger.info("[SUMMARY] SummaryProcessor initialized with gemini-2.0-flash-lite")

    def _format_messages_for_summary(self, messages: List[Dict[str, Any]]) -> str:
        """
        Format message history as chat transcript for Gemini.

        Args:
            messages: List of message dicts with user_id, username, text, timestamp, is_forwarded

        Returns:
            Formatted transcript string
        """
        lines = []
        for msg in messages:
            timestamp = msg["timestamp"].strftime("%Y-%m-%d %H:%M")
            username = msg["username"]
            text = msg["text"]

            # Format: [timestamp] @username: text
            lines.append(f"[{timestamp}] @{username}: {text}")

        # Add instruction at the end
        transcript = "\n".join(lines)
        return f"{transcript}\n\nPlease summarize the above conversation."

    async def generate_summary(self, chat_id: int, messages: List[Dict[str, Any]]) -> str:
        """
        Generate summary from message history using Gemini API.

        Args:
            chat_id: Telegram chat ID (for logging)
            messages: List of message dicts to summarize

        Returns:
            Summary text from Gemini

        Raises:
            Exception: If API call fails
        """
        logger.info(f"[SUMMARY] Generating summary for chat_id={chat_id} from {len(messages)} messages")

        try:
            # Format messages as transcript
            prompt = self._format_messages_for_summary(messages)

            # Call Gemini API (no history - standalone request)
            response = self.client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=self.generate_content_config
            )

            summary_text = response.text
            logger.info(f"[SUMMARY] Summary generated for chat_id={chat_id}, length: {len(summary_text)} characters")

            return summary_text

        except Exception as e:
            logger.error(f"[SUMMARY] Error calling Gemini API for chat_id={chat_id}: {e}", exc_info=True)
            raise
