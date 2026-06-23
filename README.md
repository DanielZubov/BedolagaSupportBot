# 🤖 Bedolaga Support Bot

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11-blue.svg" alt="Python">
  <img src="https://img.shields.io/badge/Docker-20.10-blue.svg" alt="Docker">
  <img src="https://img.shields.io/badge/Telegram-Bot-blue.svg" alt="Telegram">
  <img src="https://img.shields.io/badge/License-MIT-green.svg" alt="License">
</p>

Бот технической поддержки для сервиса Remnawave/Bedolaga с анонимной прослойкой между пользователями и администраторами.

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
