"""Top-level AI handler wrapper for pipeline integration."""
import logging
from pipeline import PipelineHandler, PipelineContext
from ai_handler_pipeline import AIProcessingHandler

logger = logging.getLogger(__name__)


class AIHandler(PipelineHandler):
    """
    Top-level wrapper for AI handler.

    Integrates AI processing into the pipeline system with auto-discovery support.
    Can be configured via environment variables:
    - AI_HANDLER_ENABLED=false to disable
    - AI_HANDLER_PRIORITY=<num> to override default priority
    """

    HANDLER_NAME = "AI_HANDLER"
    DEFAULT_PRIORITY = 80  # Default priority, runs after video downloads but before fallback

    def __init__(self):
        """Initialize AI handler wrapper."""
        super().__init__()
        self._ai_handler = AIProcessingHandler()
        logger.info("[AI] AIHandler wrapper initialized")

    async def should_process(self, ctx: PipelineContext) -> bool:
        """
        Check if message should be processed.

        Args:
            ctx: Pipeline context

        Returns:
            True if message should be processed
        """
        return await self._ai_handler.should_process(ctx)

    async def process(self, ctx: PipelineContext) -> None:
        """
        Process message through AI handler.

        Args:
            ctx: Pipeline context
        """
        await self._ai_handler.process(ctx)
