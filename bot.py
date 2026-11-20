import asyncio
import os
import signal
import sys
from aiohttp import web
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from aiogram.filters import CommandStart

# --- НАСТРОЙКИ ---
BOT_TOKEN = os.environ.get("BOT_TOKEN")
WEB_APP_URL = os.environ.get("WEB_APP_URL", "https://poli-sa.github.io/advent-calendar/")

if not BOT_TOKEN:
    raise ValueError("Не задан BOT_TOKEN! Добавьте его в переменные окружения Render.")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# --- ОБРАБОТКА /start ---
@dp.message(CommandStart())
async def start_cmd(message: Message):
    # Кнопка открывает ваш Mini App
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🎁 Открыть Адвент-календарь", web_app=WebAppInfo(url=WEB_APP_URL))]
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

# --- ВЕБ-СЕРВЕР ДЛЯ RENDER (чтобы деплой не падал) ---
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
    # ВАЖНО: Очищаем возможные "висящие" соединения перед стартом
    await bot.delete_webhook(drop_pending_updates=True)
    
    # Настройка обработки сигналов (чтобы Render мог корректно выключить бота)
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, lambda: asyncio.create_task(on_shutdown()))
    
    asyncio.create_task(start_web_server())
    
    print("Bot is running...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())