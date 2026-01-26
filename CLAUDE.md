# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

WhiteCat Bot is a Telegram bot that downloads videos from Instagram, TikTok, and other platforms. Users send video URLs in Telegram chats, and the bot replies with the downloaded video.

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run locally
python bot.py

# Run with Docker
docker-compose up --build

# Docker management (Ubuntu scripts available)
./start-bot.sh      # Start bot and show logs
./stop-bot.sh       # Stop bot
./update-bot.sh     # Git pull and restart (rebuilds if needed)
docker compose logs -f  # View live logs
```

## Environment Variables

Copy `.env.example` to `.env`. Required: `TELEGRAM_BOT_TOKEN`. Each provider needs its own `{PROVIDER_NAME}_API_KEY` from RapidAPI.

Set `LOG_LEVEL=DEBUG` for verbose logging during development.

## Architecture

### Video Feature Module

All video-related code lives in `video_pipeline/`. Services and providers are auto-discovered at startup.

**Flow**: Message -> `ServiceRouter` -> Service (matches URL) -> Providers (try by priority) -> Download -> Reply

```
video_pipeline/
├── __init__.py          # Exports VideoDownloadHandler, ServiceRouter, etc.
├── handler.py           # Pipeline handler for Telegram integration
├── router.py            # Routes URLs to services by priority
├── downloader.py        # Downloads videos to memory (100MB limit)
└── services/
    ├── __init__.py      # BaseService, BaseProvider, auto-discovery logic
    ├── instagram/
    │   ├── __init__.py  # InstagramService (URL_PATTERN, PROVIDER_BASE_CLASS)
    │   └── providers/   # Provider implementations
    └── tiktok/
        ├── __init__.py  # TikTokService
        └── providers/
```

### Adding a New Service

1. Create folder: `video_pipeline/services/{service_name}/`
2. Define service in `__init__.py`:
```python
from video_pipeline.services import BaseService, BaseProvider

class MyProvider(BaseProvider):
    pass

class MyService(BaseService):
    SERVICE_NAME = "MYSERVICE"
    URL_PATTERN = r'https?://...'
    DEFAULT_PRIORITY = 70
    PROVIDER_BASE_CLASS = MyProvider
```
3. Create providers in `providers/` subfolder. Each provider must:
   - Inherit from the service's `PROVIDER_BASE_CLASS`
   - Define `PROVIDER_NAME` (uppercase, used for env vars)
   - Define `DEFAULT_PRIORITY` (0-100)
   - Accept `api_key: str` in `__init__(self, api_key: str)`
   - Implement `get_video_url(self, url: str) -> str | None` (returns direct video URL or None)
4. Add API keys to `.env`: `{PROVIDER_NAME}_API_KEY=...` and optionally `{PROVIDER_NAME}_PRIORITY=...`

### Pipeline System

The pipeline system ([pipeline/__init__.py](pipeline/__init__.py)) provides a framework for processing Telegram messages through a chain of handlers. Each handler extends `PipelineHandler` and implements `process(ctx)`. Handlers can call `ctx.stop()` to halt the pipeline.

Handlers are feature-specific and live in their respective feature modules (e.g., `VideoDownloadHandler` in [video_pipeline/handler.py](video_pipeline/handler.py)). The bot ([bot.py](bot.py)) registers handlers with the pipeline at startup.

To add a new handler, create a class extending `PipelineHandler`, implement `process(ctx)`, and register it in `bot.py` with `pipeline.add_handler()`.

### Key Files

- [bot.py](bot.py) - Entry point, initializes Telegram bot and pipeline
- [pipeline/__init__.py](pipeline/__init__.py) - `MessagePipeline`, `PipelineHandler`, `PipelineContext`
- [video_pipeline/__init__.py](video_pipeline/__init__.py) - Video feature module exports
- [video_pipeline/handler.py](video_pipeline/handler.py) - Pipeline handler for video downloads
- [video_pipeline/router.py](video_pipeline/router.py) - Routes URLs to services by priority
- [video_pipeline/downloader.py](video_pipeline/downloader.py) - Downloads videos to memory (100MB limit)
- [video_pipeline/services/__init__.py](video_pipeline/services/__init__.py) - Base classes and auto-discovery

## Priority System

Services and providers use priority (0-100, higher tried first). Configure via env vars:
- `{SERVICE_NAME}_PRIORITY` for services
- `{PROVIDER_NAME}_PRIORITY` for providers

If a provider fails, the next one is tried automatically.
