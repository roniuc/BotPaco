import asyncio
import json
import os
import uuid
from datetime import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram import Client

# ======================
# 🔐 ЗАГРУЗКА НАСТРОЕК
# ======================

BOT_TOKEN = os.getenv("BOT_TOKEN")
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
PHONE_NUMBER = os.getenv("PHONE_NUMBER")
ADMIN_USER_ID = int(os.getenv("ADMIN_USER_ID"))

TASKS_FILE = "tasks.json"

# ======================
# 🧠 ЗАГРУЗКА/СОХРАНЕНИЕ ЗАДАЧ
# ======================

def load_tasks():
    if os.path.exists(TASKS_FILE):
        with open(TASKS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_tasks(tasks):
    with open(TASKS_FILE, "w", encoding="utf-8") as f:
        json.dump(tasks, f, ensure_ascii=False, indent=4)

# ======================
# 🤖 ИНИЦИАЛИЗАЦИЯ
# ======================

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
userbot = Client(
    "userbot_session",
    api_id=API_ID,
    api_hash=API_HASH,
    phone_number=PHONE_NUMBER
)

# Глобальные задачи (asyncio.Task)
running_tasks = {}  # task_id -> asyncio.Task

# ======================
# 📋 FSM для создания задачи
# ======================

class TaskCreation(StatesGroup):
    waiting_for_name = State()
    waiting_for_chat_id = State()
    waiting_for_message = State()
    waiting_for_interval = State()
    waiting_for_count = State()

# ======================
# 🔄 ФУНКЦИЯ ОТПРАВКИ (UserBot)
# ======================

async def send_messages_task(task_data: dict):
    task_id = task_data["task_id"]
    chat_id = task_data["chat_id"]
    message = task_data["message"]
    interval = task_data["interval_sec"]
    total = task_data["total_count"]
    sent = task_data.get("sent_count", 0)

    tasks = load_tasks()
    if sent >= total:
        tasks[task_id]["is_active"] = False
        save_tasks(tasks)
        return

    try:
        async with userbot:
            while sent < total:
                tasks = load_tasks()
                if not tasks.get(task_id, {}).get("is_active", False):
                    break

                await userbot.send_message(chat_id=chat_id, text=message)
                sent += 1

                # Обновляем счётчик
                tasks[task_id]["sent_count"] = sent
                save_tasks(tasks)

                if sent < total:
                    await asyncio.sleep(interval)
    except Exception as e:
        print(f"[Ошибка отправки в задаче {task_id}]: {e}")

# ======================
# 🎛️ УПРАВЛЕНИЕ ЗАДАЧАМИ
# ======================

async def update_running_task(task_id: str):
    # Отменяем старую задачу
    if task_id in running_tasks:
        running_tasks[task_id].cancel()
        del running_tasks[task_id]

    # Запускаем новую, если активна
    tasks = load_tasks()
    task = tasks.get(task_id)
    if task and task.get("is_active"):
        running_tasks[task_id] = asyncio.create_task(send_messages_task(task))

# ======================
# 🖥️ ИНТЕРФЕЙС БОТА
# ======================

def main_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Создать задачу", callback_data="create_task")],
        [InlineKeyboardButton(text="📋 Мои задачи", callback_data="list_tasks")]
    ])

def task_menu(task_id: str, is_active: bool):
    status = "🟢 Включить" if not is_active else "🔴 Отключить"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=status, callback_data=f"toggle_{task_id}")],
        [InlineKeyboardButton(text="🗑 Удалить", callback_data=f"delete_{task_id}")],
        [InlineKeyboardButton(text="⬅ Назад", callback_data="list_tasks")]
    ])

# ======================
# 📡 ОБРАБОТЧИКИ
# ======================

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    if message.from_user.id != ADMIN_USER_ID:
        await message.answer("❌ У вас нет доступа.")
        return
    await message.answer("🔷 Главное меню:", reply_markup=main_menu())

@dp.callback_query(F.data == "create_task")
async def create_task_start(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_USER_ID:
        return
    await callback.message.edit_text("✏ Введите название задачи:")
    await state.set_state(TaskCreation.waiting_for_name)

@dp.message(TaskCreation.waiting_for_name)
async def process_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("🆔 Введите ID чата (например, -1001234567890 или 123456789):")
    await state.set_state(TaskCreation.waiting_for_chat_id)

@dp.message(TaskCreation.waiting_for_chat_id)
async def process_chat_id(message: types.Message, state: FSMContext):
    try:
        chat_id = int(message.text)
    except ValueError:
        await message.answer("🚫 Неверный формат. Введите число.")
        return
    await state.update_data(chat_id=chat_id)
    await message.answer("💬 Введите текст сообщения:")
    await state.set_state(TaskCreation.waiting_for_message)

@dp.message(TaskCreation.waiting_for_message)
async def process_message(message: types.Message, state: FSMContext):
    await state.update_data(message=message.text)
    await message.answer("⏱ Введите интервал между сообщениями (в секундах, мин. 10):")
    await state.set_state(TaskCreation.waiting_for_interval)

@dp.message(TaskCreation.waiting_for_interval)
async def process_interval(message: types.Message, state: FSMContext):
    try:
        interval = int(message.text)
        if interval < 10:
            raise ValueError
    except ValueError:
        await message.answer("🚫 Минимум 10 секунд. Попробуйте снова:")
        return
    await state.update_data(interval=interval)
    await message.answer("🔢 Сколько сообщений отправить (1–1000)?")
    await state.set_state(TaskCreation.waiting_for_count)

@dp.message(TaskCreation.waiting_for_count)
async def process_count(message: types.Message, state: FSMContext):
    try:
        count = int(message.text)
        if not (1 <= count <= 1000):
            raise ValueError
    except ValueError:
        await message.answer("🚫 От 1 до 1000. Попробуйте снова:")
        return

    data = await state.get_data()
    task_id = str(len(load_tasks()) + 1)

    task = {
        "task_id": task_id,
        "name": data["name"],
        "chat_id": data["chat_id"],
        "message": data["message"],
        "interval_sec": data["interval"],
        "total_count": count,
        "sent_count": 0,
        "is_active": False,
        "created_at": datetime.now().isoformat()
    }

    tasks = load_tasks()
    tasks[task_id] = task
    save_tasks(tasks)

    await state.clear()
    await message.answer("✅ Задача создана! Вы можете включить её из списка.", reply_markup=main_menu())

# ======================
# 📋 СПИСОК ЗАДАЧ
# ======================

@dp.callback_query(F.data == "list_tasks")
async def list_tasks(callback: types.CallbackQuery):
    tasks = load_tasks()
    if not tasks:
        await callback.message.edit_text("📭 Нет задач.", reply_markup=main_menu())
        return

    text = "📋 Ваши задачи:\n\n"
    for tid, t in tasks.items():
        status = "🟢 Работает" if t["is_active"] else "⚪ Остановлена"
        sent = t["sent_count"]
        total = t["total_count"]
        text += f"ID: {tid} | {t['name']}\n"
        text += f"Статус: {status} | Отправлено: {sent}/{total}\n\n"

    kb = [[InlineKeyboardButton(text=f"ID {tid}", callback_data=f"view_{tid}")] for tid in tasks]
    kb.append([InlineKeyboardButton(text="⬅ Назад", callback_data="main_menu")])
    await callback.message.edit_text(text[:4096], reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@dp.callback_query(F.data == "main_menu")
async def back_to_menu(callback: types.CallbackQuery):
    await callback.message.edit_text("🔷 Главное меню:", reply_markup=main_menu())

@dp.callback_query(F.data.startswith("view_"))
async def view_task(callback: types.CallbackQuery):
    task_id = callback.data.split("_")[1]
    tasks = load_tasks()
    task = tasks.get(task_id)
    if not task:
        await callback.answer("Задача не найдена.")
        return

    text = (
        f"📌 Задача: {task['name']}\n"
        f"ID чата: {task['chat_id']}\n"
        f"Сообщение: {task['message'][:50]}...\n"
        f"Интервал: {task['interval_sec']} сек\n"
        f"Всего: {task['total_count']}, Отправлено: {task['sent_count']}\n"
        f"Статус: {'🟢 Активна' if task['is_active'] else '⚪ Остановлена'}"
    )
    await callback.message.edit_text(text, reply_markup=task_menu(task_id, task["is_active"]))

@dp.callback_query(F.data.startswith("toggle_"))
async def toggle_task(callback: types.CallbackQuery):
    task_id = callback.data.split("_")[1]
    tasks = load_tasks()
    if task_id not in tasks:
        await callback.answer("Задача не найдена.")
        return

    tasks[task_id]["is_active"] = not tasks[task_id]["is_active"]
    save_tasks(tasks)

    # Обновляем запущенную задачу
    await update_running_task(task_id)

    status = "включена" if tasks[task_id]["is_active"] else "отключена"
    await callback.answer(f"✅ Задача {status}!")
    await view_task(callback)

@dp.callback_query(F.data.startswith("delete_"))
async def delete_task(callback: types.CallbackQuery):
    task_id = callback.data.split("_")[1]
    tasks = load_tasks()
    if task_id in tasks:
        del tasks[task_id]
        save_tasks(tasks)
        # Отменяем задачу
        if task_id in running_tasks:
            running_tasks[task_id].cancel()
            del running_tasks[task_id]
        await callback.answer("🗑 Задача удалена.")
        await list_tasks(callback)
    else:
        await callback.answer("Задача не найдена.")

# ======================
# ▶️ ЗАПУСК
# ======================

async def main():
    # Загружаем и возобновляем активные задачи
    tasks = load_tasks()
    for tid, task in tasks.items():
        if task.get("is_active") and task.get("sent_count", 0) < task.get("total_count", 0):
            running_tasks[tid] = asyncio.create_task(send_messages_task(task))

    await dp.start_polling(bot)

if __name__ == "__main__":
    # Запускаем userbot в фоне (авторизация при первом запуске)
    userbot.start()
    print("✅ Userbot готов.")
    asyncio.run(main())
