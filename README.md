# 🤖 Bedolaga Support Bot

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11-blue.svg" alt="Python">
  <img src="https://img.shields.io/badge/Docker-20.10-blue.svg" alt="Docker">
  <img src="https://img.shields.io/badge/Telegram-Bot-blue.svg" alt="Telegram">
  <img src="https://img.shields.io/badge/License-MIT-green.svg" alt="License">
</p>

Бот технической поддержки для Bedolaga.

## ✨ Особенности

| Функция | Описание |
|---------|----------|
| 🔒 **Анонимная поддержка** | Полностью скрывает личный Telegram профиль администратора |
| 📊 **Автоматический сбор данных** | Получает информацию о пользователе из БД Bedolaga |
| 📝 **Система тикетов** | Создание и управление обращениями в поддержку |
| 📎 **Поддержка медиа** | Отправка фото, видео, документов в обращениях |
| 👥 **Мультиадминистрирование** | Поддержка нескольких администраторов одновременно |
| 🐳 **Docker интеграция** | Работает в одной сети с Bedolaga без конфликтов |
| 💾 **Персистентное хранение** | Все тикеты сохраняются в базе данных |
| 🔄 **Автоматическое обновление** | Простое обновление через Git и Docker |

## 📦 Требования

Перед установкой убедитесь, что у вас есть:

- ✅ Docker & Docker Compose
- ✅ Работающий сервис [Remnawave Bedolaga Bot](https://github.com/fr1ngg/remnawave-bedolaga-telegram-bot)
- ✅ PostgreSQL и Redis (используются от Bedolaga)
- ✅ Telegram Bot Token (получить у [@BotFather](https://t.me/BotFather))

## 🚀 Быстрый старт

### 1. Клонирование репозитория

```bash
cd /opt
git clone https://github.com/DanielZubov/BedolagaSupportBot.git
cd BedolagaSupportBot
```

### 2. Настройка бота
#### Создайте файл конфигурации из примера:
```bash
cp .env.example .env
```
#### Отредактируйте ```.env``` файл:
```bash
nano .env
```
## 📋 Конфигурация
```bash
# ===============================================
# 🤖 BEDOLAGA SUPPORT BOT CONFIGURATION
# ===============================================

# ===== TELEGRAM BOT =====
# Токен бота поддержки от @BotFather
# ВАЖНО: Создайте нового бота специально для поддержки
SUPPORT_BOT_TOKEN=YOUR_BOT_TOKEN_HERE

# ID администраторов (через запятую)
# Можно найти в @userinfobot или в логах основного бота
ADMIN_IDS=123456789,987654321

# ===== DATABASE CONFIGURATION =====
# Настройки подключения к БД (должны совпадать с Bedolaga)
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_DB=remnawave_bot
POSTGRES_USER=remnawave_user
POSTGRES_PASSWORD=your_secure_password

# ===== REDIS CONFIGURATION =====
REDIS_URL=redis://redis:6379/1

# ===== SYSTEM =====
# Часовой пояс
TZ=Europe/Moscow

# Уровень логирования: DEBUG, INFO, WARNING, ERROR
LOG_LEVEL=INFO
```
### 3. Запуск бота
```bash
# Сборка и запуск контейнера
docker-compose -f docker-compose.yml up -d --build

# Проверка статуса
docker-compose -f docker-compose.yml ps

# Просмотр логов в реальном времени
docker-compose -f docker-compose.yml logs -f support-bot
```
### 4. Проверка работы
1. Отправьте команду /start вашему боту поддержки в Telegram

2. Если все настроено правильно — вы увидите главное меню

3. Создайте тестовое обращение и проверьте получение уведомления у админа

## 🔧 Управление ботом
| Команда | Описание |
|---------|----------|
| ```docker-compose -f docker-compose.yml up -d``` | Запуск бота в фоновом режиме |
| ```docker-compose -f docker-compose.yml down``` | Остановка и удаление контейнера |
| ```docker-compose -f docker-compose.yml restart``` | Перезапуск бота |
| ```docker-compose -f docker-compose.yml logs -f support-bot``` | Просмотр логов в реальном времени |
| ```docker-compose -f docker-compose.yml ps``` | Проверка статуса контейнера |

## 🔄Обновление бота
```bash
# Получение последних изменений
git pull

# Пересборка и запуск
docker-compose -f docker-compose.yml down
docker-compose -f docker-compose.yml up -d --build

# Очистка старых образов (опционально)
docker system prune -f
```
## 📁 Структура проекта
```text
BedolagaSupportBot/
├── 📄 docker-compose.yml     # Docker Compose конфигурация
├── 📄 Dockerfile             # Docker образ бота
├── 📄 bot.py                 # Основной код бота (на Python)
├── 📄 requirements.txt       # Python зависимости
├── 📄 .env.example           # Пример конфигурации
├── 📄 .env                   # Конфигурация (не в репозитории!)
├── 📄 .gitignore             # Исключения для Git
├── 📄 README.md              # Документация
├── 📁 logs/                  # Логи бота
└── 📁 data/                  # Данные и кэш
```
## 🔌 Интеграция с Bedolaga
### Сетевая интеграция
Бот использует существующую Docker сеть remnawave_bot_bot_network от Bedolaga, что позволяет:

✅ Получать данные пользователей напрямую из БД

✅ Использовать Redis для кэширования сессий

✅ Автоматически обнаруживать зарегистрированных пользователей

✅ Работать в одной экосистеме без дополнительных настроек

## 📊 Использование бота
### 👤 Для пользователей
1. Отправьте /start боту поддержки
2. Нажмите "📝 Создать обращение"
3. Опишите проблему
4. Дождитесь ответа

### Для администраторов:
1. Получаете уведомление с данными пользователя
2. Нажмите "✏️ Ответить" под сообщением
3. Напишите ответ — он уйдет анонимно
4. Нажмите "❌ Закрыть" для завершения тикета


⚠️ Важно: Основной бот Bedolaga должен быть запущен до старта бота поддержки!

📝 Примечание: Замените YOUR_BOT_TOKEN_HERE в .env на реальный токен от @BotFather.
