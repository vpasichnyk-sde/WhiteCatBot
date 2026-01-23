# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**whiteCat** is a Telegram bot that downloads videos from multiple platforms (Instagram, TikTok, YouTube, etc.) using a plugin-based multi-service architecture. The bot monitors group messages, detects video URLs, and automatically downloads and replies with the video.

## Commands

### Running the Bot

```bash
# Local development (bot only, no health check server)
ENABLE_HEALTH_CHECK=false python bot.py

# Local development (with health check server on port 8080)
python bot.py

# Docker
docker-compose up --build

# Render.com deployment
# Option 1: Connect repository and use render.yaml (auto-deploy, FREE tier)
# Option 2: Manual setup as Web Service (FREE tier)
# Option 3: Manual setup as Background Worker (requires paid plan)
```

### Dependencies

```bash
pip install -r requirements.txt
```

### Testing

No automated tests currently exist. Manual testing:
1. Start the bot
2. Send a video URL (Instagram/TikTok) to the bot in a Telegram chat
3. Verify the bot replies with the downloaded video

### Debugging

The bot uses verbose logging with prefixes for easy filtering:

```bash
# Filter logs by component
python bot.py 2>&1 | grep "\[HANDLER\]"   # Message handling flow
python bot.py 2>&1 | grep "\[ROUTER\]"    # Service routing decisions
python bot.py 2>&1 | grep "\[DOWNLOAD\]"  # Video download progress
python bot.py 2>&1 | grep "\[SERVICE:"    # Provider fallback chain
python bot.py 2>&1 | grep "\[HEALTH\]"    # Health check server
```

To enable debug logging for specific components, modify logging levels in [bot.py](bot.py) at lines 26-36.

## Architecture

### Core Components

```
bot.py               # Main Telegram bot (message handler)
service_router.py       # Routes URLs to services by priority
video_services/         # Plugin-based service system
  ├── __init__.py       # BaseService, BaseProvider, auto-discovery
  ├── instagram/
  │   ├── __init__.py           # InstagramService, InstagramProvider
  │   └── providers/            # Provider implementations
  │       ├── instagram120.py
  │       ├── instagram_downloader.py
  │       └── instagram_looter2.py
  └── tiktok/
      ├── __init__.py           # TikTokService, TikTokProvider
      └── providers/
          ├── tiktok_api1.py
          └── tiktok_nowatermark2.py
```

### Plugin System Flow

1. **Auto-Discovery** (`load_services_from_env()` in [video_services/__init__.py](video_services/__init__.py)):
   - Scans `video_services/*/` for service classes inheriting from `BaseService`
   - For each service, discovers providers in `providers/` folder
   - Loads API keys and priorities from environment variables
   - Returns sorted list of services by priority

2. **ServiceRouter** ([service_router.py](service_router.py)):
   - Maintains list of services sorted by priority
   - Tries each service's URL pattern against incoming text
   - When matched, calls service's `get_video_url()` which tries providers by priority
   - Returns `(video_url, service_name, provider_num, provider_name)` on success

3. **Message Handler** ([bot.py:156](bot.py#L156)):
   - Receives Telegram message → extracts text
   - Calls `service_router.get_video_url(text)`
   - Downloads video to memory via `download_video()`
   - Replies with video and caption showing service/provider info

### Adding a New Service

1. Create `video_services/{service_name}/__init__.py`:
```python
from video_services import BaseService, BaseProvider

class MyServiceProvider(BaseProvider):
    """Base class for MyService providers."""
    pass

class MyService(BaseService):
    SERVICE_NAME = "MYSERVICE"
    URL_PATTERN = r'https?://(?:www\.)?myservice\.com/watch/[A-Za-z0-9_-]+'
    DEFAULT_PRIORITY = 70
    PROVIDER_BASE_CLASS = MyServiceProvider
```

2. Create providers in `video_services/{service_name}/providers/*.py`:
```python
from video_services.myservice import MyServiceProvider

class MyProvider(MyServiceProvider):
    PROVIDER_NAME = "MYPROVIDER"  # Used for env vars: MYPROVIDER_API_KEY, MYPROVIDER_PRIORITY
    DEFAULT_PRIORITY = 80

    def __init__(self, api_key: str):
        super().__init__("MyProvider")
        self.api_key = api_key

    def get_video_url(self, url: str) -> str | None:
        # Implementation: call API, return direct video URL or None
        pass
```

3. Add to `.env`:
```bash
MYSERVICE_PRIORITY=70                # Service priority (optional)
MYPROVIDER_API_KEY=your_key         # Provider API key
MYPROVIDER_PRIORITY=80              # Provider priority (optional)
```

Auto-discovery handles the rest - no code changes needed in bot.py or service_router.py.

**Important Notes:**
- Providers are scoped to their service (discovered from their service's `providers/` folder only)
- `PROVIDER_NAME` must be unique within a service and should be uppercase
- The bot must be restarted for new services/providers to be discovered
- Files starting with underscore (e.g., `_helpers.py`) are ignored during discovery

### Environment Variables

**Required:**
- `TELEGRAM_BOT_TOKEN` - Telegram bot API token

**Optional:**
- `BOT_USERNAME` - Bot username for captions (default: @white_cat_downloader_bot)
- `ENABLE_HEALTH_CHECK` - Enable HTTP health check server (default: true)
- `PORT` - HTTP server port for health checks (default: 8080, auto-set by Render)
- `{SERVICE}_PRIORITY` - Service priority 0-100 (higher = tried first)
- `{PROVIDER}_API_KEY` - RapidAPI key for provider
- `{PROVIDER}_PRIORITY` - Provider priority 0-100 (higher = tried first)

See [.env.example](.env.example) for complete example.

## Deployment

### Render.com Free Tier Support

The bot includes an HTTP health check server ([bot.py:260](bot.py#L260)) that allows deployment on Render's **free Web Service tier**. The health check server runs concurrently with the Telegram bot using asyncio.

**Health Check Endpoints:**
- `GET /` - Simple status check
- `GET /health` - Detailed health info (service count, loaded services)

**How it works:**
1. Bot uses `run_polling()` to connect to Telegram (outbound only)
2. Health check server binds to `PORT` (provided by Render) on `0.0.0.0`
3. Both run concurrently via `asyncio.gather()`
4. Render pings the health endpoint to verify the service is alive

**Configuration:**
- Set `ENABLE_HEALTH_CHECK=true` to enable (default)
- Set `ENABLE_HEALTH_CHECK=false` for local dev or background workers
- Render automatically sets `PORT` environment variable

This pattern allows free hosting on platforms that require HTTP endpoints while maintaining the simplicity of Telegram's long-polling architecture.

## Key Design Patterns

### Priority-Based Fallback

Both services and providers use priority-based ordering (0-100, higher first). The router tries services by priority until one matches the URL pattern, then that service tries its providers by priority until one succeeds. This enables graceful degradation when APIs fail.

### In-Memory Video Processing

Videos are downloaded to `BytesIO` buffers (not disk) with a 100MB size limit. The buffer is passed directly to Telegram's `reply_video()`. This avoids filesystem I/O but limits video size.

### Auto-Discovery Pattern

Services and providers are auto-discovered via filesystem scanning + reflection:
- `discover_services()` finds all `BaseService` subclasses
- `discover_providers()` finds all service-specific provider classes
- Environment variables configure which providers are enabled and their priorities
- Add new services/providers by creating files - no registration code needed

## File Structure Notes

- `bot.py` contains:
  - Single message handler (`handle_message()`) that processes ALL messages
  - Health check server (`health_check_server()`) for deployment platforms
  - Async bot runner (`run_bot()`) and main orchestrator (`main()`)
- Logging is verbose with `[HANDLER]`, `[ROUTER]`, `[DOWNLOAD]`, `[HEALTH]` prefixes for easy filtering
- Error messages use cat emojis from `CAT_EMOJIS` list

## Important Constants

### Video Size Limit
- `MAX_FILE_SIZE` in [bot.py](bot.py) is set to 100MB by default
- Telegram's actual limit is 2GB, but 100MB provides memory safety
- To change: modify `MAX_FILE_SIZE = 100 * 1024 * 1024` (value in bytes)
- The bot checks size both via Content-Length header and during streaming download

### Error Handling
- Provider failures are logged but don't crash the bot (graceful fallback)
- HTTP 404 errors get specific user-facing message ("video not found")
- Size limit errors get specific user-facing message with current limit
- All errors use random cat emoji from `CAT_EMOJIS` list for consistency
