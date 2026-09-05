# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

WhiteCat Bot is a Telegram bot with three features:
1. **Video downloads** from Instagram, TikTok, etc. (RapidAPI providers, in-memory, 100MB limit)
2. **AI chat** powered by Google Gemini with passive-listening conversation context
3. **Chat summarization** — AI-powered summaries of recent chat history

## Commands

```bash
pip install -r requirements.txt   # Install dependencies
python bot.py                     # Run locally
docker-compose up --build         # Run with Docker

# Docker management scripts (Ubuntu/Linux)
./start-bot.sh      # Start bot and show logs
./stop-bot.sh       # Stop bot
./update-bot.sh     # Git pull and restart (rebuilds when there are changes)
docker compose logs -f
```

There is no automated test suite or linter; testing is manual through Telegram (send a video URL, `/cat <msg>`, or `/summary` and check the reply). Set `LOG_LEVEL=DEBUG` in `.env` for verbose logs (default is WARNING).

## Environment Variables

Copy `.env.example` to `.env`.

**Required:** `TELEGRAM_BOT_TOKEN`. `GEMINI_API_KEY` is required for both AI features. Video providers each need `{PROVIDER_NAME}_API_KEY` from RapidAPI.

Env-var configurability differs by component type (names derive from each component's declared `HANDLER_NAME`/`TRIGGER_NAME`/`SERVICE_NAME`/`PROVIDER_NAME`):
- **Handlers**: `{NAME}_ENABLED=false` and `{NAME}_PRIORITY=<0-100>` (clamped in `pipeline/__init__.py`)
- **AI triggers**: `{NAME}_ENABLED=false` only — there is NO `_PRIORITY` env var for triggers; their priority is fixed by `DEFAULT_PRIORITY` in code
- **Services/providers**: `{NAME}_PRIORITY` only (clamped in `video_pipeline/services/__init__.py`) — there is NO `_ENABLED` switch; a provider is enabled by the presence of its `{PROVIDER_NAME}_API_KEY`, so remove/unset the key to disable it

Priority is 0–100, higher runs/tried first.

**Priority constraint:** `SUMMARY_HANDLER_PRIORITY` (default 90) must stay higher than `AI_HANDLER_PRIORITY` (default 80). Otherwise a `/summary` sent as a reply to a bot message is swallowed by the AI handler's ReplyTrigger. `VIDEO_DOWNLOAD` defaults to 100.

**Missing keys degrade gracefully** (useful for local dev): with no provider API keys, `load_services_from_env` raises, the video wrapper fails to init, and `load_handlers_from_env` logs it and skips that handler; with no `GEMINI_API_KEY`, the AI/summary handlers still load but their processor is None so `should_process` always returns False. The rest of the bot keeps working either way.

## Architecture

### Pipeline System

[bot.py](bot.py) registers a single `MessageHandler(filters.ALL)` that runs every message through a `MessagePipeline` ([pipeline/__init__.py](pipeline/__init__.py)). Handlers are auto-discovered from [handlers/](handlers/) at startup (`load_handlers_from_env`), instantiated, filtered/re-prioritized via env vars, and sorted by priority.

For each message, the pipeline calls each handler's `should_process(ctx)` then `process(ctx)` in priority order. `ctx.stop()` halts the pipeline; `ctx.data` is a shared dict for passing data between the two phases (e.g. the AI handler stashes its matched trigger there). The pipeline is created with `stop_on_error=True`, so an unhandled exception in one handler ends processing for that message.

### Two-Level Handler Pattern

Files in [handlers/](handlers/) are thin auto-discovered wrappers declaring `HANDLER_NAME` and `DEFAULT_PRIORITY`; the real logic lives in self-contained feature modules (`video_pipeline/`, `ai_handler_pipeline/`, `ai_summary_pipeline/`). To add a feature: build the module, then add a wrapper in `handlers/` that inherits `PipelineHandler` and delegates. Any new top-level module also needs its own `COPY` line in the [Dockerfile](Dockerfile) — it copies directories explicitly, so a missing line means the module silently doesn't exist in the Docker image (this already happened once with `ai_summary_pipeline/`).

### Passive Listening (important side effect of `should_process`)

Both AI and summary handlers **store messages inside `should_process()`**, not `process()` — they listen to every text message and only return True when triggered. Consequences:

- Handler ordering affects storage: if a higher-priority handler stops the pipeline, lower handlers never see the message and don't store it. The video handler (priority 100) stops only when the message matched a service URL (success or failure), so video-URL messages never enter conversation history; ordinary text falls through to the AI/summary handlers.
- The bot needs Privacy Mode OFF (via BotFather) in groups to receive all messages.
- All storage is in-RAM (`collections.deque` rolling windows, thread-safe via `Lock`), separate per chat_id, and intentionally lost on restart.

### Shared Message Storage

[message_storage/](message_storage/) is a shared module (moved out of `ai_handler_pipeline/`). Both AI and summary handlers use ONE process-wide `ConversationManager` instance obtained via `get_conversation_manager()` — each message is stored once, deduplicated across handlers via the `ctx.data['message_stored']` flag. It keeps the last **250 messages per chat** with metadata (`user_id`, `username`, `timestamp`, `role`, `is_bot`, `is_trigger`, `is_forwarded`); forwarded messages are attributed to the original sender via `extract_sender_info()`. Two read paths: `get_history()` converts to Gemini `types.Content` (prefixing user messages with `@username: ` for attribution) for AI chat; `get_raw_history(limit, include_bot=False)` returns raw dicts for summarization (bot messages excluded by default). Summary trigger messages (`/summary` etc.) are never stored: the summary handler skips storing them and stops the pipeline before the AI handler could store them.

### AI Chat (`ai_handler_pipeline/`)

**Flow**: Message → store in ConversationManager → trigger check → Gemini (history excludes the just-stored trigger message, which is sent instead as the live prompt with `@username: ` attribution) → reply → store bot response.

Triggers are auto-discovered from `ai_handler_pipeline/triggers/` and checked highest-priority first, stopping at first match:
1. **CommandTrigger** (`AI_COMMAND`, 80) — `/cat <msg>` or `/кіт <msg>`
2. **MentionTrigger** (`AI_MENTION`, 70) — `@botusername <msg>`
3. **ReplyTrigger** (`AI_REPLY`, 60) — reply to any bot message, except the bot's video/animation messages (replies to downloaded videos are treated as plain conversation and only stored)

New trigger: create a file in `triggers/` with a class extending `BaseTrigger`, declaring `TRIGGER_NAME`/`DEFAULT_PRIORITY` and implementing `async should_trigger(self, message: Message) -> bool` and the **synchronous** `extract_user_message(self, message_text: str) -> Optional[str]` — it receives the raw message text (not the Message object) and is called without `await` (`trigger_registry.py` line 81), so making it async silently passes a coroutine object downstream as the prompt.

Gemini config ([processor.py](ai_handler_pipeline/processor.py)): model `gemini-3.1-flash-lite`, temperature 0.85, minimal thinking level, Google Search tool enabled, personality from [system_instruction.txt](ai_handler_pipeline/system_instruction.txt).

### Chat Summarization (`ai_summary_pipeline/`)

Triggered when a message **contains** (not just starts with) `/summarize`, `/summary`, or `/самарі` (case-insensitive; list in `DEFAULT_TRIGGER_KEYWORDS` in [handler.py](ai_summary_pipeline/handler.py)). Trigger messages are deliberately NOT stored in history so they don't appear in summaries. Handles forwarded messages by attributing to the original sender when available.

Gemini config differs from chat: temperature 0.3, no Google Search tool, output is plain text (no Markdown) with language-aware prompting from its own `system_instruction.txt`.

### Video Pipeline (`video_pipeline/`)

**Flow**: Message → `ServiceRouter` matches URL to a service → service tries providers by priority until one returns a direct video URL → `downloader.py` fetches to memory (100MB cap) → reply with video.

Services and providers are auto-discovered from `video_pipeline/services/`. To add a service, create `video_pipeline/services/{name}/__init__.py` defining a `BaseService` subclass with `SERVICE_NAME`, `URL_PATTERN`, `DEFAULT_PRIORITY`, and a `PROVIDER_BASE_CLASS`; put providers in a `providers/` subfolder. Each provider declares `PROVIDER_NAME` (uppercase, drives env vars) and `DEFAULT_PRIORITY`, takes `api_key: str` in its constructor, and implements `get_video_url(url) -> str | None` (None = failure, next provider is tried).
