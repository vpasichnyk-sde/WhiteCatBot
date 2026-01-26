"""
RapidAPI TikTok No Watermark2 Provider
Provider for TikTok video downloads using tiktok-video-no-watermark2.p.rapidapi.com
Supports HD video quality
"""

import json
import logging
import http.client
from urllib.parse import quote
from video_pipeline.services.tiktok import TikTokProvider

logger = logging.getLogger(__name__)


class TikTokNoWatermark2Provider(TikTokProvider):
    """Provider using RapidAPI's tiktok-video-no-watermark2.p.rapidapi.com"""

    PROVIDER_NAME = "TIKTOK_NOWATERMARK2"
    DEFAULT_PRIORITY = 85  # Slightly lower than API1, used as fallback

    def __init__(self, api_key: str, api_host: str = 'tiktok-video-no-watermark2.p.rapidapi.com'):
        super().__init__("TikTok-NoWatermark2")
        self.api_key = api_key
        self.api_host = api_host

    def get_video_url(self, tiktok_url: str) -> str | None:
        """
        Get video URL using RapidAPI TikTok No Watermark2 service.

        Priority order:
        1. 'hdplay' - HD quality (if available)
        2. 'play' - Standard quality without watermark
        3. 'wmplay' - With watermark (last resort)
        """
        logger.info(f"[{self.name}] ========== PROVIDER START ==========")
        logger.info(f"[{self.name}] TikTok URL: {tiktok_url}")
        logger.info(f"[{self.name}] API Host: {self.api_host}")
        logger.info(f"[{self.name}] API Key: {self.api_key[:10]}...{self.api_key[-4:]}")

        conn = None
        try:
            logger.info(f"[{self.name}] Creating HTTPS connection to {self.api_host}...")
            conn = http.client.HTTPSConnection(self.api_host)

            # URL encode the TikTok URL for the query parameter
            # Include hd=1 parameter to request HD quality
            encoded_url = quote(tiktok_url, safe='')
            endpoint = f"/?url={encoded_url}&hd=1"
            logger.info(f"[{self.name}] Request endpoint: {endpoint}")

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

            # Parse JSON response
            logger.info(f"[{self.name}] Parsing JSON response...")
            response_json = json.loads(data.decode('utf-8'))
            logger.info(f"[{self.name}] Parsed JSON type: {type(response_json)}")
            logger.info(f"[{self.name}] Parsed JSON: {json.dumps(response_json, indent=2)[:1000]}")

            # Extract video URL from response
            # Response structure: {"code": 0, "msg": "success", "data": {"hdplay": "...", "play": "...", "wmplay": "..."}}
            logger.info(f"[{self.name}] Extracting video URL from response...")

            if response_json.get('code') != 0:
                logger.error(f"[{self.name}] ✗ API returned error code: {response_json.get('code')}")
                logger.error(f"[{self.name}] Message: {response_json.get('msg', 'No message')}")
                return None

            if 'data' not in response_json:
                logger.error(f"[{self.name}] ✗ No 'data' field in response")
                return None

            data_obj = response_json['data']

            # Try 'hdplay' first (HD quality), then 'play' (standard no watermark), fallback to 'wmplay' (with watermark)
            video_url = data_obj.get('hdplay') or data_obj.get('play') or data_obj.get('wmplay')

            if video_url:
                # Determine which quality we got
                if data_obj.get('hdplay'):
                    video_type = 'hdplay'
                    quality_info = 'HD quality, no watermark'
                elif data_obj.get('play'):
                    video_type = 'play'
                    quality_info = 'standard quality, no watermark'
                else:
                    video_type = 'wmplay'
                    quality_info = 'standard quality, with watermark'

                logger.info(f"[{self.name}] ✓ Successfully extracted video URL ({video_type} - {quality_info})")
                logger.info(f"[{self.name}] Video URL: {video_url}")

                # Log available quality options
                if 'hd_size' in data_obj:
                    logger.info(f"[{self.name}] HD size available: {data_obj['hd_size']} bytes ({data_obj['hd_size'] / 1024 / 1024:.2f} MB)")
                if 'size' in data_obj:
                    logger.info(f"[{self.name}] Standard size: {data_obj['size']} bytes ({data_obj['size'] / 1024 / 1024:.2f} MB)")

                logger.info(f"[{self.name}] ========== PROVIDER SUCCESS ==========")
                return video_url
            else:
                logger.error(f"[{self.name}] ✗ No 'hdplay', 'play', or 'wmplay' URL found in response")
                logger.error(f"[{self.name}] Available keys in data: {list(data_obj.keys())}")
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
