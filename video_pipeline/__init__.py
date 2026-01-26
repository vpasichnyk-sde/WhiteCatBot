"""
Video download feature module.

This module contains everything related to video downloading:
- Service routing and URL matching
- Video services (Instagram, TikTok, etc.)
- HTTP download logic
- Pipeline handler for Telegram integration
"""

from video_pipeline.handler import VideoDownloadHandler

# For extending with new services
from video_pipeline.services import BaseService, BaseProvider

__all__ = [
    'VideoDownloadHandler',
    'BaseService',
    'BaseProvider',
]
