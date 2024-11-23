import time
import logging
from fpdf import FPDF
import os
import asyncio
import tempfile

from aiofiles import tempfile as aio_tempfile
from aiogram import Bot, Dispatcher, types
from aiogram.contrib.middlewares.logging import LoggingMiddleware
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, InputFile
import psycopg2
from psycopg2 import sql

logging.basicConfig(level=logging.INFO)

DATABASE_URL = os.environ.get("DATABASE_URL") or "postgresql://postgres:postgresd@localhost:5432/test"
conn = psycopg2.connect(DATABASE_URL)
cursor = conn.cursor()

# Инициализация базы данных
cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        user_id BIGINT PRIMARY KEY,
        username VARCHAR(100),
        registration_date DATE DEFAULT CURRENT_DATE
    );

    CREATE TABLE IF NOT EXISTS gifts (
        gift_id SERIAL PRIMARY KEY,
        user_id BIGINT REFERENCES users(user_id),
        title VARCHAR(70) NOT NULL,
        description TEXT,
        link TEXT
    );
''')
conn.commit()

TOKEN = ""
bot = Bot(token=TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)
dp.middleware.setup(LoggingMiddleware())

# Main menu keyboard
main_menu = ReplyKeyboardMarkup(resize_keyboard=True)
main_menu.add(KeyboardButton("📜 Просмотреть подарки"), KeyboardButton("➕ Добавить подарок"))
main_menu.add(KeyboardButton("🗑 Удалить подарок"), KeyboardButton("✏️ Изменить подарок"))
main_menu.add(KeyboardButton("📤 Поделиться виш-листом"))


class Form(StatesGroup):
    add_item_name = State()
    add_item_description = State()
    add_item_link = State()
    edit_item_select = State()
    edit_item_field = State()
    edit_item_value = State()
    delete_item_select = State()  # New state for selecting gift to delete


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
    cursor.execute("SELECT title, description, link FROM gifts WHERE user_id = %s", (user_id,))
    items = cursor.fetchall()

    if items:
        response = "🎁 Ваш список желаний:\n\n"
        for title, description, link in items[:20]:
            response += f"🔹 {title} - {description or 'Без описания'}\n{link}\n\n"
    else:
        response = "Ваш список желаний пуст."

    await message.reply(response, reply_markup=main_menu)


@dp.message_handler(lambda message: message.text == "➕ Добавить подарок")
async def add_item_name(message: types.Message):
    await Form.add_item_name.set()
    await message.reply("Введите название подарка (не менее 3 символов):")


@dp.message_handler(state=Form.add_item_name)
async def add_item_description(message: types.Message, state: FSMContext):
    name = message.text.strip()
    if len(name) < 3:
        await message.reply("Название подарка должно содержать не менее 3 символов.")
        return

    await state.update_data(name=name)
    await Form.add_item_description.set()
    await message.reply("Введите описание подарка:")


@dp.message_handler(state=Form.add_item_description)
async def add_item_link(message: types.Message, state: FSMContext):
    description = message.text.strip()
    await state.update_data(description=description)
    await Form.add_item_link.set()
    await message.reply("Введите ссылку на подарок (или пропустите):")


@dp.message_handler(state=Form.add_item_link)
async def add_gift(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    link = message.text.strip()
    data = await state.get_data()

    try:
        cursor.execute(
            "INSERT INTO gifts (user_id, title, description, link) VALUES (%s, %s, %s, %s)",
            (user_id, data['name'], data.get('description', ''), link)
        )
        conn.commit()
        await message.reply("Подарок добавлен в ваш список желаний!", reply_markup=main_menu)
    except Exception as e:
        logging.error(f"Error inserting gift: {e}")
        await message.reply("Произошла ошибка при добавлении подарка. Пожалуйста, попробуйте снова.")
    finally:
        await state.finish()


# Изменение подарка
@dp.message_handler(lambda message: message.text == "✏️ Изменить подарок")
async def edit_gift_start(message: types.Message):
    user_id = message.from_user.id
    cursor.execute("SELECT gift_id, title FROM gifts WHERE user_id = %s", (user_id,))
    items = cursor.fetchall()

    if items:
        response = "🔄 Выберите номер подарка для изменения:\n"
        for gift_id, title in items:
            response += f"{gift_id}. {title}\n"
        await Form.edit_item_select.set()
        await message.reply(response)
    else:
        await message.reply("Ваш список желаний пуст.", reply_markup=main_menu)


@dp.message_handler(state=Form.edit_item_select)
async def select_field_to_edit(message: types.Message, state: FSMContext):
    gift_id = message.text.strip()
    if not gift_id.isdigit():
        await message.reply("Пожалуйста, введите корректный номер подарка.")
        return

    await state.update_data(gift_id=gift_id)
    await Form.edit_item_field.set()
    await message.reply("Что вы хотите изменить? (название, описание, ссылка)")


@dp.message_handler(state=Form.edit_item_field)
async def edit_field_value(message: types.Message, state: FSMContext):
    field = message.text.lower().strip()
    if field not in ["название", "описание", "ссылка"]:
        await message.reply("Пожалуйста, выберите одно из полей: название, описание, ссылка.")
        return

    await state.update_data(field=field)
    await Form.edit_item_value.set()
    await message.reply("Введите новое значение для выбранного поля:")


@dp.message_handler(state=Form.edit_item_value)
async def save_edited_gift(message: types.Message, state: FSMContext):
    data = await state.get_data()
    field_map = {"название": "title", "описание": "description", "ссылка": "link"}
    field = field_map[data['field']]
    value = message.text.strip()

    try:
        cursor.execute(
            sql.SQL("UPDATE gifts SET {} = %s WHERE gift_id = %s").format(sql.Identifier(field)),
            (value, data['gift_id']),
        )
        conn.commit()
    except Exception as e:
        logging.error(f"Error updating gift: {e}")

    await message.reply("🎉 Изменения успешно сохранены!", reply_markup=main_menu)
    await state.finish()


# Удаление подарка
@dp.message_handler(lambda message: message.text == "🗑 Удалить подарок")
async def delete_gift_start(message: types.Message):
    user_id = message.from_user.id
    cursor.execute("SELECT gift_id, title FROM gifts WHERE user_id = %s", (user_id,))
    items = cursor.fetchall()

    if items:
        response = "🗑 Выберите номер подарка для удаления:\n"
        for gift_id, title in items:
            response += f"{gift_id}. {title}\n"
        await Form.delete_item_select.set()
        await message.reply(response)
    else:
        await message.reply("Ваш список желаний пуст.", reply_markup=main_menu)


@dp.message_handler(state=Form.delete_item_select)
async def delete_gift_confirm(message: types.Message, state: FSMContext):
    gift_id = message.text.strip()
    if not gift_id.isdigit():
        await message.reply("Пожалуйста, введите корректный номер подарка.")
        return

    cursor.execute("SELECT title FROM gifts WHERE gift_id = %s AND user_id = %s", (gift_id, message.from_user.id))
    gift = cursor.fetchone()
    if gift:
        title = gift[0]
        try:
            cursor.execute("DELETE FROM gifts WHERE gift_id = %s AND user_id = %s", (gift_id, message.from_user.id))
            conn.commit()
            await message.reply(f"🎉 Подарок '{title}' был успешно удален из вашего списка желаний!",
                                reply_markup=main_menu)
        except Exception as e:
            logging.error(f"Error deleting gift: {e}")
            await message.reply("Произошла ошибка при удалении подарка. Пожалуйста, попробуйте снова.")
    else:
        await message.reply("Подарок с указанным номером не найден.")

    await state.finish()

def create_html_file(data):
    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>Wishlist</title>
        <style>
            body {{ font-family: Arial, sans-serif; }}
            h1 {{ color: #333; }}
            .gift {{ margin-bottom: 15px; }}
        </style>
    </head>
    <body>
        <h1>Ваш список подарков 🎁</h1>
        {data}
    </body>
    </html>
    """
    with tempfile.NamedTemporaryFile(delete=False, suffix=".html") as tmp_file:
        tmp_file.write(html_content.encode('utf-8'))
        return tmp_file.name


@dp.message_handler(lambda message: message.text == "📤 Поделиться виш-листом")
async def export_wishlist_handler(message: types.Message):
    user_id = message.from_user.id
    cursor.execute("SELECT title, description, link FROM gifts WHERE user_id = %s", (user_id,))
    gifts = cursor.fetchall()

    if not gifts:
        await message.reply("Ваш список желаний пуст. Нечего экспортировать.")
        return

    gift_list_html = ""
    for title, description, link in gifts:
        gift_list_html += f"<div class='gift'><h3>{title}</h3><p>{description or 'Без описания'}</p><a href='{link}' target='_blank'>{link or 'Нет ссылки'}</a></div>"

    file_path = create_html_file(gift_list_html)

    await message.reply_document(InputFile(file_path), caption="Ваш список подарков в формате HTML 🎉")
    os.remove(file_path)


# Запуск бота
async def main():
    try:
        await dp.start_polling(bot)
    except Exception as e:
        logging.error(f"Error in main polling: {e}")


# Запуск бота
if __name__ == '__main__':
    from aiogram import executor

    executor.start_polling(dp, skip_updates=True)
