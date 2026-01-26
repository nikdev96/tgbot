# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Telegram translation bot supporting 6 languages (Russian, English, Thai, Arabic, Chinese, Vietnamese) with text and voice message translation. Built with aiogram 3.x and OpenAI APIs (GPT-4o for translation, Whisper for speech-to-text, TTS for voice responses).

## Common Commands

```bash
# Run the bot
python -m src.main

# Run tests
python -m pytest tests/
python -m pytest tests/test_database.py -v  # single test file

# Linting
ruff check src/
ruff format src/
black src/
isort src/
```

## Environment Setup

Copy `.env.example` to `.env` and set:
- `TELEGRAM_BOT_TOKEN` - Bot token from @BotFather
- `OPENAI_API_KEY` - OpenAI API key (must start with `sk-`)
- `ADMIN_USER_ID` - Comma-separated Telegram user IDs for admin access
- `ENVIRONMENT` - `development` or `production` (selects config file)

## Architecture

### Core Application Flow
1. `src/main.py` - Entry point, initializes DB, registers middleware and handlers
2. `src/core/app.py` - Creates global Bot, Dispatcher, OpenAI client, DatabaseManager instances
3. `src/core/config.py` - YAML config loading with dataclass models, env var overrides

### Handler Registration Order (in `handlers/__init__.py`)
Handlers are registered in specific order - **text handler must be last** as it catches all text messages:
1. `commands.py` - Bot commands (/start, /menu, /admin, /help)
2. `callbacks.py` - Inline keyboard callbacks
3. `room_commands.py` - Room management (/room)
4. `voice.py` - Voice message processing
5. `text.py` - Text message translation (catch-all)

### Translation Pipeline
`services/translation.py`:
- `translate_text()` - Uses OpenAI JSON response format, validates translations for all target languages
- `generate_tts_audio()` - Creates voice responses with persistent file caching in `data/cache/tts/`
- `generate_parallel_voice_responses()` - Parallel TTS generation for multiple languages

### Database
SQLite with WAL mode (`storage/database.py`). Tables: `users`, `user_language_preferences`, `rooms`, `room_members`, `room_messages`. Async methods wrap synchronous SQLite calls via `run_in_executor`.

### Middleware
- `UserCheckMiddleware` - Ensures user exists in DB before processing
- `RateLimitMiddleware` - Rate limiting (configurable, admin bypass)

### Configuration
YAML files in `config/` (development.yaml, production.yaml). Key sections: audio, tts, translation, rate_limits, database, openai, security.

### Key Constants (`core/constants.py`)
- `SUPPORTED_LANGUAGES` - Language codes with names and flags
- `DEFAULT_LANGUAGES` - Default set for new users: ru, en, th
- `ADMIN_IDS` - Loaded from ADMIN_USER_ID env var

## Room System
Multi-user translation rooms where each participant writes in their language and receives translations. Rooms expire after 24 hours. Creator has special privileges (close room).
