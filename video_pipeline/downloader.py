"""
Video downloader module for whiteCat bot.

Handles downloading videos from URLs to memory buffers.
"""

import logging
from io import BytesIO
from typing import Optional

import requests

logger = logging.getLogger(__name__)

# Telegram bot file size limit is 2GB, but we use 100MB for memory/performance safety
# Increase this value if you need to download larger videos (max: 2000MB)
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB in bytes


async def download_video(video_url: str) -> Optional[tuple[BytesIO, Optional[str]]]:
    """
    Download video to memory.

    Args:
        video_url: Direct video URL

    Returns:
        Tuple of (BytesIO buffer, error_type) where error_type is:
        - None if successful
        - "too_large" if video exceeds size limit
        - "not_found" if video URL is invalid/not found (404)
        - "download_failed" for other errors
    """
    try:
        logger.info(f"[DOWNLOAD] Starting video download from: {video_url[:100]}...")
        logger.info(f"[DOWNLOAD] Full URL: {video_url}")
        logger.info(f"[DOWNLOAD] Max file size limit: {MAX_FILE_SIZE} bytes ({MAX_FILE_SIZE / (1024*1024):.1f}MB)")

        logger.info(f"[DOWNLOAD] Initiating HTTP GET request with streaming...")
        response = requests.get(video_url, stream=True, timeout=30)
        logger.info(f"[DOWNLOAD] Response received - Status Code: {response.status_code}")
        logger.info(f"[DOWNLOAD] Response Headers: {dict(response.headers)}")

        # Check for 404 or other client errors
        if response.status_code == 404:
            logger.error(f"[DOWNLOAD] ✗ Video not found (404)")
            return None, "not_found"

        response.raise_for_status()

        # Check content length
        content_length = response.headers.get('content-length')
        if content_length:
            content_length_int = int(content_length)
            logger.info(f"[DOWNLOAD] Content-Length header: {content_length_int} bytes ({content_length_int / (1024*1024):.2f}MB)")
            if content_length_int > MAX_FILE_SIZE:
                logger.error(f"[DOWNLOAD] Video too large: {content_length_int} bytes (max {MAX_FILE_SIZE})")
                return None, "too_large"
        else:
            logger.warning(f"[DOWNLOAD] No Content-Length header present, will check size during download")

        # Download to memory
        logger.info(f"[DOWNLOAD] Starting chunked download (chunk_size=16,384 bytes)...")
        video_buffer = BytesIO()
        downloaded = 0

        for chunk in response.iter_content(chunk_size=16384):
            if chunk:
                video_buffer.write(chunk)
                downloaded += len(chunk)
                
                # Check size while downloading
                if downloaded > MAX_FILE_SIZE:
                    logger.error(f"[DOWNLOAD] Video exceeded size limit during download: {downloaded} bytes")
                    return None, "too_large"

        video_buffer.seek(0)
        logger.info(f"[DOWNLOAD] ✓ Video downloaded successfully!")
        logger.info(f"[DOWNLOAD] Total size: {downloaded} bytes ({downloaded / (1024*1024):.2f}MB)")
        return video_buffer, None

    except requests.HTTPError as e:
        if e.response and e.response.status_code == 404:
            logger.error(f"[DOWNLOAD] ✗ Video not found (404)")
            return None, "not_found"
        logger.error(f"[DOWNLOAD] ✗ HTTP error downloading video: {type(e).__name__}: {e}")
        return None, "download_failed"
    except requests.RequestException as e:
        logger.error(f"[DOWNLOAD] ✗ Error downloading video: {type(e).__name__}: {e}")
        return None, "download_failed"
