import asyncio
import os
import sqlite3
import signal
import sys
from datetime import datetime, timedelta
from aiohttp import web
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo, CallbackQuery, BotCommand
from aiogram.filters import CommandStart, Command
from aiogram.exceptions import TelegramForbiddenError

# --- НАСТРОЙКИ ---
BOT_TOKEN = os.environ.get("BOT_TOKEN")
WEB_APP_URL = os.environ.get("WEB_APP_URL", "https://poli-sa.github.io/advent-calendar/")

if not BOT_TOKEN:
    raise ValueError("Не задан BOT_TOKEN!")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# ВАШ ID (для админских команд)
ADMIN_ID = 7684212166  # ЗАМЕНИТЕ НА ВАШ ID!

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

# --- УСТАНОВКА МЕНЮ КОМАНД ---
async def set_commands():
    commands = [
        BotCommand(command="start", description="🎄 Главное меню"),
        BotCommand(command="days", description="⏳ Сколько дней до Нового года"),
    ]
    await bot.set_my_commands(commands)

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
            [InlineKeyboardButton(text="🔔 Включить напоминания", callback_data="subscribe")],
            [InlineKeyboardButton(text="⏳ Сколько дней до НГ?", callback_data="days_left")]
        ]
    )
    
    await message.answer(
        "🎄 <b>Привет!</b>\n\n"
        "Добро пожаловать в наш новогодний адвент-календарь.\n"
        "Каждый день открывай новое окошко с подарком!\n\n"
        "👇 Нажми на кнопку ниже, чтобы начать.",
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
        "Добро пожаловать в наш новогодний адвент-календарь.\n\n"
        "✅ <b>Напоминания включены!</b> Бот будет присылать вам сообщение каждое утро в 08:00.",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🎁 Открыть Адвент-календарь", web_app=WebAppInfo(url=WEB_APP_URL))]
            ]
        ),
        parse_mode="HTML"
    )

# --- КОМАНДА "СКОЛЬКО ДНЕЙ ДО НОВОГО ГОДА" ---
@dp.message(Command("days"))
async def days_cmd(message: Message):
    now = datetime.now()
    next_year = now.year + 1 if now.month == 12 and now.day >= 31 else now.year
    new_year = datetime(next_year, 1, 1)
    
    delta = new_year - now
    days_left = delta.days
    
    await message.answer(
        f"⏳ До Нового года осталось: <b>{days_left} дней</b>!\n\n"
        "🎅 А пока не забудь открыть сегодняшнее окошко в календаре!",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🎁 Открыть календарь", web_app=WebAppInfo(url=WEB_APP_URL))]
            ]
        ),
        parse_mode="HTML"
    )

# --- ТАКЖЕ ДОБАВИМ КНОПКУ ИЗ CALLBACK ДЛЯ "ДНЕЙ" ---
@dp.callback_query(F.data == "days_left")
async def days_callback(callback: CallbackQuery):
    await callback.answer()
    now = datetime.now()
    next_year = now.year + 1 if now.month == 12 and now.day >= 31 else now.year
    new_year = datetime(next_year, 1, 1)
    days_left = (new_year - now).days
    
    await callback.message.answer(
        f"⏳ До Нового года осталось: <b>{days_left} дней</b>!",
        parse_mode="HTML"
    )

# --- ТЕСТОВАЯ КОМАНДА ---
@dp.message(Command("test"))
async def test_reminder(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    await message.answer("⏳ Запускаю тестовую рассылку...")
    users = get_subscribed_users()
    count = 0
    for user_id in users:
        try:
            await bot.send_message(
                chat_id=user_id,
                text="🎄 <b>Тестовое напоминание!</b>",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Открыть календарь", web_app=WebAppInfo(url=WEB_APP_URL))]]),
                parse_mode="HTML"
            )
            count += 1
            await asyncio.sleep(0.05)
        except Exception as e:
            print(f"Ошибка: {e}")
    await message.answer(f"✅ Отправлено: {count} чел.")

# --- ПРОСМОТР БАЗЫ ---
@dp.message(Command("users"))
async def show_users(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, first_name, subscribed FROM users")
    all_users = cursor.fetchall()
    conn.close()
    if not all_users:
        await message.answer("База пуста.")
        return
    text = "📊 <b>База:</b>\n\n"
    count_sub = 0
    for u in all_users:
        user_id, first_name, subscribed = u
        status = "✅" if subscribed == 1 else "❌"
        if subscribed == 1: count_sub += 1
        text += f"• {first_name} (ID: <code>{user_id}</code>) {status}\n"
    text += f"\n<b>Всего:</b> {len(all_users)} | <b>Подписаны:</b> {count_sub}"
    await message.answer(text, parse_mode="HTML")

# --- ЕЖЕДНЕВНЫЕ И ПРАЗДНИЧНЫЕ РАССЫЛКИ ---
async def daily_reminder():
    # Флаги, чтобы праздничные сообщения не отправлялись дважды в день
    sent_dec25 = False
    sent_ny = False
    sent_jan1_end = False

    while True:
        now = datetime.now()
        target_time = now.replace(hour=8, minute=0, second=0, microsecond=0)
        if now > target_time:
            target_time += timedelta(days=1)
        
        wait_seconds = (target_time - now).total_seconds()
        print(f"Ждём {wait_seconds} секунд...")
        await asyncio.sleep(wait_seconds)
        
        # Сбрасываем флаги при смене дня
        if now.hour == 0 and now.minute < 10:
            sent_dec25 = False
            sent_ny = False
            sent_jan1_end = False

        users = get_subscribed_users()
        if not users:
            continue

        current_date = datetime.now()
        text_to_send = ""
        button_text = "Открыть календарь"
        
        # Логика праздничных сообщений
        if current_date.month == 12 and current_date.day == 25 and not sent_dec25:
            text_to_send = "🎄 <b>С Рождеством!</b>\n\nПусть этот день будет наполнен теплом, уютом и волшебством. Открывай скорее окошко!"
            sent_dec25 = True
        elif current_date.month == 12 and current_date.day == 31 and not sent_ny:
            text_to_send = "🥂 <b>С наступающим Новым годом!</b>\n\nПусть следующий год принесёт только радость и счастье! Успей открыть последнее окошко!"
            sent_ny = True
        elif current_date.month == 1 and current_date.day == 1 and not sent_jan1_end:
            text_to_send = "🎉 <b>С Новым годом!</b>\n\nПусть этот год будет лучше предыдущего! Спасибо, что был с нами. До встречи в следующем году!"
            button_text = "Закрыть календарь"
            sent_jan1_end = True
        else:
            text_to_send = "🎄 <b>Доброе утро!</b>\n\nНе забудь открыть новое окошко в адвент-календаре!"

        for user_id in users:
            try:
                await bot.send_message(
                    chat_id=user_id,
                    text=text_to_send,
                    reply_markup=InlineKeyboardMarkup(
                        inline_keyboard=[[InlineKeyboardButton(text=button_text, web_app=WebAppInfo(url=WEB_APP_URL))]]
                    ),
                    parse_mode="HTML"
                )
                await asyncio.sleep(0.05)
            except TelegramForbiddenError:
                pass
            except Exception as e:
                print(f"Ошибка отправки {user_id}: {e}")
                
        await asyncio.sleep(60)

# --- ВЕБ-СЕРВЕР ---
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

# --- ЗАВЕРШЕНИЕ ---
async def on_shutdown():
    await bot.session.close()
    sys.exit(0)

# --- ГЛАВНАЯ ---
async def main():
    init_db()
    await set_commands()
    await bot.delete_webhook(drop_pending_updates=True)
    
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, lambda: asyncio.create_task(on_shutdown()))
    
    asyncio.create_task(start_web_server())
    asyncio.create_task(daily_reminder())
    
    print("Bot is running...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())