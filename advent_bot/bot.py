import asyncio
from aiogram import Bot, Dispatcher
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from aiogram.filters import CommandStart

# 1. ВСТАВЬТЕ ВАШ ТОКЕН (который выдал BotFather)
BOT_TOKEN = "9285771934:AAF35GN7b0UAxN24KNTC6ZZX7SuQpcp4CJQ"

# 2. ВАША ССЫЛКА НА GITHUB PAGES
WEB_APP_URL = "https://poli-sa.github.io/advent-calendar/"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

@dp.message(CommandStart())
async def start_cmd(message: Message):
    # Создаем кнопку, которая откроет Mini App
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🎁 Открыть Адвент-календарь", 
                    web_app=WebAppInfo(url=WEB_APP_URL)
                )
            ]
        ]
    )
    
    # Отправляем текст и кнопку
    await message.answer(
        "🎄 <b>Привет!</b>\n\n"
        "Добро пожаловать в наш новогодний адвент-календарь.\n"
        "Каждый день открывай новое окошко с подарком!\n\n"
        "Нажми на кнопку ниже, чтобы начать:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )

async def main():
    print("Бот запущен...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())