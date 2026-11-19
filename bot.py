import asyncio
import os
from datetime import datetime, timedelta
from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from aiogram.filters import CommandStart

# 1. ВСТАВЬТЕ ВАШ ТОКЕН ИЗ BOTFATHER
BOT_TOKEN = "9285771934:AAF35GN7b0UAxN24KNTC6ZZX7SuQpcp4CJQ"
# 2. ВАША ССЫЛКА НА GITHUB PAGES
WEB_APP_URL = "https://poli-sa.github.io/advent-calendar/"
# 3. ВАШ ID ЧАТА (ГРУППЫ ИЛИ ЛИЧНЫЙ)
CHAT_ID = "ВАШ_CHAT_ID_ЗДЕСЬ"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# --- ОБРАБОТКА КОМАНДЫ /start ---
@dp.message(CommandStart())
async def start_cmd(message: Message):
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🎁 Открыть Адвент-календарь", web_app=WebAppInfo(url=WEB_APP_URL))]
        ]
    )
    await message.answer(
        "🎄 <b>Привет!</b>\n\nДобро пожаловать в наш новогодний адвент-календарь.\n"
        "Каждый день открывай новое окошко с подарком!\n\n"
        "Нажми на кнопку ниже, чтобы начать:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )

# --- ФУНКЦИЯ ДЛЯ ЕЖЕДНЕВНОГО НАПОМИНАНИЯ ---
async def daily_reminder():
    while True:
        now = datetime.now()
        # ЗАДАЙТЕ ВРЕМЯ ОТПРАВКИ (например, 08:00 утра)
        target_time = now.replace(hour=8, minute=0, second=0, microsecond=0)
        
        if now > target_time:
            target_time += timedelta(days=1)
        
        wait_seconds = (target_time - now).total_seconds()
        print(f"Следующее напоминание через {wait_seconds} секунд (в {target_time})")
        
        await asyncio.sleep(wait_seconds)
        
        try:
            await bot.send_message(
                chat_id=CHAT_ID,
                text="🎄 <b>Доброе утро!</b>\n\nНе забудьте открыть новое окошко в нашем адвент-календаре!\n👇",
                reply_markup=InlineKeyboardMarkup(
                    inline_keyboard=[
                        [InlineKeyboardButton(text="Открыть календарь", web_app=WebAppInfo(url=WEB_APP_URL))]
                    ]
                ),
                parse_mode="HTML"
            )
            print("Напоминание отправлено!")
        except Exception as e:
            print(f"Ошибка отправки: {e}")
        
        await asyncio.sleep(60)

# --- ФИКТИВНЫЙ ВЕБ-СЕРВЕР ДЛЯ RENDER (чтобы деплой не падал) ---
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

# --- ГЛАВНАЯ ФУНКЦИЯ ---
async def main():
    # Запускаем веб-сервер для Render
    asyncio.create_task(start_web_server())
    
    # Запускаем фоновую задачу для напоминаний
    asyncio.create_task(daily_reminder())
    
    print("Bot and web server are running...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())