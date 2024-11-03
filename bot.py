import time
import logging
from aiogram import Bot, Dispatcher, types, executor # type: ignore

TOKEN = "7761010862:AAGsr-eeZ28Ym4BQehU8zXlLctIJYvW4BqY"  # Token for the bot
bot = Bot(token=TOKEN)
dp = Dispatcher(bot=bot)


@dp.message_handler(commands=['start'])  # Handle the /start command
async def start_handler(message: types.Message):
    user_id = message.from_user.id
    user_full_name = message.from_user.first_name
    logging.info(f'{user_id=} {user_full_name=} {time.asctime()}')

    await message.reply(f'''Привет, {user_full_name}!!!

    Это чат-бот wish_u_all_the_best! 🎉

    Здесь ты можешь создать список 
    твоих хотелок и поделиться ими с друзьями. 😊''')

if __name__ == '__main__':
    executor.start_polling(dp)  # Pass dp to start_polling
