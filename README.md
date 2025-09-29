# 🌍 Telegram Translation Bot

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![aiogram](https://img.shields.io/badge/aiogram-3.x-green.svg)](https://docs.aiogram.dev/)
[![OpenAI](https://img.shields.io/badge/OpenAI-GPT--4o-orange.svg)](https://openai.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A smart Telegram bot that translates text and voice messages between **6 languages** 🇷🇺🇺🇸🇹🇭🇯🇵🇰🇷🇻🇳 with customizable user preferences, built using OpenAI's latest models and a clean modular architecture.

## 📊 Current Status

**✅ Production Ready** - v2.4.0 with 60%+ performance improvement, modular architecture, and comprehensive offline testing.

**🚀 Performance:** Voice processing ~9s (was 22s), parallel TTS generation, persistent caching
**🏗️ Architecture:** Clean separation with core, handlers, services, and storage packages
**🧪 Testing:** Offline tests with OpenAI mocks, atomic SQL operations for race condition prevention

## ✅ What Works

**Core Translation:**
- 🎯 **Smart Language Detection** - Russian, English, Thai, Japanese, Korean, Vietnamese
- 🔄 **Customizable Preferences** - Choose target languages via `/menu`
- 🎤 **Voice Messages** - Whisper transcription + translation
- 🔊 **Voice Replies** - Optional TTS responses (toggle per user)

**Performance & Reliability:**
- ⚡ **Parallel Processing** - 60%+ faster voice responses (~9s vs 22s)
- 💾 **Smart Caching** - Translation (1h TTL) + TTS (30min TTL) with persistent storage
- 🔄 **Atomic Operations** - Race condition prevention in user analytics
- 🛡️ **Error Handling** - Retry logic with exponential backoff

**Admin Features:**
- 👑 **Admin Dashboard** - User management via `/admin`
- 📊 **Analytics** - Activity tracking, message counts, preferences
- 🔒 **Access Control** - Enable/disable users with audit logging

**Architecture:**
- 🏗️ **Modular Design** - Clean separation: core, handlers, services, storage
- 🧪 **Offline Testing** - OpenAI API mocks for development
- ⚙️ **YAML Configuration** - Environment-specific settings

## 📋 TODO

**Immediate (Sprint 4):**
- 🐳 **Docker Setup** - Production containerization with docker-compose
- 📊 **Health Checks** - Monitoring endpoints and metrics collection
- 🌐 **Language Expansion** - Add Spanish, French, German support

**Planned Features:**
- 🌍 **Web Interface** - Browser-based translation tool
- 📱 **REST API** - Third-party integrations
- 📄 **Document Support** - PDF/DOCX translation
- 🔄 **Context Awareness** - Conversation history for better translations

## 🎬 Demo

**Text Translation:**
```
User: Привет, как дела?
Bot: 🇺🇸 English: Hello, how are you?
Bot: 🇹🇭 Thai: สวัสดี เป็นอย่างไรบ้าง?
```

**Voice Translation:**
```
User: [sends voice message saying "Hello, how are you?"]
Bot: 🎤 🇺🇸 Transcribed (English): Hello, how are you?
Bot: 🇷🇺 Russian: Привет, как дела?
Bot: 🇹🇭 Thai: สวัสดี เป็นอย่างไรบ้าง?
Bot: 🔊 [Voice message with translations]
```

**Voice Replies (when enabled):**
```
User: Hello, how are you?
Bot: 🇷🇺 Russian: Привет, как дела?
Bot: 🇹🇭 Thai: สวัสดี เป็นอย่างไรบ้าง?
Bot: 🔊 Voice translation (RU + TH)
     [Audio clip with female voice saying both translations]
```

## 🚀 Quick Start

**Prerequisites:** Python 3.11+, FFmpeg, Telegram Bot Token, OpenAI API Key

```bash
# Clone and install
git clone https://github.com/nikdev96/tgbot.git
cd tgbot
pip install -r requirements.txt

# Configure (copy .env.example to .env)
TELEGRAM_BOT_TOKEN=your_token_here
OPENAI_API_KEY=your_openai_key
ADMIN_USER_ID=your_telegram_user_id

# Run
python -m src.main
```

**Get API Keys:**
- **Telegram:** [@BotFather](https://t.me/botfather) → `/newbot`
- **OpenAI:** [platform.openai.com/api-keys](https://platform.openai.com/api-keys)
- **Your User ID:** [@userinfobot](https://t.me/userinfobot)

## 📱 Usage

### Regular Users
1. **Start**: Send `/start` for welcome message and instructions
2. **Menu**: Use `/menu` to configure translation preferences
3. **Text**: Send any text in Russian, English, Thai, Japanese, Korean, or Vietnamese
4. **Voice**: Send voice messages or audio files (up to 10 minutes)
5. **Preferences**: Toggle target languages with ✅/❌ buttons (English enabled by default)
6. **Voice Replies**: Toggle 🎤 Voice replies in `/menu` to receive TTS audio responses

### Admin Features
6. **Admin Dashboard**: Use `/admin` to access user management (admin only)
7. **User Management**: View analytics, enable/disable users via dashboard
8. **Analytics**: Monitor user activity, message counts, and preferences

### Voice Message Features
- 🎤 **Supports**: Telegram voice messages and audio files
- ⏱️ **Duration**: Up to 10 minutes per message
- 🔊 **Formats**: OGG/Opus (Telegram voice), MP3, WAV, and other common formats
- 🗣️ **Quality**: Optimized for speech recognition (16kHz mono)
- 🧹 **Cleanup**: Temporary files automatically deleted after processing

### Voice Replies Features
- 🔊 **Text-to-Speech**: Uses OpenAI Audio API with female voice (alloy)
- ⚙️ **Per-User Setting**: Toggle on/off via `/menu` (default: OFF)
- 🎯 **Combined Audio**: Single voice clip with all translations
- 📏 **Smart Limits**: Skips TTS for text longer than 500 characters
- 💰 **Cost Awareness**: Additional OpenAI usage for TTS generation
- 🎚️ **Quality**: 48kHz mono OGG/Opus format for Telegram

### Admin Dashboard Features
- 📊 **User Analytics**: Total users, active/disabled counts, per-user statistics
- 👤 **User Profiles**: Username, language preferences, last activity, message count
- 🔄 **Real-time Management**: Refresh dashboard, enable/disable users instantly
- 🚫 **Access Control**: Disabled users receive polite access denied messages
- 📝 **Audit Logging**: All admin actions and blocked attempts are logged

**Admin Dashboard Commands:**
- 🔄 **Refresh**: Update dashboard with latest analytics
- ✅ **Enable User**: Restore access for disabled users
- ❌ **Disable User**: Block user access (they'll see "Access disabled" message)

## 👑 Admin Features

### Setting Up Admins

1. **Single Admin**: Set your Telegram user ID in `.env`:
   ```env
   ADMIN_USER_ID=292256687
   ```

2. **Multiple Admins**: Use comma-separated IDs:
   ```env
   ADMIN_USER_ID=292256687,123456789,987654321
   ```

3. **Find Your User ID**: Message `@userinfobot` on Telegram

### Admin Dashboard (`/admin`)

**Access Control:**
- Only users listed in `ADMIN_USER_ID` can use `/admin`
- Non-admins receive "Access denied" message
- All access attempts are logged with audit trail

**Dashboard Display:**
```
🔧 Admin Dashboard

Total Users: 15
Active: 12 | Disabled: 3

User Summary:

**Username** (user_id)
Status: 🟢 Active
Languages: ru, en, th
Messages: 45 | Last: 2025-01-15 14:30
```

**Dashboard Actions:**
- 🔄 **Refresh**: Update analytics and user list
- ✅ **Enable User**: Restore access for disabled users
- ❌ **Disable User**: Block user access immediately

### User Analytics (SQLite Database)

**Tracked Data:**
- `is_disabled`: User access status
- `preferred_targets`: Language preferences
- `message_count`: Total messages processed
- `voice_responses_sent`: Voice reply count
- `last_activity`: Last interaction timestamp
- `user_profile`: Username, first/last name

**✅ Note**: Analytics are now stored persistently in SQLite database (`data/translator_bot.db`) with full async support.

### Access Control Enforcement

**Disabled User Experience:**
- All commands respond with: "❌ Access disabled. Contact support if you believe this is an error."
- Blocked attempts are logged for audit purposes
- No translation or voice processing occurs

**Admin Audit Logging:**
```
2025-01-15 14:30:15 - audit - INFO - ADMIN_ACCESS: Admin 292256687 accessed dashboard
2025-01-15 14:31:22 - audit - INFO - ADMIN_ACTION: Admin 292256687 disabled user 123456789
2025-01-15 14:32:05 - audit - WARNING - BLOCKED_ACCESS: Disabled user 123456789 attempted text message
```

## 🧪 Testing

```bash
# Run all tests including voice pipeline and admin features
pytest

# Run with verbose output
pytest -v

# Test specific functionality
pytest tests/test_language_detection.py::TestVoiceTranslationPipeline
pytest tests/test_language_detection.py::TestUserAnalytics
```

## 🏗️ Modular Architecture

**Clean separation of concerns - each package has a single responsibility:**

```
src/
├── main.py              # 🚀 Entry point
├── core/                # App initialization
│   ├── app.py           # Bot, Dispatcher, OpenAI client, DB
│   ├── config.py        # YAML configuration system
│   ├── cache.py         # Translation & TTS caching
│   └── constants.py     # Languages, admin IDs
├── handlers/            # Telegram event handlers
│   ├── commands.py      # /start, /menu, /admin
│   ├── callbacks.py     # Button interactions
│   ├── text.py         # Text message processing
│   └── voice.py        # Voice/audio processing
├── services/            # Business logic layer
│   ├── translation.py   # Translation + parallel TTS
│   ├── language.py      # Language detection
│   ├── analytics.py     # User analytics (atomic SQL)
│   └── audio.py         # Whisper transcription
├── storage/             # Data persistence layer
│   └── database.py      # Async SQLite manager
└── utils/               # Shared utilities
    ├── keyboards.py     # Inline keyboards
    └── formatting.py    # Text formatting
```

**Key Benefits:**
- 🧪 **Testable**: Business logic isolated from Telegram API
- 🔄 **Maintainable**: Clear boundaries and dependencies
- ⚡ **Performant**: Atomic SQL operations prevent race conditions
- 🏗️ **Scalable**: Easy to add new features without touching core logic

## 🚀 Deployment

**Current:** Manual deployment with systemd on Linux servers

**Docker (Planned):** Production containerization with:
- Multi-stage builds for optimized images
- docker-compose for easy deployment
- Health checks and monitoring
- PostgreSQL for production database
- Nginx reverse proxy


## ⚙️ Configuration

**Essential Variables:**
- `TELEGRAM_BOT_TOKEN` - Your bot token from [@BotFather](https://t.me/botfather)
- `OPENAI_API_KEY` - API key from [platform.openai.com](https://platform.openai.com/api-keys)
- `ADMIN_USER_ID` - Your Telegram user ID for `/admin` access

**Optional:**
- `OPENAI_MODEL=gpt-4o` (recommended: fast, accurate, cost-effective)
- `OPENAI_TTS_MODEL=tts-1` / `OPENAI_TTS_VOICE=alloy`

**Supported Languages:** Russian 🇷🇺, English 🇺🇸, Thai 🇹🇭, Japanese 🇯🇵, Korean 🇰🇷, Vietnamese 🇻🇳

## 🔧 Troubleshooting

**Bot not responding:** Check token, ensure bot isn't running elsewhere, disable webhook via [@BotFather](https://t.me/botfather)

**Translation failures:** Verify OpenAI API key, check billing/quota, try shorter text

**Voice issues:** Install FFmpeg, check file isn't corrupted, audio under 10min limit

**Admin access:** Ensure your user ID in `ADMIN_USER_ID`, use `/admin` command

**Performance:** Check logs, verify sufficient disk space, restart if needed

## 📄 License & Contributing

**License:** MIT - see [LICENSE](LICENSE) file

**Contributing:** Fork → Branch → Commit → Pull Request. Run `pytest` before submitting.

## 🙏 Credits

Built with [aiogram](https://github.com/aiogram/aiogram), [OpenAI](https://openai.com/), and [langdetect](https://github.com/Mimino666/langdetect)

---

<div align="center">

**Built with ❤️ for the global community**

*Making language barriers disappear, one message at a time* 🌍

</div>