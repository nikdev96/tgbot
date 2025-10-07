# 📱 Telegram Bot Monitoring System

## ✨ **Красивые алерты настроены!**

Система теперь отправляет красиво отформатированные уведомления с:
- 🎨 Эмодзи и визуальными индикаторами
- 📋 Структурированными разделами  
- 💻 Блоками кода для команд
- ⚡ Четким форматированием Markdown

---

## 🚨 **Типы алертов:**

### 🔴 **КРИТИЧЕСКИЕ** - Бот упал
```
🔴 CRITICAL ALERT

❌ Translator Bot is DOWN!
The service has stopped and requires immediate attention.

📋 Service Details:
• Status: Failed/Stopped  
• Service: translator-bot.service

📄 Recent Logs:
```
Logs here...
```

🔧 Immediate Actions:
1. Check status: systemctl status translator-bot.service
2. View full logs: journalctl -u translator-bot.service -n 20  
3. Restart service: systemctl restart translator-bot.service
```

### ✅ **ВОССТАНОВЛЕНИЕ** - Бот восстановлен  
```
✅ RECOVERY SUCCESS

🤖 Translator Bot is BACK ONLINE!
The service has recovered and is running normally again.

🔧 Service Details:
• Status: Running
• Service: translator-bot.service
• Recovery: Automatic
```

### ⚠️ **ПРЕДУПРЕЖДЕНИЯ** - Высокое потребление памяти
```
⚠️ HIGH MEMORY USAGE WARNING  

🐘 Memory consumption is high
The bot is using significant memory resources.

📊 Resource Details:
• Memory Usage: 1024 MB
• Process ID: 12345

💡 Recommendations:
• Monitor for memory leaks
• Consider restarting if usage grows
```

---

## 🛠️ **Команды управления:**

### 📊 **Системный отчет**
```bash
./monitoring/system_info.sh
```
Отправляет красивый отчет о состоянии системы и бота.

### 🧪 **Тестовый алерт**
```bash
./monitoring/telegram_alert.sh "🧪 Тестовое сообщение"
```

### 🔍 **Проверка статуса**
```bash
./monitoring/check_bot_status.sh
```

### 📄 **Просмотр логов**
```bash
tail -f logs/monitoring.log
```

---

## ⚙️ **Файлы системы:**

- `telegram_alert.sh` - 📱 Отправка красивых алертов
- `check_bot_status.sh` - 🔍 Мониторинг статуса  
- `system_info.sh` - 📊 Системный отчет
- `.env` - ⚙️ Конфигурация
- `README.md` - 📖 Документация

---

## 🔄 **Автоматический мониторинг:**

- ✅ **Каждые 2 минуты** - cron проверка
- ✅ **Мгновенно** - SystemD OnFailure  
- ✅ **Красивые алерты** - форматированные уведомления
- ✅ **Логирование** - все события сохраняются

---

## 📞 **Поддержка:**

Все алерты содержат готовые команды для диагностики и исправления проблем.

**Ваш Translator Bot теперь под надежной защитой с красивыми уведомлениями!** 🤖✨📱
