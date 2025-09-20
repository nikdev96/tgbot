# 🌍 Telegram Translation Bot

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![aiogram](https://img.shields.io/badge/aiogram-3.x-green.svg)](https://docs.aiogram.dev/)
[![OpenAI](https://img.shields.io/badge/OpenAI-GPT--4o-orange.svg)](https://openai.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A smart Telegram bot that translates text and voice messages between **Russian** 🇷🇺, **English** 🇺🇸, **Thai** 🇹🇭, **Japanese** 🇯🇵, and **Korean** 🇰🇷 with customizable user preferences using OpenAI's latest models.

## ✨ Features

- 🎯 **Smart Language Detection** - Automatically identifies Russian, English, Thai, Japanese, and Korean
- ⚙️ **User Preferences** - Customizable target languages via `/menu` command
- 🔄 **Selective Translation** - Only translates to user-enabled languages
- 🎤 **Voice Message Support** - Transcribes and translates voice notes using OpenAI Whisper
- 🔊 **Voice Replies** - Optional TTS responses using OpenAI Audio API (female voice)
- 🚀 **Async Performance** - Built with aiogram 3.x for fast responses
- 🛡️ **Error Handling** - Retry logic with exponential backoff for API calls
- 🎨 **Interactive Menu** - Toggle translation targets and voice replies with checkbox buttons
- 🧹 **Auto Cleanup** - Temporary audio files automatically removed
- 👑 **Admin Dashboard** - User analytics, management, and access control
- 📊 **User Analytics** - Track activity, preferences, message counts, and voice usage
- 🔒 **Access Control** - Enable/disable user access with audit logging

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

### Prerequisites
- Python 3.11+
- FFmpeg (for audio processing)
- Telegram Bot Token from [@BotFather](https://t.me/botfather)
- OpenAI API Key

### System Dependencies

**Install FFmpeg:**

**macOS:**
```bash
brew install ffmpeg
```

**Ubuntu/Debian:**
```bash
sudo apt update
sudo apt install ffmpeg
```

**Windows:**
Download from [FFmpeg official site](https://ffmpeg.org/download.html) or use:
```bash
choco install ffmpeg  # Using Chocolatey
```

### Installation

```bash
# Clone repository
git clone https://github.com/nikdev96/tgbot.git
cd tgbot

# Install with Poetry (recommended)
curl -sSL https://install.python-poetry.org | python3 -
poetry install
poetry shell

# OR install with pip
python3.11 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install aiogram openai langdetect python-dotenv pydub
```

### Configuration
```bash
# Copy example configuration
cp .env.example .env

# Edit with your credentials
nano .env
```

Required environment variables:
```env
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_MODEL=gpt-4o
ADMIN_USER_ID=123456789

# Optional - Voice Replies (TTS)
OPENAI_TTS_MODEL=tts-1
OPENAI_TTS_VOICE=alloy
```

### 4. Get Your API Keys

**🤖 Telegram Bot Token:**
1. Message [@BotFather](https://t.me/botfather) on Telegram
2. Send `/newbot` and follow instructions
3. Copy the provided token

**🧠 OpenAI API Key:**
1. Visit [OpenAI API Keys](https://platform.openai.com/api-keys)
2. Create a new secret key
3. Copy the key (starts with `sk-`)

### 5. Run the Bot
```bash
# Using Poetry
poetry run python -m src.bot

# Using pip
python -m src.bot
```

🎉 **That's it!** Your bot is now running and ready to translate messages.

## 📱 Usage

### Regular Users
1. **Start**: Send `/start` for welcome message and instructions
2. **Menu**: Use `/menu` to configure translation preferences
3. **Text**: Send any text in Russian, English, Thai, Japanese, or Korean
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

### User Analytics (In-Memory)

**Tracked Data:**
- `is_disabled`: User access status
- `preferred_targets`: Language preferences
- `message_count`: Total messages processed
- `last_activity`: Last interaction timestamp
- `user_profile`: Username, first/last name

**⚠️ Note**: Analytics are stored in memory only. For production use, implement persistent storage (SQLite/Redis/PostgreSQL).

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

## 🏗️ Project Structure

```
telegram-translator-bot/
├── 📁 src/
│   ├── __init__.py
│   └── bot.py                 # 🤖 Main bot logic
├── 📁 tests/
│   ├── __init__.py
│   └── test_language_detection.py  # 🧪 Unit tests
├── pyproject.toml             # 📦 Poetry configuration
├── .env.example              # 🔧 Environment template
├── .env                      # 🔐 Your secrets (git-ignored)
├── README.md                 # 📖 This file
└── .gitignore               # 🚫 Git ignore rules
```

## 🚀 Deployment

### Option 1: Linux Server with systemd

1. **Upload code to server:**
```bash
scp -r . user@your-server:/opt/translator-bot/
```

2. **Setup on server:**
```bash
ssh user@your-server
cd /opt/translator-bot
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

3. **Create systemd service:**
```bash
sudo nano /etc/systemd/system/translator-bot.service
```

```ini
[Unit]
Description=Telegram Translation Bot
After=network.target

[Service]
Type=simple
User=your-user
WorkingDirectory=/opt/translator-bot
Environment=PATH=/opt/translator-bot/venv/bin
ExecStart=/opt/translator-bot/venv/bin/python -m src.bot
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

4. **Start service:**
```bash
sudo systemctl daemon-reload
sudo systemctl enable translator-bot
sudo systemctl start translator-bot
```

### Option 2: Docker (Coming Soon)

### Option 3: Cloud Platforms
- **Heroku** - Ready for deployment with Procfile
- **Railway** - One-click deployment
- **DigitalOcean App Platform** - Automated scaling

## 🔮 Future Enhancements

### Voice Message Support
The bot is prepared for voice translation via OpenAI Whisper:

```python
# TODO: Implement in src/bot.py
@dp.message(F.voice)
async def voice_handler(message: Message):
    file = await bot.get_file(message.voice.file_id)
    file_content = await bot.download_file(file.file_path)

    transcription = await openai_client.audio.transcriptions.create(
        model="whisper-1",
        file=file_content
    )

    # Process transcription through existing translation logic
```

### Planned Features
- 🎵 Voice message translation
- 📊 Usage analytics
- 🌐 Additional language support
- 💾 Translation history
- ⚡ Caching for faster responses

## ⚙️ Configuration

### Environment Variables
| Variable | Default | Description |
|----------|---------|-------------|
| `TELEGRAM_BOT_TOKEN` | Required | Your Telegram bot token |
| `OPENAI_API_KEY` | Required | OpenAI API key |
| `OPENAI_MODEL` | `gpt-4o` | Model to use (`gpt-4o`, `gpt-4-turbo`, `gpt-4`, `gpt-3.5-turbo`) |
| `ADMIN_USER_ID` | Optional | Comma-separated admin user IDs for `/admin` access |
| `OPENAI_TTS_MODEL` | `tts-1` | OpenAI TTS model (`tts-1`, `tts-1-hd`) |
| `OPENAI_TTS_VOICE` | `alloy` | TTS voice (`alloy`, `echo`, `fable`, `onyx`, `nova`, `shimmer`) |

### Model Recommendations
- **gpt-4o** (default) - ⭐ Best balance: fast, accurate, cost-effective
- **gpt-4-turbo** - High quality, slower, more expensive
- **gpt-4** - Standard quality, slowest
- **gpt-3.5-turbo** - Fastest, cheapest, lower quality for Thai

### Supported Languages
| Language | Code | Flag |
|----------|------|------|
| Russian | `ru` | 🇷🇺 |
| English | `en` | 🇺🇸 |
| Thai | `th` | 🇹🇭 |
| Japanese | `ja` | 🇯🇵 |
| Korean | `ko` | 🇰🇷 |

## 🔧 Troubleshooting

### Common Issues

**❌ Bot not responding**
- Verify bot token is correct
- Check if bot is already running elsewhere
- Ensure webhook is disabled (`/deleteWebhook` to @BotFather)

**❌ Translation failures**
- Verify OpenAI API key and billing status
- Check API quota and usage limits
- Try switching to `gpt-3.5-turbo` for cost efficiency (note: lower quality for Thai)

**❌ Language detection issues**
- Send longer text (minimum 5-10 words recommended)
- Ensure text is in Russian, English, Thai, Japanese, or Korean
- Mixed-language text may not detect properly

**❌ Voice processing fails**
- Ensure FFmpeg is installed and in PATH
- Check audio file isn't corrupted
- Verify sufficient disk space for temp files

**❌ Transcription errors**
- Speak clearly and avoid background noise
- Check OpenAI API quota for Whisper usage
- Ensure audio is under 10 minutes

**❌ "Audio too long" message**
- Split longer recordings into shorter segments
- Current limit is 10 minutes per message

**❌ "Access denied" for admin features**
- Verify your user ID is in `ADMIN_USER_ID` environment variable
- Use `/admin` command to access dashboard (admin only)
- Multiple admins: `ADMIN_USER_ID=123456789,987654321`

**❌ "Access disabled" for regular users**
- Contact administrator if you believe this is an error
- Admins can re-enable access via `/admin` dashboard

**❌ Voice replies not working**
- Ensure FFmpeg is installed and in PATH for audio conversion
- Check OpenAI API quota for TTS usage (separate from text completions)
- Verify `OPENAI_TTS_MODEL` and `OPENAI_TTS_VOICE` are correctly set
- Text longer than 500 characters will skip TTS automatically

**❌ \"TTS error\" or \"Voice reply error\"**
- Check OpenAI API billing status and TTS quota
- Verify internet connection for OpenAI API calls
- Check logs for specific error details (rate limits, API errors)

### Getting Help

1. 📖 Check this README for setup instructions
2. 🔧 Verify FFmpeg installation: `ffmpeg -version`
3. 🐛 [Open an issue](https://github.com/nikdev96/tgbot/issues) with error logs

## 🤝 Contributing

We welcome contributions! Here's how:

1. **Fork** the repository
2. **Create** a feature branch (`git checkout -b feature/amazing-feature`)
3. **Commit** your changes (`git commit -m 'Add amazing feature'`)
4. **Push** to the branch (`git push origin feature/amazing-feature`)
5. **Open** a Pull Request

### Development Setup
```bash
# Install dev dependencies
poetry install --with dev

# Format code
black src/ tests/
isort src/ tests/

# Lint code
flake8 src/ tests/

# Run tests
pytest
```

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- [aiogram](https://github.com/aiogram/aiogram) - Modern Telegram Bot API framework
- [OpenAI](https://openai.com/) - Powerful AI translation capabilities
- [langdetect](https://github.com/Mimino666/langdetect) - Language detection library

## 📊 Stats

![GitHub stars](https://img.shields.io/github/stars/yourusername/telegram-translator-bot?style=social)
![GitHub forks](https://img.shields.io/github/forks/yourusername/telegram-translator-bot?style=social)
![GitHub issues](https://img.shields.io/github/issues/yourusername/telegram-translator-bot)

---

<div align="center">

**Built with ❤️ for the global community**

*Making language barriers disappear, one message at a time* 🌍

</div>