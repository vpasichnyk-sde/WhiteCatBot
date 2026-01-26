"""
Instagram Service
Handles Instagram reels, posts, and stories
"""

from video_pipeline.services import BaseService, BaseProvider


class InstagramProvider(BaseProvider):
    """Base class for Instagram video providers."""
    pass


class InstagramService(BaseService):
    """Service for downloading Instagram videos."""

    SERVICE_NAME = "INSTAGRAM"
    URL_PATTERN = r'https?://(?:www\.)?instagram\.com/(reels?|p|stories)/[A-Za-z0-9_-]+(?:/[^\s]*)?'
    DEFAULT_PRIORITY = 80
    PROVIDER_BASE_CLASS = InstagramProvider


__all__ = ['InstagramProvider', 'InstagramService']
