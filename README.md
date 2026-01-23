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
- 🚀 Deploy anywhere: Docker, Render.com, or local development
- 💾 100MB video size limit per download

## Prerequisites

- Python 3.11+
- Telegram Bot Token (get from [@BotFather](https://t.me/botfather))
- RapidAPI keys for video download services

## Architecture

### Plugin System

whiteCat uses an auto-discovery plugin system that automatically loads services and providers:

```
video_services/
├── __init__.py           # BaseService, BaseProvider, auto-discovery
├── instagram/
│   ├── __init__.py       # InstagramService + InstagramProvider
│   └── providers/
│       ├── instagram120.py
│       ├── instagram_downloader.py
│       └── instagram_looter2.py
├── tiktok/
│   ├── __init__.py       # TikTokService + TikTokProvider
│   └── providers/
│       ├── tiktok_api1.py
│       └── tiktok_nowatermark2.py
```

### How It Works

1. **Message received** → Bot detects URL in message
2. **ServiceRouter** → Matches URL to service (Instagram/TikTok/etc.)
3. **Service** → Tries providers by priority until one succeeds
4. **Download** → Fetches video to memory (max 100MB)
5. **Reply** → Sends video back to Telegram chat

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
ENABLE_HEALTH_CHECK=true  # Set to false for local development

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

Run the bot locally without health check server:

```bash
ENABLE_HEALTH_CHECK=false python bot.py
```

Or with health check server (on port 8080):

```bash
python bot.py
```

### Option 2: Docker (Local or Cloud)

**Build and run with Docker Compose:**

```bash
docker-compose up --build
```

This runs the bot in a container with `ENABLE_HEALTH_CHECK=false` (suitable for local development or background services).

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

### Option 3: Render.com 

The bot includes a health check server to work with Render's requirements.

**Automatic Deployment (Recommended):**

1. Fork this repository to your GitHub account
2. Go to [Render Dashboard](https://dashboard.render.com/)
3. Click "New" → "Blueprint"
4. Connect your GitHub repository
5. Render will detect `render.yaml` and configure everything automatically
6. Set your secret environment variables in Render dashboard:
   - `TELEGRAM_BOT_TOKEN`
   - `INSTAGRAM120_API_KEY`
   - `TIKTOK_API1_API_KEY`
   - (and other API keys)
7. Click "Apply" to deploy

**Manual Deployment:**

1. Go to [Render Dashboard](https://dashboard.render.com/)
2. Click "New" → "Web Service"
3. Connect your repository
4. Configure:
   - **Name:** whitecat-bot
   - **Environment:** Python 3
   - **Region:** Choose closest to you
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `python bot.py`
   - **Plan:** Free
5. Add environment variables (same as `.env` file)
6. Ensure `ENABLE_HEALTH_CHECK=true` is set
7. Click "Create Web Service"

The bot will automatically use the `PORT` environment variable provided by Render for health checks.

## Adding New Services and Providers

The plugin system makes it easy to add new platforms without modifying core code.

### Adding a New Service (e.g., Facebook)

1. **Create service directory and base files:**

```
video_services/facebook/
├── __init__.py
└── providers/
    └── facebook_api1.py
```

2. **Define the service in `video_services/facebook/__init__.py`:**

```python
from video_services import BaseService, BaseProvider

class FacebookProvider(BaseProvider):
    """Base class for Facebook providers."""
    pass

class FacebookService(BaseService):
    SERVICE_NAME = "FACEBOOK"
    URL_PATTERN = r'https?://(?:www\.)?facebook\.com/watch/\?v=\d+'
    DEFAULT_PRIORITY = 70
    PROVIDER_BASE_CLASS = FacebookProvider
```

3. **Create a provider in `video_services/facebook/providers/facebook_api1.py`:**

```python
from video_services.facebook import FacebookProvider
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

1. **Create `video_services/instagram/providers/instagram_api_new.py`:**

```python
from video_services.instagram import InstagramProvider
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
3. Send a video URL (Instagram, TikTok, or YouTube Shorts)
4. Verify the bot replies with the downloaded video and caption showing which service/provider was used

Example URLs to test:
- Instagram: `https://www.instagram.com/reel/...`
- TikTok: `https://www.tiktok.com/@user/video/...`
- YouTube Shorts: `https://youtube.com/shorts/...`

## Health Check Endpoints

When `ENABLE_HEALTH_CHECK=true`, the bot exposes HTTP endpoints on the configured `PORT`:

- `GET /` - Simple status check (returns "OK")
- `GET /health` - Detailed health info (service count, loaded services)

This allows deployment on platforms that require HTTP endpoints (like Render.com free tier).

## Troubleshooting

**Bot doesn't respond to URLs:**
- Check `TELEGRAM_BOT_TOKEN` is correct
- Verify the URL pattern matches (check logs for `[ROUTER]` messages)
- Ensure at least one provider has a valid API key

**Provider failures:**
- Check API key is valid and has remaining quota
- Try lowering the priority of failing providers
- Add more providers as fallbacks

**Deployment issues on Render:**
- Ensure `ENABLE_HEALTH_CHECK=true` is set
- Verify the service is set as "Web Service" (not Background Worker)
- Check logs for health check endpoint activity

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
