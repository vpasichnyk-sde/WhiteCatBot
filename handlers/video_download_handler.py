"""Video download handler for the pipeline."""

import logging
from pipeline import PipelineHandler, PipelineContext
from video_pipeline import VideoDownloadHandler as VideoHandler

logger = logging.getLogger(__name__)


class VideoDownloadHandler(PipelineHandler):
    """
    Auto-discovered video download handler.

    Wraps the VideoDownloadHandler from video_pipeline module.
    """

    HANDLER_NAME = "VIDEO_DOWNLOAD"
    DEFAULT_PRIORITY = 100

    def __init__(self):
        super().__init__()
        self._video_handler = VideoHandler()

    async def process(self, ctx: PipelineContext) -> None:
        """Delegate to the video pipeline handler."""
        await self._video_handler.process(ctx)
