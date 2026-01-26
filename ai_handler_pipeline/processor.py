"""Google Gemini API processor for AI handler."""
import logging
import os
from pathlib import Path
from google import genai
from google.genai import types

logger = logging.getLogger(__name__)


class GeminiProcessor:
    """Handles Google Gemini API interaction."""

    def __init__(self):
        """Initialize Gemini processor with API key and configuration."""
        self.api_key = os.environ.get("GEMINI_API_KEY")
        if not self.api_key:
            logger.error("[AI] GEMINI_API_KEY not found in environment variables")
            raise ValueError("GEMINI_API_KEY is required")

        self.client = genai.Client(api_key=self.api_key)
        self.model = "gemini-flash-latest"

        # Load system instruction from txt file
        instruction_path = Path(__file__).parent / "system_instruction.txt"
        try:
            with open(instruction_path, "r", encoding="utf-8") as f:
                self.system_instruction = f.read().strip()
            logger.info(f"[AI] Loaded system instruction from {instruction_path}")
        except Exception as e:
            logger.error(f"[AI] Failed to load system instruction: {e}", exc_info=True)
            self.system_instruction = "be nice and gentle."

        # Configure tools
        self.tools = [
            types.Tool(googleSearch=types.GoogleSearch()),
        ]

        # Configure generation settings
        self.generate_content_config = types.GenerateContentConfig(
            thinking_config=types.ThinkingConfig(
                thinking_budget=-1,  # Unlimited thinking budget
            ),
            tools=self.tools,
            system_instruction=[
                types.Part.from_text(text=self.system_instruction),
            ],
        )

        logger.info("[AI] GeminiProcessor initialized successfully")

    async def process_message(self, user_message: str) -> str:
        """
        Process user message with Gemini API and return full response.

        Args:
            user_message: The user's message text

        Returns:
            The AI-generated response text

        Raises:
            Exception: If API call fails
        """
        logger.info(f"[AI] Sending request to Gemini API for message: {user_message[:50]}...")

        try:
            # Prepare contents
            contents = [
                types.Content(
                    role="user",
                    parts=[
                        types.Part.from_text(text=user_message),
                    ],
                ),
            ]

            # Collect streaming response
            full_response = []

            for chunk in self.client.models.generate_content_stream(
                model=self.model,
                contents=contents,
                config=self.generate_content_config,
            ):
                if chunk.text:
                    full_response.append(chunk.text)

            response_text = ''.join(full_response)
            logger.info(f"[AI] Response received, length: {len(response_text)} characters")

            return response_text

        except Exception as e:
            logger.error(f"[AI] Error calling Gemini API: {e}", exc_info=True)
            raise
