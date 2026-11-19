import asyncio
import os
import sqlite3
import signal
import sys
from datetime import datetime, timedelta
from aiohttp import web
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo, CallbackQuery
from aiogram.filters import CommandStart
from aiogram.exceptions import TelegramForbiddenError

# --- НАСТРОЙКИ ---
# ВСТАВЬТЕ НОВЫЙ ТОКЕН (СГЕНЕРИРУЙТЕ ЕГО В BOTFATHER!)
BOT_TOKEN = os.environ.get("BOT_TOKEN")
WEB_APP_URL = os.environ.get("WEB_APP_URL", "https://poli-sa.github.io/advent-calendar/")

if not BOT_TOKEN:
    raise ValueError("Не задан BOT_TOKEN! Добавьте его в переменные окружения Render.")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# --- БАЗА ДАННЫХ ---
DB_PATH = "users.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            first_name TEXT,
            subscribed INTEGER DEFAULT 0
        )
    """)
    conn.commit()
    conn.close()

def subscribe_user(user_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO users (user_id, subscribed) VALUES (?, 1) ON CONFLICT(user_id) DO UPDATE SET subscribed=1",
        (user_id,)
    )
    conn.commit()
    conn.close()

def get_subscribed_users():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users WHERE subscribed = 1")
    users = [row[0] for row in cursor.fetchall()]
    conn.close()
    return users

# --- ОБРАБОТКА /start ---
@dp.message(CommandStart())
async def start_cmd(message: Message):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO users (user_id, first_name) VALUES (?, ?)", 
                   (message.from_user.id, message.from_user.first_name))
    conn.commit()
    conn.close()

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🎁 Открыть Адвент-календарь", web_app=WebAppInfo(url=WEB_APP_URL))],
            [InlineKeyboardButton(text="🔔 Включить напоминания", callback_data="subscribe")]
        ]
    )
    
    await message.answer(
        "🎄 <b>Привет!</b>\n\n"
        "Добро пожаловать в наш новогодний адвент-календарь.\n"
        "Каждый день открывай новое окошко с подарком!\n\n"
        "👇 Нажми на кнопку ниже, чтобы начать.\n"
        "👇 А если хочешь получать напоминания каждое утро — нажми «Включить напоминания».",
        reply_markup=keyboard,
        parse_mode="HTML"
    )

# --- ОБРАБОТКА КНОПКИ "ВКЛЮЧИТЬ НАПОМИНАНИЯ" ---
@dp.callback_query(F.data == "subscribe")
async def process_subscribe(callback: CallbackQuery):
    user_id = callback.from_user.id
    subscribe_user(user_id)
    
    await callback.answer("Вы подписались на напоминания! 🔔")
    
    await callback.message.edit_text(
        "🎄 <b>Привет!</b>\n\n"
        "Добро пожаловать в наш новогодний адвент-календарь.\n"
        "Каждый день открывай новое окошко с подарком!\n\n"
        "✅ <b>Напоминания включены!</b> Бот будет присылать вам сообщение каждое утро в 08:00.",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🎁 Открыть Адвент-календарь", web_app=WebAppInfo(url=WEB_APP_URL))]
            ]
        ),
        parse_mode="HTML"
    )

# --- РАССЫЛКА НАПОМИНАНИЙ ---
async def daily_reminder():
    while True:
        now = datetime.now()
        target_time = now.replace(hour=8, minute=0, second=0, microsecond=0)
        if now > target_time:
            target_time += timedelta(days=1)
        
        wait_seconds = (target_time - now).total_seconds()
        print(f"Ждём {wait_seconds} секунд до рассылки...")
        await asyncio.sleep(wait_seconds)
        
        users = get_subscribed_users()
        print(f"Начинаем рассылку для {len(users)} пользователей...")
        
        for user_id in users:
            try:
                await bot.send_message(
                    chat_id=user_id,
                    text="🎄 <b>Доброе утро!</b>\n\nНе забудь открыть новое окошко в адвент-календаре!",
                    reply_markup=InlineKeyboardMarkup(
                        inline_keyboard=[[InlineKeyboardButton(text="Открыть календарь", web_app=WebAppInfo(url=WEB_APP_URL))]]
                    ),
                    parse_mode="HTML"
                )
                await asyncio.sleep(0.05)
            except TelegramForbiddenError:
                print(f"Пользователь {user_id} заблокировал бота.")
            except Exception as e:
                print(f"Ошибка отправки {user_id}: {e}")
                
        await asyncio.sleep(60)

# --- ФИКТИВНЫЙ ВЕБ-СЕРВЕР ДЛЯ RENDER ---
async def handle(request):
    return web.Response(text="Bot is running")

async def start_web_server():
    app = web.Application()
    app.router.add_get('/', handle)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    print(f"Web server started on port {port}")

# --- КОРРЕКТНОЕ ЗАВЕРШЕНИЕ РАБОТЫ ---
async def on_shutdown():
    print("Получен сигнал завершения, закрываем сессию бота...")
    await bot.session.close()
    sys.exit(0)

# --- ГЛАВНАЯ ФУНКЦИЯ ---
async def main():
    init_db()
    
    # ВАЖНО: Очищаем возможные "висящие" соединения перед стартом
    await bot.delete_webhook(drop_pending_updates=True)
    
    # Настройка обработки сигналов (чтобы Render мог корректно выключить бота)
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, lambda: asyncio.create_task(on_shutdown()))
    
    asyncio.create_task(start_web_server())
    asyncio.create_task(daily_reminder())
    
    print("Bot is running...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())