import asyncio
import json
import os
import signal
import sys
from datetime import datetime, timezone, timedelta
from aiohttp import web
from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
)
from aiogram.filters import CommandStart, Command

# Библиотеки для Google Таблиц
import gspread
from google.oauth2.service_account import Credentials

# --- НАСТРОЙКИ ---
BOT_TOKEN = os.environ.get("BOT_TOKEN")
WEB_APP_URL = os.environ.get("WEB_APP_URL", "https://poli-sa.github.io/advent-calendar/")
ADMIN_ID = int(os.environ.get("ADMIN_ID", "0"))
TZ_OFFSET = int(os.environ.get("TZ_OFFSET", "3"))
APP_TZ = timezone(timedelta(hours=TZ_OFFSET))

GOOGLE_CREDENTIALS = os.environ.get("GOOGLE_CREDENTIALS")
SPREADSHEET_ID = os.environ.get("SPREADSHEET_ID")

if not BOT_TOKEN:
    raise ValueError("Не задан BOT_TOKEN!")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Переменные для кэша в памяти (чтобы не дергать Google API лишний раз)
user_ids = set()
sent_24_year = None
sent_25_year = None

# --- РАБОТА С GOOGLE ТАБЛИЦЕЙ ---
def get_sheet():
    """Авторизуется в Google и возвращает первый лист таблицы."""
    if not GOOGLE_CREDENTIALS or not SPREADSHEET_ID:
        raise ValueError("Не заданы GOOGLE_CREDENTIALS или SPREADSHEET_ID")
        
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds_dict = json.loads(GOOGLE_CREDENTIALS)
    
    # Исправляем переносы строк в приватном ключе (частая проблема на Render)
    creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
    
    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    client = gspread.authorize(creds)
    return client.open_by_key(SPREADSHEET_ID).sheet1

async def load_users_from_sheet():
    """Загружает ID пользователей из таблицы при старте бота."""
    global user_ids
    try:
        sheet = get_sheet()
        records = sheet.get_all_records()
        user_ids.clear()
        for row in records:
            if "user_id" in row and row["user_id"]:
                try:
                    user_ids.add(int(row["user_id"]))
                except ValueError:
                    pass
        print(f"✅ Загружено {len(user_ids)} пользователей из Google Таблицы.")
    except Exception as e:
        print(f"⚠️ Ошибка загрузки из таблицы: {e}")

async def save_user_to_sheet(user_id, name):
    """Добавляет нового пользователя или обновляет имя/дату у существующего."""
    try:
        sheet = get_sheet()
        cell = sheet.find(str(user_id), in_column=1)
        now_str = datetime.now(APP_TZ).strftime("%Y-%m-%d %H:%M")
        
        if cell:
            # Пользователь уже есть, обновляем имя и дату последнего визита
            sheet.update_cell(cell.row, 2, name)
            sheet.update_cell(cell.row, 5, now_str)
        else:
            # Новый пользователь — добавляем строку
            sheet.append_row([user_id, name, "", "", now_str])
            
        user_ids.add(user_id)
    except Exception as e:
        print(f"⚠️ Ошибка сохранения пользователя {user_id}: {e}")

async def save_rating_to_sheet(user_id, score=None, comment=None):
    """Сохраняет оценку и/или комментарий пользователя."""
    try:
        sheet = get_sheet()
        cell = sheet.find(str(user_id), in_column=1)
        if cell:
            if score is not None:
                sheet.update_cell(cell.row, 3, score)
            if comment is not None:
                sheet.update_cell(cell.row, 4, comment)
        else:
            # Если пользователя нет в таблице (например, написал отзыв без старта), создаем строку
            now_str = datetime.now(APP_TZ).strftime("%Y-%m-%d %H:%M")
            sheet.append_row([user_id, "Неизвестный", score or "", comment or "", now_str])
    except Exception as e:
        print(f"⚠️ Ошибка сохранения оценки {user_id}: {e}")


# --- ЛОГИКА БОТА ---
def is_calendar_closed(now: datetime | None = None) -> bool:
    now = now or datetime.now(APP_TZ)
    return now.month == 12 and now.day >= 25

def build_rating_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=f"{i} ⭐", callback_data=f"rate:{i}") for i in range(1, 6)
    ]])

def build_dec24_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎁 Открыть Адвент-календарь", web_app=WebAppInfo(url=WEB_APP_URL))],
        [InlineKeyboardButton(text=f"{i} ⭐", callback_data=f"rate:{i}") for i in range(1, 6)]
    ])

@dp.message(CommandStart())
async def start_cmd(message: Message):
    # Сохраняем пользователя в Google Таблицу
    await save_user_to_sheet(message.from_user.id, message.from_user.full_name)

    if is_calendar_closed():
        await message.answer(
            "🎄 <b>Рождественский адвент-календарь закрыт до следующего года!</b>\n\n"
            "Спасибо, что провели этот декабрь с нами. Увидимся в следующем году! ✨",
            reply_markup=build_rating_keyboard(), parse_mode="HTML"
        )
        return

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎁 Открыть Адвент-календарь", web_app=WebAppInfo(url=WEB_APP_URL))]
    ])
    await message.answer(
        "🎄 <b>Привет!</b>\n\nДобро пожаловать в наш новогодний адвент-календарь.\n"
        "Каждый день открывай новое окошко с подарком!\n\n"
        "👇 Нажми на кнопку ниже, чтобы начать.",
        reply_markup=keyboard, parse_mode="HTML"
    )

@dp.callback_query(F.data.startswith("rate:"))
async def handle_rating_callback(callback: CallbackQuery):
    score = int(callback.data.split(":")[1])
    await save_rating_to_sheet(callback.from_user.id, score=score)
    await callback.answer(f"Спасибо за оценку {score} ⭐!")
    await callback.message.answer(
        f"Спасибо за вашу оценку: <b>{'⭐' * score} ({score}/5)</b>! 🎄\n\n"
        "Если хотите, напишите ответным сообщением пару слов о календаре.",
        parse_mode="HTML"
    )

@dp.message(F.text & ~F.text.startswith("/"))
async def handle_review_text(message: Message):
    # Сохраняем текст как комментарий
    await save_rating_to_sheet(message.from_user.id, comment=message.text)
    await message.answer("💌 Спасибо за тёплый отзыв!")

# --- РАССЫЛКИ ---
async def send_dec24_reminder():
    await load_users_from_sheet() # Обновляем список перед рассылкой
    print(f"Рассылка 24 декабря для {len(user_ids)} пользователей...")
    text = "🎄 <b>Сегодня 24 декабря — финальный день!</b>\n\nСпасибо, что были с нами! ✨\nОцените календарь:"
    for uid in user_ids:
        try:
            await bot.send_message(uid, text, reply_markup=build_dec24_keyboard(), parse_mode="HTML")
            await asyncio.sleep(0.05) # Защита от блокировки Telegram
        except Exception:
            pass

async def send_dec25_closing():
    await load_users_from_sheet()
    print(f"Закрытие календаря 25 декабря для {len(user_ids)} пользователей...")
    text = "❄️ <b>С Рождеством и наступающим Новым годом!</b>\n\nАдвент-календарь закрыт. Увидимся в следующем году! 🎄✨"
    for uid in user_ids:
        try:
            await bot.send_message(uid, text, parse_mode="HTML")
            await asyncio.sleep(0.05)
        except Exception:
            pass

# --- ПЛАНИРОВЩИК И ВЕБ-СЕРВЕР ---
async def calendar_scheduler_loop():
    global sent_24_year, sent_25_year
    while True:
        try:
            now = datetime.now(APP_TZ)
            if now.month == 12 and now.day == 24 and now.hour >= 11 and sent_24_year != now.year:
                await send_dec24_reminder()
                sent_24_year = now.year
            if now.month == 12 and now.day == 25 and now.hour >= 0 and sent_25_year != now.year:
                await send_dec25_closing()
                sent_25_year = now.year
        except Exception as e:
            print(f"Ошибка в планировщике: {e}")
        await asyncio.sleep(60)

async def handle(request):
    return web.Response(text="Bot is running")

async def start_web_server():
    app = web.Application()
    app.router.add_get("/", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

async def on_shutdown():
    await bot.session.close()
    sys.exit(0)

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    
    # Загружаем пользователей при старте
    await load_users_from_sheet()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, lambda: asyncio.create_task(on_shutdown()))

    asyncio.create_task(start_web_server())
    asyncio.create_task(calendar_scheduler_loop())

    print("🚀 Бот запущен с Google Sheets!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())