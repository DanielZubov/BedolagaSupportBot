#!/bin/bash

# Создание директории для бота поддержки
mkdir -p support-bot
cd support-bot

# Создание файлов
cat > Dockerfile << 'EOF'
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p logs data

CMD ["python", "bot.py"]
EOF

cat > requirements.txt << 'EOF'
python-telegram-bot==20.7
asyncpg==0.29.0
redis==5.0.1
python-dotenv==1.0.0
pytz==2023.3
aiohttp==3.9.1
EOF

# Создаем .env файл
cat > .env << 'EOF'
SUPPORT_BOT_TOKEN=YOUR_SUPPORT_BOT_TOKEN_HERE
ADMIN_IDS=
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_DB=remnawave_bot
POSTGRES_USER=remnawave_user
POSTGRES_PASSWORD=
REDIS_URL=redis://redis:6379/1
EOF

# Скачиваем bot.py
curl -o bot.py https://raw.githubusercontent.com/your-repo/support-bot/main/bot.py

# Возвращаемся в корневую директорию
cd ..

# Останавливаем существующий контейнер если есть
docker-compose -f docker-compose-support.yml down 2>/dev/null

# Запускаем бота поддержки
docker-compose -f docker-compose-support.yml up -d --build

echo "✅ Бот поддержки запущен!"
echo "📝 Не забудьте заменить SUPPORT_BOT_TOKEN в файле support-bot/.env"
