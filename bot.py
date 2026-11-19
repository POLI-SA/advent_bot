import asyncio
import os
from datetime import datetime, timedelta
from aiohttp import web  # Добавляем веб-сервер
from aiogram import Bot, Dispatcher
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from aiogram.filters import CommandStart

# ... (ваш существующий код для BOT_TOKEN, WEB_APP_URL, CHAT_ID и т.д.) ...

# --- ВАШ СУЩЕСТВУЮЩИЙ КОД БОТА (start_cmd, daily_reminder) ---
# ...

# --- НОВЫЙ БЛОК: ФИКТИВНЫЙ ВЕБ-СЕРВЕР ДЛЯ RENDER ---
async def handle(request):
    return web.Response(text="Bot is running")

async def start_web_server():
    app = web.Application()
    app.router.add_get('/', handle)
    runner = web.AppRunner(app)
    await runner.setup()
    # Render передает порт через переменную окружения PORT
    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    print(f"Web server started on port {port}")

async def main():
    # Запускаем веб-сервер для Render
    asyncio.create_task(start_web_server())
    
    # Запускаем фоновую задачу для напоминаний
    asyncio.create_task(daily_reminder())
    
    print("Bot and web server are running...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())