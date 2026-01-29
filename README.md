# WhiteCat Bot 🐱

A powerful Telegram bot with AI-powered chat, conversation summarization, and automatic video downloads from multiple platforms (Instagram, TikTok and more).

## Why whiteCat?

Social media platforms often make it difficult to download videos directly. **whiteCat** solves this by:
- **Automatic detection** - Just send a video URL in any Telegram chat, and the bot replies with the downloaded video
- **Multi-platform support** - Works with Instagram, TikTok and easily extensible to other platforms
- **Reliable fallback** - Uses multiple providers per platform with priority-based failover
- **Zero storage** - Videos are processed in-memory and sent directly to Telegram

## Features

### AI Features
- 🤖 **AI Chat** - Conversational AI powered by Google Gemini
  - Responds to `/cat` or `/кіт` commands
  - Responds to @mentions
  - Continues conversations when you reply to bot messages
  - Maintains last 50 messages of context per chat

- 📊 **Chat Summarization** - AI-powered conversation summaries
  - Trigger with `/summarize` or `/summary` command anywhere in message
  - Summarizes last 200 messages from all participants
  - Language-aware: summary matches the conversation language
  - Attributes topics to specific users with @usernames
  - Plain text format optimized for Telegram (no Markdown formatting)
  - Trigger commands are excluded from summaries automatically

### Video Download Features
- 🎬 Download videos from Instagram, TikTok
- 🔄 Priority-based provider fallback for reliability
- 🔌 Plugin architecture - add new services without touching core code
- 📦 In-memory processing (no disk storage needed)
- 🚀 Deploy anywhere: Docker or local development
- 💾 100MB video size limit per download

## Prerequisites

- Python 3.11+
- Telegram Bot Token (get from [@BotFather](https://t.me/botfather))
- Google Gemini API Key (get from [Google AI Studio](https://aistudio.google.com/apikey)) - for AI chat and summarization
- RapidAPI keys for video download services (optional - only if using video downloads)

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

### AI Features Architecture

whiteCat includes two AI-powered features built on Google Gemini:

**1. AI Chat (`ai_handler_pipeline/`)**
- Conversational AI with context memory (last 50 messages)
- Trigger system: commands (`/cat`, `/кіт`), mentions (`@bot`), replies
- Stores conversation pairs (user/model) in Gemini format
- Temperature: 0.85 (creative responses)
- Includes Google Search tool integration

**2. Chat Summarization (`ai_summary_pipeline/`)**
- Stores ALL text messages from chat (last 200 messages, except trigger commands)
- Triggered by `/summarize` or `/summary` keywords
- Message storage: raw metadata (username, text, timestamp, forwarded status)
- Temperature: 0.3 (factual summaries)
- Language-aware: summary matches conversation language
- Plain text output: no Markdown formatting, preserves @usernames correctly
- Requires Privacy Mode OFF in groups to see all messages

Both features:
- Auto-discovered and loaded at startup
- Can be independently enabled/disabled via env vars
- Share the same `GEMINI_API_KEY`
- Use thread-safe in-memory storage (lost on restart)

## Quick Start

### 1. Configuration

Create a `.env` file in the project root:

```bash
# Required
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here

# AI Features (Google Gemini API)
GEMINI_API_KEY=your_gemini_api_key_here

# Optional
BOT_USERNAME=@your_bot_username
LOG_LEVEL=INFO  # DEBUG, INFO, WARNING, ERROR, CRITICAL

# Handler Configuration (optional, 0-100 = priority, higher runs first)
# VIDEO_DOWNLOAD_ENABLED=false  # Disable video downloads
# VIDEO_DOWNLOAD_PRIORITY=100
# AI_HANDLER_ENABLED=false      # Disable AI chat
# AI_HANDLER_PRIORITY=80
# SUMMARY_HANDLER_ENABLED=false # Disable chat summarization
# SUMMARY_HANDLER_PRIORITY=90   # MUST be higher than AI_HANDLER to catch /summary in replies

# AI Trigger Configuration (optional)
AI_COMMAND_ENABLED=true   # /cat and /кіт commands
AI_REPLY_ENABLED=true     # Replies to bot messages
AI_MENTION_ENABLED=true   # @bot_username mentions

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

*For AI Features (Chat & Summarization):*
1. Go to [Google AI Studio](https://aistudio.google.com/apikey)
2. Sign in with your Google account
3. Click "Create API Key"
4. Copy the key to `GEMINI_API_KEY` in `.env`

*For Video Downloads:*
1. Sign up at [RapidAPI](https://rapidapi.com/)
2. Subscribe to the video download APIs you need (most have free tiers)
3. Copy your API key to the `.env` file

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Using the Bot

**AI Chat:**
- Send `/cat <your message>` or `/кіт <your message>` to start a conversation
- Mention the bot: `@your_bot_username what's the weather?`
- Reply to any bot message to continue the conversation
- The bot remembers the last 50 messages in each chat for context

**Chat Summarization:**
- Send any message containing `/summarize` or `/summary`
- Examples:
  - `Can you /summarize this discussion?`
  - `/summary of the last hour please`
- The bot will analyze the last 200 messages and provide:
  - Brief overview of the conversation
  - Key topics with attribution to participants (@usernames)
  - Any decisions or action items
- Summary format: plain text with simple bullet points (optimized for Telegram)
- Trigger commands are automatically excluded from the summary

**Note:** For group chats, disable Privacy Mode in [@BotFather](https://t.me/botfather) so the bot can see and summarize all messages.

**Video Downloads:**
- Simply send any Instagram or TikTok video URL
- The bot will automatically detect and download the video
- No commands needed!

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
