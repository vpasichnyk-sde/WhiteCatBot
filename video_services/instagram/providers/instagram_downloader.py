"""
RapidAPI Instagram Downloader Provider
Secondary fallback provider
"""

import json
import logging
import http.client
import urllib.parse
from video_services.instagram import InstagramProvider

logger = logging.getLogger(__name__)


class RapidAPIInstagramDownloaderProvider(InstagramProvider):
    """
    Provider using RapidAPI's instagram-downloader-download-instagram-videos-stories1.p.rapidapi.com

    API Response Structure:
    {
      "error": false,
      "medias": [
        {"type": "video", "download_url": "..."}
      ]
    }
    """

    PROVIDER_NAME = "INSTAGRAM_DOWNLOADER"
    DEFAULT_PRIORITY = 50  # Medium priority - fallback provider

    def __init__(self, api_key: str):
        super().__init__("RapidAPI-InstagramDownloader")
        self.api_key = api_key
        self.api_host = 'instagram-downloader-download-instagram-videos-stories1.p.rapidapi.com'

    def get_video_url(self, instagram_url: str) -> str | None:
        """Get video URL using RapidAPI Instagram Downloader service."""
        logger.info(f"[{self.name}] ========== PROVIDER START ==========")
        logger.info(f"[{self.name}] Instagram URL: {instagram_url}")
        logger.info(f"[{self.name}] API Host: {self.api_host}")
        logger.info(f"[{self.name}] API Key: {self.api_key[:10]}...{self.api_key[-4:]}")

        conn = None
        try:
            logger.info(f"[{self.name}] Creating HTTPS connection...")
            conn = http.client.HTTPSConnection(self.api_host)

            # URL encode the Instagram URL
            encoded_url = urllib.parse.quote(instagram_url, safe='')
            endpoint = f"/get-info-rapidapi?url={encoded_url}"
            logger.info(f"[{self.name}] Endpoint: {endpoint}")

            headers = {
                'x-rapidapi-key': self.api_key,
                'x-rapidapi-host': self.api_host
            }
            logger.info(f"[{self.name}] Request headers: {headers}")

            logger.info(f"[{self.name}] Sending GET request...")
            conn.request("GET", endpoint, headers=headers)

            logger.info(f"[{self.name}] Waiting for response...")
            res = conn.getresponse()
            logger.info(f"[{self.name}] Response status: {res.status}")
            logger.info(f"[{self.name}] Response headers: {dict(res.headers)}")

            data = res.read()
            logger.info(f"[{self.name}] Response data length: {len(data)} bytes")
            logger.info(f"[{self.name}] Response data (raw): {data[:500]}")

            if res.status != 200:
                logger.error(f"[{self.name}] ✗ API returned status {res.status}: {data.decode('utf-8')}")
                return None

            logger.info(f"[{self.name}] Parsing JSON response...")
            response_json = json.loads(data.decode('utf-8'))
            logger.info(f"[{self.name}] Parsed JSON: {json.dumps(response_json, indent=2)[:1000]}")

            # Check for API error
            # API returns either {'error': False, 'medias': [...]} on success
            # or {'error': 'error message', 'details': '...'} on failure
            error_value = response_json.get('error')
            logger.info(f"[{self.name}] Error field value: {error_value} (type: {type(error_value)})")

            if error_value != False and error_value is not False:
                # error is either a string (error message) or True
                logger.error(f"[{self.name}] ✗ API returned error: {error_value}")
                if 'details' in response_json:
                    logger.error(f"[{self.name}] Error details: {response_json.get('details')}")
                return None

            # Extract medias array
            medias = response_json.get('medias', [])
            logger.info(f"[{self.name}] Medias array length: {len(medias)}")

            # Find first video in medias
            for idx, media in enumerate(medias):
                logger.info(f"[{self.name}] Media {idx}: type={media.get('type')}")
                if media.get('type') == 'video':
                    video_url = media.get('download_url')
                    if video_url:
                        logger.info(f"[{self.name}] ✓ Found video URL: {video_url}")
                        logger.info(f"[{self.name}] ========== PROVIDER SUCCESS ==========")
                        return video_url

            logger.error(f"[{self.name}] ✗ No video found in {len(medias)} media items")
            return None

        except json.JSONDecodeError as e:
            logger.error(f"[{self.name}] ✗ JSON decode error: {e}")
            logger.error(f"[{self.name}] Raw data: {data.decode('utf-8', errors='replace')[:500]}")
            return None
        except Exception as e:
            logger.error(f"[{self.name}] ✗ Error calling API: {type(e).__name__}: {e}", exc_info=True)
            return None
        finally:
            if conn:
                conn.close()
                logger.info(f"[{self.name}] Connection closed")
