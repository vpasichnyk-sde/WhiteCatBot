# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

WhiteCat Bot is a Telegram bot with three main features:
1. **Video downloads** from Instagram, TikTok, and other platforms
2. **AI chat** powered by Google Gemini with conversation context memory
3. **Chat summarization** - AI-powered summaries of conversation history

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

Copy `.env.example` to `.env`.

**Required:**
- `TELEGRAM_BOT_TOKEN` - Telegram bot token from BotFather
- `GEMINI_API_KEY` - Google Gemini API key (for AI chat feature)

**Video providers:** Each provider needs `{PROVIDER_NAME}_API_KEY` from RapidAPI.

Set `LOG_LEVEL=DEBUG` for verbose logging during development.

**Handler Configuration** (optional):
- `{HANDLER_NAME}_ENABLED=false` - Disable specific handlers (e.g., `VIDEO_DOWNLOAD_ENABLED=false`, `AI_HANDLER_ENABLED=false`, `SUMMARY_HANDLER_ENABLED=false`)
- `{HANDLER_NAME}_PRIORITY=<num>` - Override handler priority (e.g., `VIDEO_DOWNLOAD_PRIORITY=100`, `SUMMARY_HANDLER_PRIORITY=90`)

**Important Priority Notes:**
- **Priorities are capped at 0-100** (enforced by `pipeline/__init__.py:326`)
- `SUMMARY_HANDLER_PRIORITY` **must** be higher than `AI_HANDLER_PRIORITY` to ensure `/summary` commands in replies to bot messages are processed correctly
- Recommended: `AI_HANDLER_PRIORITY=80`, `SUMMARY_HANDLER_PRIORITY=90`

**AI Trigger Configuration** (optional):
- `{TRIGGER_NAME}_ENABLED=false` - Disable specific AI triggers (e.g., `AI_COMMAND_ENABLED=false`)
- `{TRIGGER_NAME}_PRIORITY=<num>` - Override trigger priority

## Architecture

### Two-Level Handler Architecture

The bot uses a two-level architecture:

1. **Top-level handlers** ([handlers/](handlers/) directory): Auto-discovered wrappers that integrate features into the pipeline
2. **Feature modules** (like [video_pipeline/](video_pipeline/)): Self-contained features with their own logic

Example: [handlers/video_download_handler.py](handlers/video_download_handler.py) wraps [video_pipeline/handler.py](video_pipeline/handler.py), allowing the video feature to be enabled/disabled via `VIDEO_DOWNLOAD_ENABLED=false`.

### Handler Auto-Discovery

Handlers are automatically discovered from the `handlers/` directory at startup. Each handler file:
- Must inherit from `PipelineHandler`
- Can define `HANDLER_NAME` (for env var configuration)
- Can define `DEFAULT_PRIORITY` (0-100, higher runs first)
- Is automatically loaded by `load_handlers_from_env("handlers")`

Configure handlers via environment variables:
- `{HANDLER_NAME}_ENABLED=false` - Disable a specific handler
- `{HANDLER_NAME}_PRIORITY=<num>` - Override default priority

To add a new top-level handler, create a Python file in `handlers/` that inherits from `PipelineHandler`.

### Video Feature Module

All video-related code lives in `video_pipeline/`. Services and providers are auto-discovered at startup.

**Flow**: Message -> `ServiceRouter` -> Service (matches URL) -> Providers (try by priority) -> Download -> Reply

```
video_pipeline/
├── __init__.py          # Exports VideoDownloadHandler, BaseService, BaseProvider
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
   - Accept constructor parameters as needed (commonly `api_key: str`)
   - Implement `get_video_url(self, url: str) -> str | None`
   - Return direct video URL on success, None on failure
4. Add API keys to `.env`: `{PROVIDER_NAME}_API_KEY=...` and optionally `{PROVIDER_NAME}_PRIORITY=...`

### AI Handler Feature Module

All AI-related code lives in `ai_handler_pipeline/`. The AI handler uses Google Gemini API with conversation context memory (last 50 messages per chat).

**Flow**: Message -> Trigger Check -> Extract Message -> Gemini API (with history) -> Store in Context -> Reply

```
ai_handler_pipeline/
├── __init__.py              # Exports AIProcessingHandler
├── handler.py               # Pipeline handler for AI chat
├── processor.py             # Gemini API integration
├── conversation_manager.py  # In-memory conversation context (50 msgs/chat)
├── trigger_registry.py      # Manages trigger priority and checking
├── system_instruction.txt   # WhiteCat personality definition
└── triggers/
    ├── __init__.py          # BaseTrigger, auto-discovery logic
    ├── command_trigger.py   # Triggers on `/cat` or `/кіт` commands
    ├── mention_trigger.py   # Triggers when bot is @mentioned
    └── reply_trigger.py     # Triggers when replying to bot messages
```

**Conversation Context:**
- Stores last 50 messages per chat in RAM (separate for each chat_id)
- Uses `collections.deque` with automatic rolling window
- Thread-safe for concurrent access
- Lost on bot restart (by design)
- Messages stored in Gemini format: `{"role": "user"/"model", "parts": [text]}`

**Trigger System:**
Triggers are checked in priority order (highest first) until one matches:
1. **CommandTrigger** (priority 80) - `/cat <message>` or `/кіт <message>`
2. **MentionTrigger** (priority 70) - `@botusername <message>`
3. **ReplyTrigger** (priority 60) - Reply to any bot message

All triggers auto-discovered from `triggers/` directory at startup.

### Adding a New AI Trigger

1. Create file in `ai_handler_pipeline/triggers/{trigger_name}.py`
2. Define trigger class:
```python
from . import BaseTrigger

class MyTrigger(BaseTrigger):
    TRIGGER_NAME = "AI_MY_TRIGGER"
    DEFAULT_PRIORITY = 50
    DEFAULT_ENABLED = True

    async def should_trigger(self, message) -> bool:
        # Return True if this trigger matches
        pass

    async def extract_user_message(self, message) -> str:
        # Extract and return the user's message text
        pass
```
3. Configure via env vars: `AI_MY_TRIGGER_ENABLED=false` or `AI_MY_TRIGGER_PRIORITY=<num>`

### AI Summary Pipeline Feature Module

All chat summarization code lives in `ai_summary_pipeline/`. This feature stores ALL text messages from chat and generates summaries on-demand.

**Flow**: Message -> Store in History -> Check Trigger -> Gemini API (format transcript) -> Reply with Summary

```
ai_summary_pipeline/
├── __init__.py              # Exports SummaryProcessingHandler
├── handler.py               # Pipeline handler for summarization
├── history_manager.py       # In-memory message storage (200 msgs/chat)
├── summary_processor.py     # Gemini API integration for summaries
└── system_instruction.txt   # Summarization prompt (language-aware)
```

**Message Storage:**
- Stores last 200 messages per chat in RAM (separate for each chat_id)
- Stores ALL text messages EXCEPT trigger commands (not just bot interactions)
- Uses `collections.deque` with automatic rolling window
- Thread-safe for concurrent access
- Lost on bot restart (by design)
- Message format: `{"user_id", "username", "text", "timestamp", "is_forwarded"}`
- Includes text from: `message.text`, `message.caption`, forwarded messages
- Skips: stickers, voice messages, media without captions, trigger commands (`/summary` etc.)

**Trigger System:**
Triggers when message CONTAINS (not just starts with) keywords:
- `/summarize` or `/summary` (case-insensitive)
- Configurable list in `handler.py`: `DEFAULT_TRIGGER_KEYWORDS`
- Works in replies to bot messages (priority 90 > AI_HANDLER priority 80)
- Trigger messages are NOT stored in history (prevents "/summary" from appearing in summaries)

**Output Format:**
- Plain text without Markdown formatting (no asterisks, underscores for styling)
- Simple hyphens (-) for bullet points instead of Markdown lists
- Preserves @usernames exactly as they appear (e.g., @itis_v without escaping)
- Optimized for Telegram's default text rendering

**Key Differences from AI Handler:**
- **Storage**: Raw message metadata vs. AI conversation pairs
- **Trigger**: Simple keyword matching vs. trigger registry system
- **Processing**: On-demand only vs. every matched message
- **Context**: All users' messages vs. user-bot dialogue
- **Purpose**: Analytical summaries vs. conversational responses
- **Gemini Config**: Lower temperature (0.3 vs 0.85), no Google Search tool

**Privacy Requirement:**
Bot must have Privacy Mode OFF in group chats (configured via BotFather) to receive and store all messages.

### Pipeline System

The pipeline system ([pipeline/__init__.py](pipeline/__init__.py)) provides a framework for processing Telegram messages through a chain of handlers. Each handler extends `PipelineHandler` and implements `process(ctx)`. Handlers can call `ctx.stop()` to halt the pipeline.

The bot ([bot.py](bot.py)) automatically discovers and registers handlers from the `handlers/` directory at startup.

To add a new handler:
1. Create a class extending `PipelineHandler` in a new file under `handlers/`
2. Implement `process(ctx)` method
3. Optionally define `HANDLER_NAME` and `DEFAULT_PRIORITY`
4. The handler is automatically discovered and loaded on next bot startup

### Key Files

**Core:**
- [bot.py](bot.py) - Entry point, initializes Telegram bot and pipeline
- [pipeline/__init__.py](pipeline/__init__.py) - `MessagePipeline`, `PipelineHandler`, `PipelineContext`, auto-discovery
- [handlers/](handlers/) - Top-level handlers directory (auto-discovered)

**Video Pipeline:**
- [video_pipeline/__init__.py](video_pipeline/__init__.py) - Video feature module exports
- [video_pipeline/handler.py](video_pipeline/handler.py) - Pipeline handler for video downloads
- [video_pipeline/router.py](video_pipeline/router.py) - Routes URLs to services by priority
- [video_pipeline/downloader.py](video_pipeline/downloader.py) - Downloads videos to memory (100MB limit)
- [video_pipeline/services/__init__.py](video_pipeline/services/__init__.py) - Base classes and auto-discovery

**AI Chat Pipeline:**
- [ai_handler_pipeline/__init__.py](ai_handler_pipeline/__init__.py) - AI feature module exports
- [ai_handler_pipeline/handler.py](ai_handler_pipeline/handler.py) - Pipeline handler for AI chat
- [ai_handler_pipeline/processor.py](ai_handler_pipeline/processor.py) - Gemini API integration
- [ai_handler_pipeline/conversation_manager.py](ai_handler_pipeline/conversation_manager.py) - Conversation context storage
- [ai_handler_pipeline/trigger_registry.py](ai_handler_pipeline/trigger_registry.py) - Trigger management
- [ai_handler_pipeline/triggers/__init__.py](ai_handler_pipeline/triggers/__init__.py) - Trigger base class and auto-discovery

**AI Summary Pipeline:**
- [ai_summary_pipeline/__init__.py](ai_summary_pipeline/__init__.py) - Summary feature module exports
- [ai_summary_pipeline/handler.py](ai_summary_pipeline/handler.py) - Pipeline handler for chat summarization
- [ai_summary_pipeline/history_manager.py](ai_summary_pipeline/history_manager.py) - Message history storage (200 msgs)
- [ai_summary_pipeline/summary_processor.py](ai_summary_pipeline/summary_processor.py) - Gemini API for summaries
- [ai_summary_pipeline/system_instruction.txt](ai_summary_pipeline/system_instruction.txt) - Language-aware summarization prompt

## Priority System

Handlers, services, providers, and triggers use priority (0-100, higher runs/tried first). Configure via env vars:
- `{HANDLER_NAME}_PRIORITY` for handlers (e.g., `AI_HANDLER_PRIORITY=50`)
- `{SERVICE_NAME}_PRIORITY` for services (e.g., `INSTAGRAM_PRIORITY=80`)
- `{PROVIDER_NAME}_PRIORITY` for providers (e.g., `INSTAGRAM120_PRIORITY=80`)
- `{TRIGGER_NAME}_PRIORITY` for AI triggers (e.g., `AI_COMMAND_PRIORITY=80`)

If a provider fails, the next one is tried automatically. For triggers, checking stops at first match.
