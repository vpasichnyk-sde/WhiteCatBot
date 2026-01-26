"""
RapidAPI Instagram120 Provider
Primary provider for Instagram video downloads
"""

import json
import logging
import http.client
from video_pipeline.services.instagram import InstagramProvider

logger = logging.getLogger(__name__)


class RapidAPIInstagram120Provider(InstagramProvider):
    """Provider using RapidAPI's instagram120.p.rapidapi.com"""

    PROVIDER_NAME = "INSTAGRAM120"
    DEFAULT_PRIORITY = 80  # Higher priority - primary provider

    def __init__(self, api_key: str, api_host: str = 'instagram120.p.rapidapi.com'):
        super().__init__("RapidAPI-Instagram120")
        self.api_key = api_key
        self.api_host = api_host

    def get_video_url(self, instagram_url: str) -> str | None:
        """Get video URL using RapidAPI Instagram120 service."""
        logger.info(f"[{self.name}] ========== PROVIDER START ==========")
        logger.info(f"[{self.name}] Instagram URL: {instagram_url}")
        logger.info(f"[{self.name}] API Host: {self.api_host}")
        logger.info(f"[{self.name}] API Key: {self.api_key[:10]}...{self.api_key[-4:]}")

        conn = None
        try:
            logger.info(f"[{self.name}] Creating HTTPS connection to {self.api_host}...")
            conn = http.client.HTTPSConnection(self.api_host)

            payload = json.dumps({"url": instagram_url})
            logger.info(f"[{self.name}] Request payload: {payload}")

            headers = {
                'x-rapidapi-key': self.api_key,
                'x-rapidapi-host': self.api_host,
                'Content-Type': 'application/json'
            }
            logger.info(f"[{self.name}] Request headers: {headers}")

            logger.info(f"[{self.name}] Sending POST request to /api/instagram/links...")
            conn.request("POST", "/api/instagram/links", payload, headers)

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

            # Extract video URL from response: response[0]['urls'][0]['url']
            logger.info(f"[{self.name}] Extracting video URL from response...")
            logger.info(f"[{self.name}] Is list? {isinstance(response_json, list)}")
            if isinstance(response_json, list):
                logger.info(f"[{self.name}] List length: {len(response_json)}")
                if len(response_json) > 0:
                    logger.info(f"[{self.name}] First element keys: {response_json[0].keys() if isinstance(response_json[0], dict) else 'Not a dict'}")
                    logger.info(f"[{self.name}] Has 'urls' key? {'urls' in response_json[0] if isinstance(response_json[0], dict) else False}")
                    if 'urls' in response_json[0]:
                        logger.info(f"[{self.name}] URLs array length: {len(response_json[0]['urls'])}")

            if (isinstance(response_json, list) and len(response_json) > 0 and
                'urls' in response_json[0] and len(response_json[0]['urls']) > 0):

                video_url = response_json[0]['urls'][0]['url']
                logger.info(f"[{self.name}] ✓ Successfully extracted video URL: {video_url}")
                logger.info(f"[{self.name}] ========== PROVIDER SUCCESS ==========")
                return video_url
            else:
                logger.error(f"[{self.name}] ✗ Unexpected API response structure")
                logger.error(f"[{self.name}] Expected: list with element containing 'urls' array")
                logger.error(f"[{self.name}] Got: {type(response_json)} - {response_json}")
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
