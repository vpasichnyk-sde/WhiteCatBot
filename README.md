# WhiteCat Bot 🐱

A powerful Telegram bot that automatically downloads videos from multiple platforms (Instagram, TikTok and more) using a plugin-based multi-service architecture.

## Why whiteCat?

Social media platforms often make it difficult to download videos directly. **whiteCat** solves this by:
- **Automatic detection** - Just send a video URL in any Telegram chat, and the bot replies with the downloaded video
- **Multi-platform support** - Works with Instagram, TikTok and easily extensible to other platforms
- **Reliable fallback** - Uses multiple providers per platform with priority-based failover
- **Zero storage** - Videos are processed in-memory and sent directly to Telegram

## Features

- 🎬 Download videos from Instagram, TikTok
- 🔄 Priority-based provider fallback for reliability
- 🔌 Plugin architecture - add new services without touching core code
- 📦 In-memory processing (no disk storage needed)
- 🚀 Deploy anywhere: Docker or local development
- 💾 100MB video size limit per download

## Prerequisites

- Python 3.11+
- Telegram Bot Token (get from [@BotFather](https://t.me/botfather))
- RapidAPI keys for video download services

## Architecture

### Two-Level Handler System

whiteCat uses a modular architecture with auto-discovery:

1. **Pipeline handlers** (`handlers/` directory): Auto-discovered wrappers that can be enabled/disabled via env vars
2. **Feature modules** (`video_pipeline/`): Self-contained features with their own logic

### Plugin System

The video feature uses an auto-discovery plugin system that automatically loads services and providers:

```
video_pipeline/
├── __init__.py           # Exports for video feature
├── handler.py            # Pipeline handler for Telegram integration
├── router.py             # Routes URLs to services
├── downloader.py         # Downloads videos to memory
└── services/
    ├── __init__.py       # BaseService, BaseProvider, auto-discovery
    ├── instagram/
    │   ├── __init__.py   # InstagramService + InstagramProvider
    │   └── providers/
    │       ├── instagram120.py
    │       ├── instagram_downloader.py
    │       └── instagram_looter2.py
    └── tiktok/
        ├── __init__.py   # TikTokService + TikTokProvider
        └── providers/
            ├── tiktok_api1.py
            └── tiktok_nowatermark2.py
```

### How It Works

1. **Message received** → Bot receives message in Telegram
2. **Pipeline** → Message flows through auto-discovered handlers by priority
3. **VideoDownloadHandler** → Detects URL in message
4. **ServiceRouter** → Matches URL to service (Instagram/TikTok/etc.)
5. **Service** → Tries providers by priority until one succeeds
6. **Download** → Fetches video to memory (max 100MB)
7. **Reply** → Sends video back to Telegram chat

### Priority-Based Fallback

Both services and providers use priority ordering (0-100, higher tried first). If one provider fails, the next is attempted automatically, ensuring reliability even when APIs go down.


## Quick Start

### 1. Configuration

Create a `.env` file in the project root:

```bash
# Required
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here

# Optional
BOT_USERNAME=@your_bot_username
LOG_LEVEL=INFO  # DEBUG, INFO, WARNING, ERROR, CRITICAL

# Handler Configuration (optional)
# VIDEO_DOWNLOAD_ENABLED=false  # Disable video downloads
# VIDEO_DOWNLOAD_PRIORITY=100   # Handler priority (0-100, higher runs first)

# Service Priorities (0-100, higher = tried first)
INSTAGRAM_PRIORITY=80
TIKTOK_PRIORITY=70

# Provider API Keys (get from RapidAPI)
INSTAGRAM120_API_KEY=your_rapidapi_key
INSTAGRAM120_PRIORITY=80

INSTAGRAM_DOWNLOADER_API_KEY=your_rapidapi_key
INSTAGRAM_DOWNLOADER_PRIORITY=50

TIKTOK_API1_API_KEY=your_rapidapi_key
TIKTOK_API1_PRIORITY=90

TIKTOK_NOWATERMARK2_API_KEY=your_rapidapi_key
TIKTOK_NOWATERMARK2_PRIORITY=85
```

**Getting API Keys:**
1. Sign up at [RapidAPI](https://rapidapi.com/)
2. Subscribe to the video download APIs you need (most have free tiers)
3. Copy your API key to the `.env` file

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

## Deployment Options

### Option 1: Local Development

Run the bot locally:

```bash
python bot.py
```

### Option 2: Docker (Local or Cloud)

**Build and run with Docker Compose:**

```bash
docker-compose up --build
```

**Docker Management Scripts (Ubuntu):**

For easier management on Ubuntu/Linux, use the included convenience scripts:

```bash
# Start the bot and show logs
./start-bot.sh

# Stop the bot
./stop-bot.sh

# Update and restart (git pull, rebuilds if needed)
./update-bot.sh

# View live logs
docker compose logs -f
```

**Deploy to cloud Docker services:**

1. Build the image:
   ```bash
   docker build -t whitecat-bot .
   ```

2. Push to your registry:
   ```bash
   docker tag whitecat-bot your-registry/whitecat-bot
   docker push your-registry/whitecat-bot
   ```

3. Deploy to your cloud provider (AWS ECS, Google Cloud Run, Azure Container Instances, etc.)

## Extending the Bot

### Adding Custom Handlers

Handlers are automatically discovered from the `handlers/` directory. To add a new feature handler:

1. Create a new Python file in `handlers/` (e.g., `handlers/my_feature.py`)
2. Create a class that inherits from `PipelineHandler`:

```python
from pipeline import PipelineHandler, PipelineContext

class MyFeatureHandler(PipelineHandler):
    HANDLER_NAME = "MY_FEATURE"  # For env var configuration
    DEFAULT_PRIORITY = 50  # 0-100, higher runs first

    async def process(self, ctx: PipelineContext) -> None:
        # Your handler logic here
        message = ctx.message
        # Process the message...
        # Call ctx.stop() to prevent further handlers from running
```

3. Configure via environment variables:
   - `MY_FEATURE_ENABLED=false` to disable
   - `MY_FEATURE_PRIORITY=75` to override priority

4. Restart the bot - the handler is automatically discovered and loaded

### Adding New Services and Providers

The plugin system makes it easy to add new platforms without modifying core code.

### Adding a New Service (e.g., Facebook)

1. **Create service directory and base files:**

```
video_pipeline/services/facebook/
├── __init__.py
└── providers/
    └── facebook_api1.py
```

2. **Define the service in `video_pipeline/services/facebook/__init__.py`:**

```python
from video_pipeline.services import BaseService, BaseProvider

class FacebookProvider(BaseProvider):
    """Base class for Facebook providers."""
    pass

class FacebookService(BaseService):
    SERVICE_NAME = "FACEBOOK"
    URL_PATTERN = r'https?://(?:www\.)?facebook\.com/watch/\?v=\d+'
    DEFAULT_PRIORITY = 70
    PROVIDER_BASE_CLASS = FacebookProvider
```

3. **Create a provider in `video_pipeline/services/facebook/providers/facebook_api1.py`:**

```python
from video_pipeline.services.facebook import FacebookProvider
import requests

class FacebookApi1(FacebookProvider):
    PROVIDER_NAME = "FACEBOOK_API1"  # Used for env vars
    DEFAULT_PRIORITY = 80

    def __init__(self, api_key: str):
        super().__init__("Facebook API 1")
        self.api_key = api_key

    def get_video_url(self, url: str) -> str | None:
        """Fetch direct video URL from Facebook URL."""
        try:
            response = requests.get(
                "https://facebook-downloader-api.example.com/download",
                params={"url": url},
                headers={"X-RapidAPI-Key": self.api_key}
            )
            data = response.json()
            return data.get("video_url")
        except Exception as e:
            print(f"FacebookApi1 error: {e}")
            return None
```

4. **Add configuration to `.env`:**

```bash
# Service priority
FACEBOOK_PRIORITY=70

# Provider API key and priority
FACEBOOK_API1_API_KEY=your_rapidapi_key
FACEBOOK_API1_PRIORITY=80
```

5. **Done!** The service is automatically discovered and loaded on bot restart.

### Adding a New Provider to Existing Service

To add another Instagram provider, for example:

1. **Create `video_pipeline/services/instagram/providers/instagram_api_new.py`:**

```python
from video_pipeline.services.instagram import InstagramProvider
import requests

class InstagramApiNew(InstagramProvider):
    PROVIDER_NAME = "INSTAGRAM_API_NEW"
    DEFAULT_PRIORITY = 60

    def __init__(self, api_key: str):
        super().__init__("Instagram API New")
        self.api_key = api_key

    def get_video_url(self, url: str) -> str | None:
        # Your implementation here
        pass
```

2. **Add to `.env`:**

```bash
INSTAGRAM_API_NEW_API_KEY=your_api_key
INSTAGRAM_API_NEW_PRIORITY=60
```

3. **Restart the bot** - the provider is automatically discovered and added to the priority queue.

### Provider Requirements

Each provider must:
- Inherit from the service's provider base class (e.g., `InstagramProvider`)
- Define `PROVIDER_NAME` (uppercase, used for env vars)
- Define `DEFAULT_PRIORITY` (0-100)
- Accept `api_key: str` in `__init__` if it needs an API key
- Implement `get_video_url(url: str) -> str | None` method
- Return direct video URL on success, `None` on failure

## Testing

Manual testing steps:

1. Start the bot (locally or deployed)
2. Open Telegram and find your bot
3. Send a video URL (Instagram, TikTok)
4. Verify the bot replies with the downloaded video and caption showing which service/provider was used

Example URLs to test:
- Instagram: `https://www.instagram.com/reel/...`
- TikTok: `https://www.tiktok.com/@user/video/...`

## Troubleshooting

**Bot doesn't respond to URLs:**
- Check `TELEGRAM_BOT_TOKEN` is correct
- Verify the URL pattern matches (check logs for `[ROUTER]` messages)
- Ensure at least one provider has a valid API key

**Provider failures:**
- Check API key is valid and has remaining quota
- Try lowering the priority of failing providers
- Add more providers as fallbacks

**Docker container exits:**
- Check logs with `docker-compose logs -f`
- Verify `.env` file exists and has `TELEGRAM_BOT_TOKEN`

## Contributing

Contributions welcome! To add support for new platforms:

1. Fork the repository
2. Create a new service following the plugin pattern above
3. Test thoroughly with multiple providers
4. Submit a pull request with:
   - Service and provider implementations
   - Updated `.env.example` with new variables
   - Documentation of the new service

## License
