import time
import logging
import os
from aiogram import Bot, Dispatcher, types  # type: ignore
import psycopg2
import asyncio

# Configure logging
logging.basicConfig(level=logging.INFO)

# Database configuration
DATABASE_URL = os.environ.get("DATABASE_URL") or "postgresql://postgres:postgresd@localhost:5432/test"
conn = psycopg2.connect(DATABASE_URL)
cursor = conn.cursor()

# Create the `users` table if it doesn't exist
cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        user_id BIGINT PRIMARY KEY,  -- set user_id as a primary key
        user_full_name VARCHAR(100)
    )
''')
conn.commit()

# Bot configuration
TOKEN = "7899846498:AAFKR19Bj_M1Qxk9avBK5mfOgle-RZosPPU"
bot = Bot(token=TOKEN)
dp = Dispatcher(bot=bot)

@dp.message_handler(commands=['start'])  # Handle the /start command
async def start_handler(message: types.Message):
    user_id = message.from_user.id
    user_full_name = message.from_user.first_name
    logging.info(f'{user_id=} {user_full_name=} {time.asctime()}')

    # Insert user data into database
    try:
        cursor.execute(
            "INSERT INTO users (user_id, user_full_name) VALUES (%s, %s) ON CONFLICT (user_id) DO NOTHING",
            (user_id, user_full_name),
        )
        conn.commit()
        logging.info(f"User {user_id} added to database.")
    except Exception as e:
        logging.error(f"Error inserting user data: {e}")

    await message.reply(f'''Привет, {user_full_name}!!!

    Это чат-бот wish_u_all_the_best! 🎉

    Здесь ты можешь создать список 
    твоих хотелок и поделиться ими с друзьями. 😊''')

async def main():
    try:
        await dp.start_polling(bot)
    except Exception as e:
        logging.error(f"Error in main polling: {e}")

if __name__ == "__main__":
    asyncio.run(main())
