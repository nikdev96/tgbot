# 🌍 Telegram Translation Bot

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![aiogram](https://img.shields.io/badge/aiogram-3.x-green.svg)](https://docs.aiogram.dev/)
[![OpenAI](https://img.shields.io/badge/OpenAI-GPT--4-orange.svg)](https://openai.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A smart Telegram bot that automatically detects and translates messages between **Russian** 🇷🇺, **English** 🇺🇸, and **Thai** 🇹🇭 using OpenAI's powerful translation capabilities.

## ✨ Features

- 🎯 **Smart Language Detection** - Automatically identifies Russian, English, and Thai text
- 🔄 **Dual Translation** - Translates to the other two supported languages in separate messages
- 🚀 **Async Performance** - Built with aiogram 3.x for lightning-fast responses
- 🛡️ **Error Handling** - Robust retry logic with exponential backoff for API calls
- 🏗️ **Production Ready** - Clean architecture, logging, and comprehensive testing
- 🎨 **Clean UI** - Country flags, auto-deleting status messages, helpful examples
- 🔮 **Voice Ready** - Prepared structure for future voice message support via Whisper

## 🎬 Demo

**Input:** `Привет, как дела сегодня?`

**Output:**
```
🇺🇸 English:
Hello, how are you doing today?

🇹🇭 Thai:
สวัสดี เป็นอย่างไรบ้าง วันนี้?
```

## 🚀 Quick Start

### 1. Clone the Repository
```bash
git clone https://github.com/yourusername/telegram-translator-bot.git
cd telegram-translator-bot
```

### 2. Install Dependencies

**Option A: Using Poetry (Recommended)**
```bash
# Install Poetry
curl -sSL https://install.python-poetry.org | python3 -

# Install dependencies
poetry install
poetry shell
```

**Option B: Using pip + venv**
```bash
python3.11 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install aiogram openai langdetect python-dotenv pytest pytest-asyncio
```

### 3. Configure Environment
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
OPENAI_MODEL=gpt-4
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

1. **Start the bot** - Send `/start` to see the welcome message
2. **Send any text** in Russian, English, or Thai
3. **Get translations** in the other two languages as separate messages

### Example Interactions

```
👤 User: Hello, how are you?

🤖 Bot: 🇷🇺 Russian:
Привет, как дела?

🤖 Bot: 🇹🇭 Thai:
สวัสดี เป็นอย่างไรบ้าง?
```

## 🧪 Testing

Run the test suite to ensure everything works correctly:

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run with coverage
pytest --cov=src
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
| `OPENAI_MODEL` | `gpt-4` | Model to use (`gpt-4`, `gpt-4-turbo`, `gpt-3.5-turbo`) |

### Supported Languages
| Language | Code | Flag |
|----------|------|------|
| Russian | `ru` | 🇷🇺 |
| English | `en` | 🇺🇸 |
| Thai | `th` | 🇹🇭 |

## 🔧 Troubleshooting

### Common Issues

**❌ Bot not responding**
- Verify bot token is correct
- Check if bot is already running elsewhere
- Ensure webhook is disabled (`/deleteWebhook` to @BotFather)

**❌ Translation failures**
- Verify OpenAI API key and billing status
- Check API quota and usage limits
- Try switching to `gpt-3.5-turbo` for cost efficiency

**❌ Language detection issues**
- Send longer text (minimum 5-10 words recommended)
- Ensure text is in Russian, English, or Thai
- Mixed-language text may not detect properly

### Getting Help

1. 📖 Check this README
2. 🐛 [Open an issue](https://github.com/yourusername/telegram-translator-bot/issues)
3. 💬 [Discussions](https://github.com/yourusername/telegram-translator-bot/discussions)

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