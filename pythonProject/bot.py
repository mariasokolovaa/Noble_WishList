import asyncio
import logging
import time

import psycopg2
from aiogram import Bot, Dispatcher, types  # type: ignore

logging.basicConfig(level=logging.INFO)

DATABASE_URL = "postgresql://postgres:postgres@localhost:5432/test"
conn = psycopg2.connect(DATABASE_URL)
cursor = conn.cursor()

cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        user_id BIGINT PRIMARY KEY,
        username VARCHAR(100),
        registration_date timestamp
    )
''')

cursor.execute('''
    CREATE TABLE IF NOT EXISTS categories (
        category_id BIGINT PRIMARY KEY,
        name VARCHAR(51),
        event_date timestamp,
        user_id BIGINT,
        FOREIGN KEY (user_id) REFERENCES users(user_id)
    )
''')

cursor.execute('''
    CREATE TABLE IF NOT EXISTS gifts (
        gift_id BIGINT PRIMARY KEY,
        title VARCHAR(71),
        description VARCHAR(101) DEFAULT NULL,
        link VARCHAR(255),
        event_date timestamp,
        category_id BIGINT,
        FOREIGN KEY (category_id) REFERENCES categories(category_id)
    )
''')
conn.commit()

TOKEN = "7899846498:AAFKR19Bj_M1Qxk9avBK5mfOgle-RZosPPU"
bot = Bot(token=TOKEN)
dp = Dispatcher(bot=bot)

@dp.message_handler(commands=['start'])
async def start_handler(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username # Get username
    reg_date = time.strftime("%Y-%m-%d %H:%M:%S") # Convert to timestamp string

    logging.info(f'{user_id=} {username=} {reg_date=}')

    # Insert user data into database using parameterized query
    try:
        cursor.execute(
            "INSERT INTO users (user_id, username, registration_date) VALUES (%s, %s, %s) ON CONFLICT (user_id) DO NOTHING",
            (user_id, username, reg_date),
        )
        conn.commit()
        logging.info(f"User {user_id} added to database.")
    except Exception as e:
        logging.error(f"Error inserting user data: {e}")

    await message.reply(f'''Привет, {username}!!!

    Это чат-бот wish_u_all_the_best! 🎉

    Здесь ты можешь создать список 
    твоих хотелок и поделиться ими с друзьями. 😊''')

async def main():
    try:
        await dp.start_polling(bot)
    except Exception as e:
        logging.error(f"Error in main polling: {e}")
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    asyncio.run(main())
