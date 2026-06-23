#!/usr/bin/env python3
import asyncio
import logging
import os
import json
import datetime
from datetime import datetime
from typing import Dict, Optional
import asyncpg
import redis.asyncio as redis
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
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
                    id, telegram_id, username, first_name, last_name, 
                    balance_kopeks as balance, created_at, language
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
                    id, status, is_trial, traffic_limit_gb, traffic_used_gb, 
                    device_limit, end_date, created_at, tariff_id
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
        lines.append("❌ Нет active подписки")
    
    return "\n".join(lines)

# --- Клавиатуры управления ---
def get_user_keyboard():
    keyboard = [
        [KeyboardButton("📝 Создать обращение"), KeyboardButton("📊 Мои обращения")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, persistent=True)

def get_admin_keyboard():
    keyboard = [
        [KeyboardButton("📋 Открытые тикеты"), KeyboardButton("📈 Статистика")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, persistent=True)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user:
        return
        
    # Админское меню
    if user.id in ADMIN_IDS:
        await update.message.reply_text(
            f"👋 **Панель администратора**\n\n"
            "📌 Используйте нижнее меню для управления обращениями.\n"
            "Ответы отправляются пользователям напрямую.",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=get_admin_keyboard()
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
    
    await update.message.reply_text(
        f"👋 Здравствуйте, {user_data.get('first_name', 'пользователь')}!\n\n"
        "Это бот технической поддержки. Нажмите кнопку **«Создать обращение»** ниже, "
        "чтобы задать свой вопрос.",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=get_user_keyboard()
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data
    logger.info(f"Button pressed: {data}")
    
    if data == 'admin_tickets':
        await show_admin_tickets(update, context)
    elif data == 'admin_stats':
        await show_admin_stats(update, context)

async def show_admin_tickets(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отображение открытых тикетов с интерактивными кнопками управления"""
    is_callback = update.callback_query is not None
    msg_obj = update.callback_query.message if is_callback else update.message
    
    async with db_pool.acquire() as conn:
        tickets = await conn.fetch(
            """
            SELECT t.id, t.message, u.first_name, u.telegram_id
            FROM support_tickets t
            JOIN users u ON t.user_id = u.id
            WHERE t.status = 'open'
            ORDER BY t.created_at DESC LIMIT 10
            """
        )
    
    if not tickets:
        text = "📭 Нет открытых тикетов."
        keyboard = [[InlineKeyboardButton("🔄 Обновить", callback_data='admin_tickets')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        if is_callback:
            await msg_obj.edit_text(text, reply_markup=reply_markup)
        else:
            await msg_obj.reply_text(text, reply_markup=reply_markup)
        return
    
    text = "📋 **Список открытых обращений:**\n\n"
    keyboard = []
    
    for ticket in tickets:
        t_id = ticket['id']
        u_id = ticket['telegram_id']
        short_msg = ticket['message'][:30] + ('...' if len(ticket['message']) > 30 else '')
        text += f"🔹 **#{t_id}** | {ticket['first_name']}: _{short_msg}_\n"
        
        # Добавляем ряд кнопок для каждого тикета прямо в кабинет
        keyboard.append([
            InlineKeyboardButton(f"✏️ Ответить #{t_id}", callback_data=f"reply_{u_id}_{t_id}"),
            InlineKeyboardButton(f"❌ Закрыть #{t_id}", callback_data=f"close_{u_id}_{t_id}")
        ])
        
    keyboard.append([InlineKeyboardButton("🔄 Обновить список", callback_data='admin_tickets')])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if is_callback:
        await msg_obj.edit_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)
    else:
        await msg_obj.reply_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)

async def show_admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    is_callback = update.callback_query is not None
    msg_obj = update.callback_query.message if is_callback else update.message
    
    async with db_pool.acquire() as conn:
        total = await conn.fetchval("SELECT COUNT(*) FROM support_tickets")
        open_tickets = await conn.fetchval("SELECT COUNT(*) FROM support_tickets WHERE status = 'open'")
        today = datetime.now(pytz.UTC).date()
        closed_today = await conn.fetchval(
            "SELECT COUNT(*) FROM support_tickets WHERE status = 'closed' AND DATE(closed_at) = $1", today
        )
    
    text = (
        "📊 **Статистика поддержки**\n\n"
        f"📌 Всего обращений: {total}\n"
        f"🔄 Открытых: {open_tickets}\n"
        f"✅ Закрыто сегодня: {closed_today}\n"
    )
    keyboard = [[InlineKeyboardButton("🔄 Обновить", callback_data='admin_stats')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if is_callback:
        await msg_obj.edit_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)
    else:
        await msg_obj.reply_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user:
        return
    
    text = update.message.text
    
    # Роутинг на основе текстовых Reply-кнопок
    if text == "📝 Создать обращение":
        context.user_data['state'] = SupportStates.WAITING_FOR_MESSAGE
        await update.message.reply_text("📝 Опишите проблему. Можно прикрепить медиафайл.\nДля отмены: /cancel")
        return
    elif text == "📊 Мои обращения":
        await show_user_tickets(update, context)
        return
    elif text == "📋 Открытые тикеты" and user.id in ADMIN_IDS:
        await show_admin_tickets(update, context)
        return
    elif text == "📈 Статистика" and user.id in ADMIN_IDS:
        await show_admin_stats(update, context)
        return

    # Проверка состояний админа
    if user.id in ADMIN_IDS:
        state = context.user_data.get('state')
        if state == SupportStates.WAITING_FOR_REPLY:
            await handle_admin_message(update, context)
            return

    # Проверка состояний пользователя
    state = context.user_data.get('state')
    if state == SupportStates.WAITING_FOR_MESSAGE:
        await create_ticket(update, context)
    else:
        # Дефолтный ответ
        kb = get_admin_keyboard() if user.id in ADMIN_IDS else get_user_keyboard()
        await update.message.reply_text("Используйте кнопки меню для управления:", reply_markup=kb)

async def show_user_tickets(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_data = await get_user_data(user_id)
    if not user_data:
        return
        
    async with db_pool.acquire() as conn:
        tickets = await conn.fetch(
            "SELECT id, title, status, created_at FROM support_tickets WHERE user_id = $1 ORDER BY created_at DESC LIMIT 5",
            user_data['id']
        )
    
    if tickets:
        text = "📋 **Ваши обращения:**\n\n"
        for ticket in tickets:
            status_emoji = '✅' if ticket['status'] == 'closed' else '🔄'
            text += f"{status_emoji} #{ticket['id']} - {ticket['title']}\n📅 {ticket['created_at'].strftime('%d.%m.%Y %H:%M')}\n\n"
    else:
        text = "📭 У вас пока нет обращений."
        
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

async def create_ticket(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    message = update.message
    
    user_data = await get_user_data(user.id)
    if not user_data:
        return
    
    message_text = message.text or message.caption or "Вложение"
    
    # Пишем в БД сразу, чтобы получить реальный ID тикета
    try:
        async with db_pool.acquire() as conn:
            ticket_db_id = await conn.fetchval(
                """
                INSERT INTO support_tickets (user_id, title, message, status, created_at)
                VALUES ($1, $2, $3, 'open', NOW()) RETURNING id
                """,
                user_data['id'],
                message_text[:50] + ('...' if len(message_text) > 50 else ''),
                message_text
            )
    except Exception as e:
        logger.error(f"Error saving ticket: {e}")
        await message.reply_text("❌ Произошла ошибка базы данных. Попробуйте позже.")
        return

    # Кэшируем связку в Redis для поиска по callback_data (ограничение 64 байта)
    # Формат ключа: r_ticket:<ticket_db_id> -> значение user_id
    await redis_client.setex(f"r_ticket:{ticket_db_id}", 86400 * 7, str(user.id))
    
    user_info = await format_user_info(user_data)
    
    # Пересылаем админам с ID из базы данных
    for admin_id in ADMIN_IDS:
        try:
            keyboard = [
                [
                    InlineKeyboardButton("✏️ Ответить", callback_data=f"reply_{user.id}_{ticket_db_id}"),
                    InlineKeyboardButton("❌ Закрыть", callback_data=f"close_{user.id}_{ticket_db_id}")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            admin_text = (
                f"🔔 **НОВОЕ ОБРАЩЕНИЕ #{ticket_db_id}**\n\n"
                f"{user_info}\n\n"
                f"**Сообщение:**\n{message_text}"
            )
            
            await context.bot.send_message(
                chat_id=admin_id, text=admin_text,
                parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup
            )
            
            # Пересылка медиа, если есть
            if message.photo:
                await context.bot.send_photo(chat_id=admin_id, photo=message.photo[-1].file_id, caption="📎 Вложение")
            elif message.video:
                await context.bot.send_video(chat_id=admin_id, video=message.video.file_id, caption="📎 Вложение")
            elif message.document:
                await context.bot.send_document(chat_id=admin_id, document=message.document.file_id, caption="📎 Вложение")
                
        except Exception as e:
            logger.error(f"Error sending to admin {admin_id}: {e}")
    
    context.user_data['state'] = None
    await message.reply_text("✅ Ваше обращение отправлено в поддержку!")

async def handle_admin_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data
    parts = data.split('_')
    
    action = parts[0]
    user_id = int(parts[1])
    ticket_id = parts[2] # Это ID тикета из БД
    
    if action == 'reply':
        context.user_data['reply_to_user'] = user_id
        context.user_data['reply_ticket_id'] = ticket_id
        context.user_data['state'] = SupportStates.WAITING_FOR_REPLY
        
        await query.message.reply_text(
            f"✏️ Введите ваш ответ для пользователя.\nТикет: #{ticket_id}\n\nДля отмены: /cancel"
        )
        
    elif action == 'close':
        try:
            async with db_pool.acquire() as conn:
                await conn.execute(
                    "UPDATE support_tickets SET status = 'closed', closed_at = NOW() WHERE id = $1",
                    int(ticket_id)
                )
            
            # Пытаемся отредактировать сообщение с тикетом, убирая кнопки
            try:
                await query.edit_message_text(
                    text=query.message.text + "\n\n❌ **Тикет закрыт**",
                    parse_mode=ParseMode.MARKDOWN
                )
            except Exception:
                pass
                
            await query.message.reply_text(f"✅ Тикет #{ticket_id} закрыт.")
            
            # Оповещение юзера
            await context.bot.send_message(
                chat_id=user_id,
                text=f"ℹ️ Ваше обращение #{ticket_id} было успешно закрыто поддержкой."
            )
        except Exception as e:
            logger.error(f"Error closing ticket {ticket_id}: {e}")

async def handle_admin_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user or user.id not in ADMIN_IDS:
        return
        
    reply_to_user = context.user_data.get('reply_to_user')
    ticket_id = context.user_data.get('reply_ticket_id')
    
    if not reply_to_user:
        await update.message.reply_text("❌ Ошибка: сессия ответа потеряна.")
        context.user_data['state'] = None
        return
        
    try:
        await context.bot.send_message(
            chat_id=reply_to_user,
            text=f"📩 **Ответ техподдержки по тикету #{ticket_id}:**\n\n{update.message.text}",
            parse_mode=ParseMode.MARKDOWN
        )
        
        await update.message.reply_text(f"✅ Ответ по тикету #{ticket_id} отправлен.")
        
        context.user_data['state'] = None
        context.user_data['reply_to_user'] = None
        context.user_data['reply_ticket_id'] = None
    except Exception as e:
        logger.error(f"Error replying to user: {e}")
        await update.message.reply_text(f"❌ Ошибка отправки: {e}")

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['state'] = None
    context.user_data['reply_to_user'] = None
    context.user_data['reply_ticket_id'] = None
    
    kb = get_admin_keyboard() if update.effective_user.id in ADMIN_IDS else get_user_keyboard()
    await update.message.reply_text("✅ Действие отменено.", reply_markup=kb)

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
        logger.info("Tables checked/created")

def main():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    application = Application.builder().token(BOT_TOKEN).build()
    
    # ⚠️ КРИТИЧНО: Первыми регистрируем точные паттерны для CallbackQuery
    application.add_handler(CallbackQueryHandler(handle_admin_reply, pattern='^reply_'))
    application.add_handler(CallbackQueryHandler(handle_admin_reply, pattern='^close_'))
    application.add_handler(CallbackQueryHandler(button_handler, pattern='^admin_'))
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("cancel", cancel))
    
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(filters=filters.PHOTO | filters.VIDEO | filters.Document.ALL, handler=MessageHandler(handle_message))
    
    application.add_error_handler(error_handler)
    
    async def init():
        await init_db()
        await init_redis()
        await create_tables()
        
        await application.initialize()
        await application.start()
        await application.updater.start_polling()
        
        logger.info(f"Support bot updated & live! Admins: {ADMIN_IDS}")
        
        try:
            await asyncio.Event().wait()
        except KeyboardInterrupt:
            pass
        finally:
            await application.updater.stop()
            await application.stop()
            if db_pool: await db_pool.close()
            if redis_client: await redis_client.close()
            
    try:
        loop.run_until_complete(init())
    except KeyboardInterrupt:
        logger.info("Bot stopped")
    finally:
        loop.close()

if __name__ == '__main__':
    main()
