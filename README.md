# 🌍 Telegram Переводчик

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![aiogram](https://img.shields.io/badge/aiogram-3.x-green.svg)](https://docs.aiogram.dev/)
[![OpenAI](https://img.shields.io/badge/OpenAI-GPT--4o-orange.svg)](https://openai.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Умный Telegram бот для перевода текста и голосовых сообщений между **6 языками** 🇷🇺🇺🇸🇹🇭🇯🇵🇰🇷🇻🇳 с настраиваемыми пользовательскими предпочтениями.

## 🚀 Статус: Готов к продакшену v2.4.0

⚡ **Производительность:** Обработка голоса ~9с (было 22с), параллельная генерация TTS  
🏗️ **Архитектура:** Модульная структура с разделением на core, handlers, services, storage  
🧪 **Тестирование:** Офлайн тесты с моками OpenAI, атомарные SQL операции  

## ✨ Возможности

### 🔄 Переводы
- **Автоопределение языка** - Русский, английский, тайский, японский, корейский, вьетнамский
- **Настройки пользователя** - Выбор целевых языков через `/menu`
- **Голосовые сообщения** - Распознавание через Whisper + перевод
- **Голосовые ответы** - TTS с переключением для каждого пользователя

### ⚡ Производительность
- **Параллельная обработка** - Ускорение на 60%+ для голосовых сообщений
- **Умное кэширование** - Переводы (1ч) + TTS (30мин) с постоянным хранением
- **Защита от гонок** - Атомарные операции в базе данных
- **Повторные попытки** - Логика с экспоненциальной задержкой

### 👑 Админ панель
- **Управление пользователями** - `/admin` панель
- **Аналитика** - Отслеживание активности, счетчики сообщений
- **Контроль доступа** - Включение/отключение пользователей с аудитом

## 🛠️ Установка

```bash
git clone https://github.com/yourusername/tgbot
cd tgbot
python3 -m venv .venv
source .venv/bin/activate  # Linux/Mac
pip install -r requirements.txt
```

## ⚙️ Настройка

1. **Создайте `.env` файл:**
```bash
cp .env.example .env
```

2. **Заполните переменные:**
```bash
TELEGRAM_BOT_TOKEN=your_bot_token
OPENAI_API_KEY=sk-your-openai-key
```

3. **Настройте конфигурацию:**
- `config/development.yaml` - для разработки
- `config/production.yaml` - для продакшена

## 🚀 Запуск

### Разработка
```bash
source .venv/bin/activate
python -m src.main
```

### Продакшен (systemd)
```bash
sudo cp translator-bot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable translator-bot
sudo systemctl start translator-bot
```

## 🧪 Тестирование

```bash
# Запуск всех тестов
python -m pytest tests/

# Тесты базы данных
python -m pytest tests/test_database.py -v

# Тесты определения языка
python -m pytest tests/test_language_detection.py -v
```

## 📁 Структура проекта

```
tgbot/
├── src/
│   ├── core/          # Основные компоненты (app, config, cache)
│   ├── handlers/      # Обработчики сообщений
│   ├── services/      # Бизнес-логика (перевод, голос, аналитика)
│   └── storage/       # База данных и хранение
├── config/            # YAML конфигурации
├── tests/            # Тесты с моками
└── data/             # SQLite база данных
```

## 🔧 Системные требования

- **Python:** 3.11+ (совместим с 3.13)
- **FFmpeg:** Для обработки аудио
- **SQLite:** Встроенная база данных
- **Память:** ~200MB RAM
- **Диск:** ~50MB для логов и кэша

## 📝 Команды бота

- `/start` - Начать работу с ботом
- `/menu` - Настройки языков перевода
- `/admin` - Админ панель (только для админов)
- `/help` - Справка по командам

## 🐛 Решение проблем

### Python 3.13 + pydub
Если возникают проблемы с модулем `audioop`, бот автоматически переключается на ffmpeg fallback.

### Нехватка места на диске
```bash
# Очистка логов
sudo journalctl --vacuum-time=7d
rm -rf logs/archive/*
```

### Проблемы с FFmpeg
```bash
# Ubuntu/Debian
sudo apt update && sudo apt install ffmpeg

# Проверка
ffmpeg -version
```

## 📄 Лицензия

MIT License - см. файл [LICENSE](LICENSE)

## 🤝 Поддержка

При возникновении вопросов создавайте Issues в GitHub репозитории.
