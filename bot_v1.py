
import time
import logging
import os
import asyncio
import json
import uuid
from aiogram import Bot, Dispatcher, types
from aiogram.contrib.middlewares.logging import LoggingMiddleware
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
import psycopg2

logging.basicConfig(level=logging.INFO)

DATABASE_URL = os.environ.get("DATABASE_URL") or "postgresql://postgres:postgresd@localhost:5432/test"
conn = psycopg2.connect(DATABASE_URL)
cursor = conn.cursor()

# Create tables and initialize the default catalog
cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        user_id BIGINT PRIMARY KEY,
        username VARCHAR(100),
        registration_date DATE DEFAULT CURRENT_DATE
    );

    CREATE TABLE IF NOT EXISTS catalogs (
        catalog_id SERIAL PRIMARY KEY,
        user_id BIGINT REFERENCES users(user_id),
        name VARCHAR(50) NOT NULL,
        event_date DATE
    );

    CREATE TABLE IF NOT EXISTS gifts (
        gift_id SERIAL PRIMARY KEY,
        catalog_id INT REFERENCES catalogs(catalog_id),
        title VARCHAR(70) NOT NULL,
        description TEXT,
        link TEXT
    );
''')
conn.commit()

cursor.execute("SELECT catalog_id FROM catalogs WHERE catalog_id = 1")
default_catalog_exists = cursor.fetchone()

if not default_catalog_exists:
    cursor.execute("INSERT INTO catalogs (catalog_id, user_id, name) VALUES (1, NULL, 'Общий список')")
    conn.commit()

TOKEN = ""
bot_v1 = Bot(token=TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot=bot_v1, storage=storage)
dp.middleware.setup(LoggingMiddleware())

main_menu = ReplyKeyboardMarkup(resize_keyboard=True)
main_menu.add(KeyboardButton("📜 Просмотреть подарки"), KeyboardButton("➕ Добавить подарок"))
main_menu.add(KeyboardButton("🗑 Удалить подарок"), KeyboardButton("✏️ Изменить подарок"))
main_menu.add(KeyboardButton("📁 Создать каталог"), KeyboardButton("🎁 Переход в каталог"))
main_menu.add(KeyboardButton("📤 Поделиться виш-листом"))

class Form(StatesGroup):
    add_item_name = State()
    add_item_description = State()
    add_item_link = State()
    add_item_category = State()
    create_catalog_name = State()
    create_catalog_date = State()

@dp.message_handler(commands=['start'])
async def start_handler(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.first_name
    logging.info(f'{user_id=} {username=} {time.asctime()}')

    try:
        cursor.execute(
            "INSERT INTO users (user_id, username) VALUES (%s, %s) ON CONFLICT (user_id) DO NOTHING",
            (user_id, username),
        )
        conn.commit()
    except Exception as e:
        logging.error(f"Error inserting user data: {e}")

    await message.reply(
        f"Привет, {username}! 🎉 Добро пожаловать в wish_u_all_the_best! Здесь ты можешь создавать и управлять своим списком желаний. 😊",
        reply_markup=main_menu
    )

@dp.message_handler(lambda message: message.text == "📜 Просмотреть подарки")
async def view_wishlist_handler(message: types.Message):
    user_id = message.from_user.id
    cursor.execute("SELECT title, description, link FROM gifts WHERE catalog_id = 1 OR catalog_id IN (SELECT catalog_id FROM catalogs WHERE user_id = %s)", (user_id,))
    items = cursor.fetchall()

    if items:
        response = "🎁 Ваш список желаний:\n\n"
        for item in items[:20]:  # Display up to 20 items
            response += f"🔹 {item[0]} - {item[1] or 'Без описания'}\n{item[2]}\n\n"
    else:
        response = "Ваш список желаний пуст."

    await message.reply(response, reply_markup=main_menu)
@dp.message_handler(lambda message: message.text == "➕ Добавить подарок")
async def add_item_start(message: types.Message):
    await Form.add_item_name.set()
    await message.reply("Введите название подарка (не менее 3 символов):")

@dp.message_handler(state=Form.add_item_name)
async def add_item_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await Form.next()
    await message.reply("Введите описание подарка (или пропустите):")

@dp.message_handler(state=Form.add_item_description)
async def add_item_description(message: types.Message, state: FSMContext):
    await state.update_data(description=message.text)
    await Form.next()
    await message.reply("Введите ссылку на подарок:")

@dp.message_handler(state=Form.add_item_link)
async def add_item_link(message: types.Message, state: FSMContext):
    await state.update_data(link=message.text)
    await Form.next()
    await message.reply("Введите категорию подарка (или пропустите):")

@dp.message_handler(state=Form.add_item_category)
async def add_item_category(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    data = await state.get_data()
    category_name = message.text or "Общий список"

    # Check if the catalog exists
    cursor.execute("SELECT catalog_id FROM catalogs WHERE name = %s AND user_id = %s", (category_name, user_id))
    result = cursor.fetchone()

    if result:
        catalog_id = result[0]
    else:
        cursor.execute(
            "INSERT INTO catalogs (user_id, name) VALUES (%s, %s) RETURNING catalog_id",
            (user_id, category_name)
        )
        catalog_id = cursor.fetchone()[0]
        conn.commit()

    cursor.execute(
        "INSERT INTO gifts (catalog_id, title, description, link) VALUES (%s, %s, %s, %s)",
        (catalog_id, data['name'], data.get('description'), data['link'])
    )
    conn.commit()
    await state.finish()
    await message.reply("Подарок добавлен в ваш список желаний!", reply_markup=main_menu)


@dp.message_handler(lambda message: message.text == "📁 Создать каталог")
async def create_catalog_start(message: types.Message):
    await Form.create_catalog_name.set()
    await message.reply("Введите название каталога (не менее 5 символов):")

@dp.message_handler(state=Form.create_catalog_name)
async def create_catalog_name(message: types.Message, state: FSMContext):
    await state.update_data(catalog_name=message.text)
    await Form.next()
    await message.reply("Введите дату празднования (в формате YYYY-MM-DD) или пропустите:")

@dp.message_handler(state=Form.create_catalog_date)
async def create_catalog_date(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    data = await state.get_data()

    catalog_date = message.text if message.text else None
    cursor.execute(
        "INSERT INTO catalogs (user_id, name, event_date) VALUES (%s, %s, %s)",
        (user_id, data['catalog_name'], catalog_date)
    )
    conn.commit()
    await state.finish()
    await message.reply("Каталог создан!", reply_markup=main_menu)

# Share Wishlist with HTML Link (User Story 11)
@dp.message_handler(state=Form.add_item_name)
async def add_item_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await Form.next()
    await message.reply("Введите описание подарка (или пропустите):")


@dp.message_handler(state=Form.add_item_description)
async def add_item_description(message: types.Message, state: FSMContext):
    await state.update_data(description=message.text)
    await Form.next()
    await message.reply("Введите ссылку на подарок:")


@dp.message_handler(state=Form.add_item_link)
async def add_item_link(message: types.Message, state: FSMContext):
    await state.update_data(link=message.text)
    await Form.next()
    await message.reply("Введите категорию подарка (или пропустите):")


@dp.message_handler(state=Form.add_item_category)
async def add_item_category(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    data = await state.get_data()

    cursor.execute(
        "INSERT INTO wishlist_items (user_id, name, description, link, category) VALUES (%s, %s, %s, %s, %s)",
        (user_id, data['name'], data.get('description'), data['link'], message.text)
    )
    conn.commit()
    await state.finish()
    await message.reply("Подарок добавлен в ваш список желаний!", reply_markup=main_menu)


# User Story 4: Delete Item from Wishlist
@dp.message_handler(lambda message: message.text == "🗑 Удалить подарок")
async def delete_item_start(message: types.Message):
    user_id = message.from_user.id
    cursor.execute("SELECT item_id, name FROM wishlist_items WHERE user_id = %s", (user_id,))
    items = cursor.fetchall()

    if items:
        keyboard = InlineKeyboardMarkup()
        for item_id, name in items:
            keyboard.add(InlineKeyboardButton(f"Удалить {name}", callback_data=f"delete_{item_id}"))
        await message.reply("Выберите подарок для удаления:", reply_markup=keyboard)
    else:
        await message.reply("Ваш список желаний пуст.", reply_markup=main_menu)


@dp.callback_query_handler(lambda call: call.data.startswith("delete_"))
async def delete_item_callback(call: types.CallbackQuery):
    item_id = int(call.data.split("_")[1])
    cursor.execute("DELETE FROM wishlist_items WHERE item_id = %s", (item_id,))
    conn.commit()
    await call.message.edit_text("Подарок удален!", reply_markup=main_menu)


# User Story 8: Create New Catalog
@dp.message_handler(lambda message: message.text == "📁 Создать каталог")
async def create_catalog_start(message: types.Message):
    await Form.create_catalog_name.set()
    await message.reply("Введите название каталога (не менее 5 символов):")


@dp.message_handler(state=Form.create_catalog_name)
async def create_catalog_name(message: types.Message, state: FSMContext):
    await state.update_data(catalog_name=message.text)
    await Form.next()
    await message.reply("Введите дату празднования (в формате YYYY-MM-DD) или пропустите:")


@dp.message_handler(state=Form.create_catalog_date)
async def create_catalog_date(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    data = await state.get_data()

    catalog_date = message.text if message.text else None
    cursor.execute(
        "INSERT INTO catalogs (user_id, catalog_name, celebration_date) VALUES (%s, %s, %s)",
        (user_id, data['catalog_name'], catalog_date)
    )
    conn.commit()
    await state.finish()
    await message.reply("Каталог создан!", reply_markup=main_menu)


# User Story 11: Share Wishlist with Unique ID
@dp.message_handler(lambda message: message.text == "📤 Поделиться списком")
async def share_wishlist_handler(message: types.Message):
    user_id = message.from_user.id
    cursor.execute("SELECT name, description, link FROM wishlist_items WHERE user_id = %s", (user_id,))
    wishlist = cursor.fetchall()

    if wishlist:
            unique_id = str(uuid.uuid4())
            wishlist_data = {
                unique_id: [{'name': item[0], 'description': item[1], 'link': item[2]} for item in wishlist]
            }
            with open(f"{unique_id}.json", "w") as f:
                json.dump(wishlist_data, f)
                await message.reply(f"Ссылка на ваш виш-лист: {unique_id}", reply_markup=main_menu)
    else:
        await message.reply("Ваш список желаний пуст.", reply_markup=main_menu)


# Start bot
async def main():
    try:
        await dp.start_polling(bot_v1)
    except Exception as e:
        logging.error(f"Error in main polling: {e}")

if __name__ == "__main__":
    asyncio.run(main())