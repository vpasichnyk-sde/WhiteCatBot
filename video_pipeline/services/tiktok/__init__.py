"""
TikTok Service
Handles TikTok video downloads
"""

from video_pipeline.services import BaseService, BaseProvider


class TikTokProvider(BaseProvider):
    """Base class for TikTok video providers."""
    pass


class TikTokService(BaseService):
    """Service for downloading TikTok videos."""

    SERVICE_NAME = "TIKTOK"
    URL_PATTERN = r'https?://(?:www\.)?tiktok\.com/@[\w.-]+/video/\d+|https?://(?:vm|vt)\.tiktok\.com/[\w-]+'
    DEFAULT_PRIORITY = 70
    PROVIDER_BASE_CLASS = TikTokProvider


__all__ = ['TikTokProvider', 'TikTokService']
