#🤖 Bedolaga Support Bot
Бот технической поддержки для сервиса Remnawave/Bedolaga с анонимной прослойкой между пользователями и администраторами.

📋 Возможности
🔒 Анонимная поддержка — скрывает личный Telegram профиль администратора

📊 Автоматический сбор данных — получает информацию о пользователе из БД Bedolaga

📝 Система тикетов — создание и управление обращениями

📎 Поддержка медиа — отправка фото, видео, документов

👥 Мультиадминистрирование — поддержка нескольких администраторов

🐳 Docker интеграция — работает в одной сети с Bedolaga

💾 Персистентное хранение — все тикеты сохраняются в БД

📦 Требования
Docker & Docker Compose

Работающий сервис Remnawave Bedolaga Bot

PostgreSQL и Redis (используются от Bedolaga)

Telegram Bot Token (получить у @BotFather)

🚀 Быстрый старт
1. Клонирование репозитория
bash
cd /opt
git clone https://github.com/DanielZubov/BedolagaSupportBot.git
cd BedolagaSupportBot
2. Настройка бота
Создайте файл конфигурации из примера:

bash
cp .env.example .env
Отредактируйте .env файл:

bash
nano .env
Обязательные параметры:

env
# Токен бота поддержки (создать у @BotFather)
SUPPORT_BOT_TOKEN=YOUR_BOT_TOKEN_HERE

# ID администраторов (через запятую)
ADMIN_IDS=123456789,987654321

# Настройки подключения к БД (должны совпадать с Bedolaga)
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_DB=remnawave_bot
POSTGRES_USER=remnawave_user
POSTGRES_PASSWORD=your_db_password

REDIS_URL=redis://redis:6379/1
Опциональные параметры:

env
# Часовой пояс
TZ=Europe/Moscow

# Уровень логирования
LOG_LEVEL=INFO

# Путь к логам
LOG_FILE=logs/bot.log
3. Запуск бота
bash
# Сборка и запуск
docker-compose -f docker-compose.yml up -d --build

# Проверка статуса
docker-compose -f docker-compose.yml ps

# Просмотр логов
docker-compose -f docker-compose.yml logs -f
4. Проверка работы
Отправьте команду /start вашему боту поддержки в Telegram. Если все настроено правильно, вы увидите главное меню.

🔧 Управление ботом
Базовые команды
bash
# Запуск бота
docker-compose -f docker-compose.yml up -d

# Остановка бота
docker-compose -f docker-compose.yml down

# Перезапуск бота
docker-compose -f docker-compose.yml restart

# Просмотр логов в реальном времени
docker-compose -f docker-compose.yml logs -f support-bot

# Обновление бота
git pull
docker-compose -f docker-compose.yml down
docker-compose -f docker-compose.yml up -d --build
Управление через Docker
bash
# Вход в контейнер
docker exec -it remnawave_support_bot bash

# Проверка здоровья контейнера
docker inspect remnawave_support_bot --format='{{.State.Health.Status}}'

# Очистка неиспользуемых образов
docker system prune -f
📝 Структура проекта
text
BedolagaSupportBot/
├── docker-compose.yml     # Docker Compose конфигурация
├── Dockerfile             # Docker образ бота
├── bot.py                 # Основной код бота
├── requirements.txt       # Python зависимости
├── .env.example           # Пример конфигурации
├── .env                   # Конфигурация (не в репозитории)
├── logs/                  # Логи бота
└── data/                  # Данные бота
🔌 Интеграция с Bedolaga
Использование общей сети
Бот использует существующую Docker сеть remnawave_bot_bot_network от Bedolaga, что позволяет:

Получать данные пользователей напрямую из БД

Использовать Redis для кэширования

Автоматически обнаруживать пользователей

Добавление кнопки поддержки в Bedolaga
Чтобы добавить кнопку "Поддержка" в главном боте, измените в .env Bedolaga:

env
# Ссылка на поддержку (можно указать ссылку на бота)
SUPPORT_USERNAME=https://t.me/YourSupportBot
📊 Использование
Для пользователей:
Отправьте /start боту поддержки

Выберите "Создать обращение"

Опишите проблему и отправьте сообщение

Получите уведомление, когда ответят

Для администраторов:
Получаете уведомление о новом обращении

Нажимаете "Ответить" под сообщением

Пишете ответ пользователю

Нажимаете "Закрыть" для завершения тикета

🔍 Логи и мониторинг
Просмотр логов
bash
# Все логи
docker-compose -f docker-compose.yml logs

# Только ошибки
docker-compose -f docker-compose.yml logs | grep ERROR

# Логи с временными метками
docker-compose -f docker-compose.yml logs --timestamps
Настройка логирования
В .env можно настроить уровень логирования:

env
LOG_LEVEL=DEBUG    # Отладка
LOG_LEVEL=INFO     # Информация (по умолчанию)
LOG_LEVEL=WARNING  # Только предупреждения
LOG_LEVEL=ERROR    # Только ошибки
🐛 Устранение неполадок
Бот не запускается
bash
# Проверьте .env файл
cat .env

# Проверьте наличие сети Docker
docker network ls | grep bot_network

# Проверьте логи
docker-compose -f docker-compose.yml logs support-bot
Ошибка подключения к БД
bash
# Проверьте, работает ли PostgreSQL
docker ps | grep postgres

# Проверьте настройки подключения
docker exec -it remnawave_support_bot python -c "
import asyncpg
import os
dsn = f'postgresql://{os.getenv(\"POSTGRES_USER\")}:{os.getenv(\"POSTGRES_PASSWORD\")}@{os.getenv(\"POSTGRES_HOST\")}:{os.getenv(\"POSTGRES_PORT\")}/{os.getenv(\"POSTGRES_DB\")}'
asyncpg.connect(dsn)
print('OK')
"
Сообщения не доходят до админов
bash
# Проверьте ID администраторов
echo $ADMIN_IDS

# Убедитесь, что бот может отправлять сообщения админу
docker exec -it remnawave_support_bot python -c "
import asyncio
from telegram import Bot
bot = Bot(token='YOUR_TOKEN')
asyncio.run(bot.send_message(chat_id=YOUR_ADMIN_ID, text='Test message'))
"
🔄 Обновление
Автоматическое обновление
bash
# Скрипт для быстрого обновления
./update.sh
Ручное обновление
bash
git pull
docker-compose -f docker-compose.yml down
docker-compose -f docker-compose.yml up -d --build
🔐 Безопасность
Рекомендации
Никогда не коммитьте .env файл — он уже в .gitignore

Используйте сложные пароли для БД

Регулярно обновляйте бота для получения исправлений

Ограничьте доступ к серверу только для нужных IP

Используйте HTTPS для всех внешних сервисов

Проверка безопасности
bash
# Проверка прав доступа к файлам
ls -la .env

# Проверка, что .env не в Git
git status | grep .env
📈 Мониторинг
Проверка здоровья бота
bash
# Статус контейнера
docker ps | grep support_bot

# Проверка через API (если включено)
curl -X GET http://localhost:8080/health
Метрики для мониторинга
Включите в .env:

env
# Включить метрики
METRICS_ENABLED=true

# Порт для метрик
METRICS_PORT=9090
🤝 Вклад в проект
Форкните репозиторий

Создайте ветку для вашей фичи (git checkout -b feature/amazing-feature)

Закоммитьте изменения (git commit -m 'Add amazing feature')

Запушьте ветку (git push origin feature/amazing-feature)

Откройте Pull Request

📄 Лицензия
Этот проект распространяется под лицензией MIT. Подробности в файле LICENSE.

📞 Поддержка
Telegram канал: @LeonVPN_Live

Основной бот: @Leon_VPNbot

Вопросы и предложения: Telegram

⚠️ Важно: Убедитесь, что основной бот Bedolaga запущен и работает перед запуском бота поддержки!

📝 Примечание: Замените YOUR_BOT_TOKEN_HERE и другие настройки в .env файле на ваши реальные значения.
