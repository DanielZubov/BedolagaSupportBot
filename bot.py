#!/usr/bin/env python3
import asyncio
import logging
import os
import json
from datetime import datetime
from typing import Dict, Optional
import asyncpg
import redis.asyncio as redis
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters
)
from telegram.constants import ParseMode
import pytz
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv('SUPPORT_BOT_TOKEN')
ADMIN_IDS = [int(id.strip()) for id in os.getenv('ADMIN_IDS', '').split(',') if id.strip()]
POSTGRES_DSN = f"postgresql://{os.getenv('POSTGRES_USER')}:{os.getenv('POSTGRES_PASSWORD')}@{os.getenv('POSTGRES_HOST')}:{os.getenv('POSTGRES_PORT')}/{os.getenv('POSTGRES_DB')}"
REDIS_URL = os.getenv('REDIS_URL', 'redis://redis:6379/1')

class SupportStates:
    WAITING_FOR_MESSAGE = 'waiting_message'
    WAITING_FOR_REPLY = 'waiting_reply'

db_pool = None
redis_client = None

async def init_db():
    global db_pool
    db_pool = await asyncpg.create_pool(
        POSTGRES_DSN,
        min_size=2,
        max_size=10,
        command_timeout=60
    )
    return db_pool

async def init_redis():
    global redis_client
    redis_client = await redis.from_url(REDIS_URL, decode_responses=True)
    return redis_client

async def get_user_data(telegram_id: int) -> Optional[Dict]:
    try:
        async with db_pool.acquire() as conn:
            user = await conn.fetchrow(
                """
                SELECT 
                    id,
                    telegram_id,
                    username,
                    first_name,
                    last_name,
                    balance_kopeks as balance,
                    created_at,
                    language
                FROM users 
                WHERE telegram_id = $1
                """,
                telegram_id
            )
            
            if not user:
                return None
                
            subscription = await conn.fetchrow(
                """
                SELECT 
                    id,
                    status,
                    is_trial,
                    traffic_limit_gb,
                    traffic_used_gb,
                    device_limit,
                    end_date,
                    created_at,
                    tariff_id
                FROM subscriptions 
                WHERE user_id = $1 AND status IN ('active', 'trial')
                ORDER BY created_at DESC 
                LIMIT 1
                """,
                user['id']
            )
            
            data = dict(user)
            if subscription:
                data['subscription'] = dict(subscription)
                data['subscription']['expires_at'] = subscription['end_date']
                
                traffic_limit = subscription['traffic_limit_gb'] or 0
                traffic_used = subscription['traffic_used_gb'] or 0
                
                if traffic_limit > 0:
                    used_percent = (traffic_used / traffic_limit) * 100
                    data['subscription']['used_percent'] = round(used_percent, 1)
                else:
                    data['subscription']['used_percent'] = 0
                    
                if subscription['end_date']:
                    days_left = (subscription['end_date'] - datetime.now(pytz.UTC)).days
                    data['subscription']['days_left'] = days_left
            else:
                data['subscription'] = None
                
            return data
    except Exception as e:
        logger.error(f"Error getting user data: {e}")
        return None

async def format_user_info(user_data: Dict) -> str:
    lines = [
        "📋 **ИНФОРМАЦИЯ О ПОЛЬЗОВАТЕЛЕ**",
        f"🆔 ID: `{user_data.get('telegram_id')}`",
        f"👤 Имя: {user_data.get('first_name', 'Не указано')}",
        f"🔗 Username: @{user_data.get('username', 'Не указан')}",
        f"💳 Баланс: {user_data.get('balance', 0) / 100:.2f} ₽",
        f"📅 Зарегистрирован: {user_data.get('created_at').strftime('%d.%m.%Y %H:%M') if user_data.get('created_at') else 'Неизвестно'}",
        "\n📦 **ПОДПИСКА:**"
    ]
    
    sub = user_data.get('subscription')
    if sub:
        status_text = '✅ Активна' if sub.get('status') == 'active' else '🔄 Триал'
        if sub.get('is_trial'):
            status_text = '🎯 Триал'
        lines.append(f"📊 Статус: {status_text}")
        lines.append(f"📶 Трафик: {sub.get('traffic_used_gb', 0):.1f} / {sub.get('traffic_limit_gb', 0):.1f} ГБ ({sub.get('used_percent', 0):.1f}%)")
        lines.append(f"📱 Устройств: {sub.get('device_limit', 0)}")
        if sub.get('end_date'):
            days = sub.get('days_left', 0)
            emoji = '🟢' if days > 7 else ('🟡' if days > 3 else '🔴')
            lines.append(f"⏳ Истекает: {sub.get('end_date').strftime('%d.%m.%Y %H:%M')} {emoji} ({days} дн.)")
    else:
        lines.append("❌ Нет активной подписки")
    
    return "\n".join(lines)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user:
        return
        
    # Админское меню
    if user.id in ADMIN_IDS:
        keyboard = [
            [InlineKeyboardButton("📋 Все открытые тикеты", callback_data='admin_tickets')],
            [InlineKeyboardButton("📊 Статистика", callback_data='admin_stats')],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"👋 **Панель администратора**\n\n"
            "📌 **Управление тикетами:**\n"
            "• Все обращения приходят автоматически\n"
            "• Используйте кнопки под сообщениями\n"
            "• Ответы отправляются анонимно\n\n"
            "Выберите действие:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
        return
    
    # Пользовательское меню
    user_data = await get_user_data(user.id)
    
    if not user_data:
        await update.message.reply_text(
            "❌ Похоже вы еще не зарегистрированы.\n"
            "Пожалуйста, сначала зарегистрируйтесь в основном боте - @Leon_VPNbot"
        )
        return
    
    context.user_data['user_data'] = user_data
    
    keyboard = [
        [InlineKeyboardButton("📝 Создать обращение", callback_data='new_ticket')],
        [InlineKeyboardButton("📊 Статус обращений", callback_data='my_tickets')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"👋 Здравствуйте, {user_data.get('first_name', 'пользователь')}!\n\n"
        "Это бот технической поддержки. Вы можете создать обращение, "
        "и наш специалист свяжется с вами.\n\n"
        "Пожалуйста, подробно опишите вашу проблему.",
        reply_markup=reply_markup
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    data = query.data
    
    # Админские кнопки
    if data == 'admin_tickets':
        await show_admin_tickets(update, context)
        return
    elif data == 'admin_stats':
        await show_admin_stats(update, context)
        return
    
    # Пользовательские кнопки
    if data == 'new_ticket':
        context.user_data['state'] = SupportStates.WAITING_FOR_MESSAGE
        await query.message.reply_text(
            "📝 Пожалуйста, опишите вашу проблему подробно.\n"
            "Вы можете отправить текст, фото, видео или документ.\n\n"
            "❗ Для отмены отправьте /cancel"
        )
    elif data == 'my_tickets':
        user_data = await get_user_data(user_id)
        if not user_data:
            await query.message.reply_text("❌ Пользователь не найден")
            return
            
        async with db_pool.acquire() as conn:
            tickets = await conn.fetch(
                """
                SELECT id, title, status, created_at
                FROM support_tickets
                WHERE user_id = $1
                ORDER BY created_at DESC
                LIMIT 10
                """,
                user_data['id']
            )
        
        if tickets:
            text = "📋 **Ваши обращения:**\n\n"
            for ticket in tickets:
                status_emoji = '✅' if ticket['status'] == 'closed' else '🔄'
                text += f"{status_emoji} #{ticket['id']} - {ticket['title']}\n"
                text += f"   📅 {ticket['created_at'].strftime('%d.%m.%Y %H:%M')}\n\n"
        else:
            text = "📭 У вас нет обращений."
        
        await query.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

async def show_admin_tickets(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать все открытые тикеты"""
    query = update.callback_query
    
    async with db_pool.acquire() as conn:
        tickets = await conn.fetch(
            """
            SELECT 
                t.id,
                t.title,
                t.status,
                t.created_at,
                u.first_name,
                u.username,
                u.telegram_id
            FROM support_tickets t
            JOIN users u ON t.user_id = u.id
            WHERE t.status = 'open'
            ORDER BY t.created_at DESC
            LIMIT 20
            """
        )
    
    if not tickets:
        await query.message.reply_text("📭 Нет открытых тикетов.")
        return
    
    text = "📋 **Открытые тикеты:**\n\n"
    for ticket in tickets:
        text += f"#{ticket['id']} - {ticket['title']}\n"
        text += f"👤 {ticket['first_name']} (@{ticket['username'] or 'нет'})\n"
        text += f"📅 {ticket['created_at'].strftime('%d.%m.%Y %H:%M')}\n\n"
    
    await query.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

async def show_admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать статистику"""
    query = update.callback_query
    
    async with db_pool.acquire() as conn:
        # Всего тикетов
        total = await conn.fetchval("SELECT COUNT(*) FROM support_tickets")
        
        # Открытых
        open_tickets = await conn.fetchval("SELECT COUNT(*) FROM support_tickets WHERE status = 'open'")
        
        # Закрытых за сегодня
        today = datetime.now(pytz.UTC).date()
        closed_today = await conn.fetchval(
            "SELECT COUNT(*) FROM support_tickets WHERE status = 'closed' AND DATE(closed_at) = $1",
            today
        )
    
    text = (
        "📊 **Статистика поддержки**\n\n"
        f"📌 Всего обращений: {total}\n"
        f"🔄 Открытых: {open_tickets}\n"
        f"✅ Закрыто сегодня: {closed_today}\n"
        f"📅 Дата: {today.strftime('%d.%m.%Y')}"
    )
    
    await query.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user:
        return
    
    if user.id in ADMIN_IDS:
        await update.message.reply_text(
            "ℹ️ Вы администратор. Используйте кнопки под сообщениями пользователей для ответа."
        )
        return
    
    state = context.user_data.get('state')
    
    if state == SupportStates.WAITING_FOR_MESSAGE:
        await create_ticket(update, context)
    else:
        await update.message.reply_text(
            "ℹ️ Используйте кнопку «Создать обращение» для связи с поддержкой.\n"
            "Или отправьте /start для главного меню."
        )

async def create_ticket(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    message = update.message
    
    if not user:
        return
    
    user_data = await get_user_data(user.id)
    if not user_data:
        await message.reply_text("❌ Ошибка: пользователь не найден.")
        return
    
    # Получаем текст сообщения
    message_text = message.text or message.caption or "Вложение"
    
    ticket_id = f"ticket_{user.id}_{datetime.now().timestamp()}"
    
    message_data = {
        'user_id': user.id,
        'text': message_text,
        'timestamp': datetime.now().isoformat(),
        'has_media': bool(message.photo or message.video or message.document)
    }
    
    await redis_client.setex(
        f"pending_ticket:{ticket_id}",
        3600,
        json.dumps(message_data)
    )
    
    user_info = await format_user_info(user_data)
    
    for admin_id in ADMIN_IDS:
        try:
            keyboard = [
                [
                    InlineKeyboardButton("✏️ Ответить", callback_data=f'reply_{user.id}_{ticket_id}'),
                    InlineKeyboardButton("❌ Закрыть", callback_data=f'close_{user.id}_{ticket_id}')
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            admin_text = (
                f"🔔 **НОВОЕ ОБРАЩЕНИЕ**\n\n"
                f"{user_info}\n\n"
                f"**Сообщение:**\n{message_text}"
            )
            
            await context.bot.send_message(
                chat_id=admin_id,
                text=admin_text,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=reply_markup
            )
            
            # Пересылаем медиа с текстом
            if message.photo:
                await context.bot.send_photo(
                    chat_id=admin_id,
                    photo=message.photo[-1].file_id,
                    caption=f"📎 Вложение к обращению\n\n{message.caption or ''}"
                )
            elif message.video:
                await context.bot.send_video(
                    chat_id=admin_id,
                    video=message.video.file_id,
                    caption=f"📎 Вложение к обращению\n\n{message.caption or ''}"
                )
            elif message.document:
                await context.bot.send_document(
                    chat_id=admin_id,
                    document=message.document.file_id,
                    caption=f"📎 Вложение к обращению\n\n{message.caption or ''}"
                )
                
        except Exception as e:
            logger.error(f"Error sending to admin {admin_id}: {e}")
    
    # Сохраняем тикет в БД
    try:
        async with db_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO support_tickets (
                    user_id, title, message, status, created_at
                ) VALUES ($1, $2, $3, 'open', NOW())
                """,
                user_data['id'],
                message_text[:50] + ('...' if len(message_text) > 50 else ''),
                message_text
            )
    except Exception as e:
        logger.error(f"Error saving ticket: {e}")
    
    context.user_data['state'] = None
    
    await message.reply_text(
        "✅ Ваше обращение отправлено в поддержку!\n"
        "Мы ответим вам в ближайшее время."
    )

async def handle_admin_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    
    try:
        await query.answer()
    except:
        pass
    
    data = query.data
    parts = data.split('_')
    
    if len(parts) < 3:
        await query.message.reply_text("❌ Ошибка: неверный формат данных")
        return
    
    action = parts[0]
    user_id = int(parts[1])
    ticket_id = parts[2]
    
    if action == 'reply':
        context.user_data['reply_to_user'] = user_id
        context.user_data['reply_ticket'] = ticket_id
        context.user_data['state'] = SupportStates.WAITING_FOR_REPLY
        
        await query.message.reply_text(
            f"✏️ Введите ваш ответ для пользователя.\n"
            f"Для отмены отправьте /cancel"
        )
    
    elif action == 'close':
        await redis_client.delete(f"pending_ticket:{ticket_id}")
        
        # Обновляем статус в БД
        try:
            async with db_pool.acquire() as conn:
                await conn.execute(
                    """
                    UPDATE support_tickets 
                    SET status = 'closed', closed_at = NOW() 
                    WHERE id = $1
                    """,
                    int(ticket_id.split('_')[-1]) if ticket_id.startswith('ticket_') else 0
                )
        except Exception as e:
            logger.error(f"Error closing ticket: {e}")
        
        await query.message.reply_text("✅ Тикет закрыт.")
        
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text="ℹ️ Ваше обращение было закрыто."
            )
        except Exception as e:
            logger.error(f"Error notifying user: {e}")

async def handle_admin_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user or user.id not in ADMIN_IDS:
        return
    
    state = context.user_data.get('state')
    if state != SupportStates.WAITING_FOR_REPLY:
        await update.message.reply_text("ℹ️ Вы не в режиме ответа. Используйте кнопку 'Ответить'.")
        return
    
    reply_to_user = context.user_data.get('reply_to_user')
    if not reply_to_user:
        await update.message.reply_text("❌ Ошибка: пользователь не найден.")
        return
    
    try:
        # Отправляем ответ пользователю
        await context.bot.send_message(
            chat_id=reply_to_user,
            text=f"📩 **Ответ поддержки:**\n\n{update.message.text}",
            parse_mode=ParseMode.MARKDOWN
        )
        
        await update.message.reply_text("✅ Ответ отправлен пользователю.")
        
        # Очищаем состояние
        context.user_data['state'] = None
        context.user_data['reply_to_user'] = None
        context.user_data['reply_ticket'] = None
        
    except Exception as e:
        logger.error(f"Error sending reply to user: {e}")
        await update.message.reply_text(f"❌ Ошибка при отправке: {e}")

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['state'] = None
    context.user_data['reply_to_user'] = None
    context.user_data['reply_ticket'] = None
    
    await update.message.reply_text(
        "✅ Действие отменено.\n"
        "Отправьте /start для главного меню."
    )

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Update {update} caused error {context.error}")

async def create_tables():
    async with db_pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS support_tickets (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                message TEXT,
                status VARCHAR(20) DEFAULT 'open',
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                closed_at TIMESTAMP WITH TIME ZONE
            )
        """)
        
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_tickets_user_id ON support_tickets(user_id)
        """)
        
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_tickets_status ON support_tickets(status)
        """)
        
        logger.info("Tables created/verified")

def main():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Команды
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("cancel", cancel))
    
    # Обработчики
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(MessageHandler(filters.PHOTO | filters.VIDEO | filters.Document.ALL, handle_message))
    
    # Обработчики админов
    application.add_handler(CallbackQueryHandler(handle_admin_reply, pattern='^reply_'))
    application.add_handler(CallbackQueryHandler(handle_admin_reply, pattern='^close_'))
    application.add_handler(MessageHandler(
        filters.TEXT & filters.User(ADMIN_IDS) & ~filters.COMMAND,
        handle_admin_message
    ))
    
    application.add_error_handler(error_handler)
    
    async def init():
        await init_db()
        await init_redis()
        await create_tables()
        
        await application.initialize()
        await application.start()
        await application.updater.start_polling()
        
        logger.info("Support bot started!")
        
        try:
            await asyncio.Event().wait()
        except KeyboardInterrupt:
            pass
        finally:
            await application.updater.stop()
            await application.stop()
            if db_pool:
                await db_pool.close()
            if redis_client:
                await redis_client.close()
    
    try:
        loop.run_until_complete(init())
    except KeyboardInterrupt:
        logger.info("Bot stopped")
    finally:
        loop.close()

if __name__ == '__main__':
    main()
