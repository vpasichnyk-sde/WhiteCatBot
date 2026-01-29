"""Top-level summary handler wrapper for pipeline integration."""
import logging
from pipeline import PipelineHandler, PipelineContext
from ai_summary_pipeline import SummaryProcessingHandler

logger = logging.getLogger(__name__)


class SummaryHandler(PipelineHandler):
    """
    Top-level wrapper for summary handler.

    Integrates chat summarization into the pipeline system with auto-discovery support.
    Can be configured via environment variables:
    - SUMMARY_HANDLER_ENABLED=false to disable
    - SUMMARY_HANDLER_PRIORITY=<num> to override default priority
    """

    HANDLER_NAME = "SUMMARY_HANDLER"
    DEFAULT_PRIORITY = 90  # Higher than AI_HANDLER (80) to catch /summary commands first

    def __init__(self):
        """Initialize summary handler wrapper."""
        super().__init__()
        self._summary_handler = SummaryProcessingHandler()
        logger.info("[SUMMARY] SummaryHandler wrapper initialized")

    async def should_process(self, ctx: PipelineContext) -> bool:
        """
        Check if message should be processed (stores all text messages, returns True if triggered).

        Args:
            ctx: Pipeline context

        Returns:
            True if message contains trigger keyword
        """
        return await self._summary_handler.should_process(ctx)

    async def process(self, ctx: PipelineContext) -> None:
        """
        Process message through summary handler.

        Args:
            ctx: Pipeline context
        """
        await self._summary_handler.process(ctx)
