import asyncio
import json
from datetime import datetime
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from pyrogram import Client
from pyrogram.errors import FloodWait

# ==================== НАСТРОЙКИ ====================
# Управляющий бот (получите у @BotFather)
BOT_TOKEN = "7588249087:AAG1kbYmKf0RkX7cpO1fT5K1Fb9UDs5QM-4"
ADMIN_ID = 5637504709  # Ваш Telegram ID

# Userbot credentials (получите на https://my.telegram.org)
API_ID = 37985180
API_HASH = "30fb5238eabd3685246c60c037e68340"
SESSION_NAME = "auto_sender"

# Файл для хранения задач
CONFIG_FILE = "tasks.json"

# ==================== AIOGRAM (Управляющий бот) ====================
class TaskStates(StatesGroup):
    waiting_chat_id = State()
    waiting_message = State()
    waiting_interval = State()

bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# Хранилище активных задач
active_tasks = {}

def load_tasks():
    """Загрузка задач из файла"""
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_tasks(tasks):
    """Сохранение задач в файл"""
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(tasks, f, ensure_ascii=False, indent=2)

@dp.message(Command("start"))
async def cmd_start(message: Message):
    """Команда /start"""
    if message.from_user.id != ADMIN_ID:
        await message.answer("⛔ У вас нет доступа к этому боту")
        return
    
    await message.answer(
        "🤖 <b>Бот для автоматической отправки сообщений</b>\n\n"
        "📋 <b>Команды:</b>\n"
        "/add - Добавить новую задачу\n"
        "/list - Список активных задач\n"
        "/stop - Остановить задачу\n"
        "/help - Помощь\n\n"
        "⚠️ <b>Внимание:</b> Используйте ответственно!",
        parse_mode="HTML"
    )

@dp.message(Command("add"))
async def cmd_add(message: Message, state: FSMContext):
    """Начало создания задачи"""
    if message.from_user.id != ADMIN_ID:
        return
    
    await message.answer(
        "📝 <b>Создание новой задачи</b>\n\n"
        "Отправьте ID чата или username:\n"
        "• Для личных чатов: ID пользователя\n"
        "• Для групп: -100xxxxxxxxxx\n"
        "• Для каналов: @channel_name или ID\n\n"
        "Для отмены: /cancel",
        parse_mode="HTML"
    )
    await state.set_state(TaskStates.waiting_chat_id)

@dp.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext):
    """Отмена операции"""
    await state.clear()
    await message.answer("❌ Операция отменена")

@dp.message(TaskStates.waiting_chat_id)
async def process_chat_id(message: Message, state: FSMContext):
    """Получение ID чата"""
    chat_id = message.text.strip()
    
    # Проверка формата
    if not chat_id.startswith('@') and not chat_id.lstrip('-').isdigit():
        await message.answer("⚠️ Неверный формат. Попробуйте снова или /cancel")
        return
    
    await state.update_data(chat_id=chat_id)
    await message.answer("✏️ Теперь отправьте текст сообщения:")
    await state.set_state(TaskStates.waiting_message)

@dp.message(TaskStates.waiting_message)
async def process_message(message: Message, state: FSMContext):
    """Получение текста сообщения"""
    text = message.text
    
    if len(text) > 4096:
        await message.answer("⚠️ Сообщение слишком длинное (макс. 4096 символов)")
        return
    
    await state.update_data(text=text)
    await message.answer(
        "⏱ Укажите интервал в секундах:\n"
        "Например: 60 (раз в минуту), 3600 (раз в час)\n\n"
        "⚠️ Минимум 30 секунд, чтобы избежать блокировки"
    )
    await state.set_state(TaskStates.waiting_interval)

@dp.message(TaskStates.waiting_interval)
async def process_interval(message: Message, state: FSMContext):
    """Получение интервала и создание задачи"""
    try:
        interval = int(message.text)
        if interval < 5:
            await message.answer("⚠️ Интервал должен быть минимум 30 секунд")
            return
    except ValueError:
        await message.answer("⚠️ Введите число (количество секунд)")
        return
    
    data = await state.get_data()
    task_id = f"task_{len(active_tasks) + 1}"
    
    task_config = {
        "chat_id": data["chat_id"],
        "text": data["text"],
        "interval": interval,
        "created_at": datetime.now().isoformat()
    }
    
    # Сохранение
    tasks = load_tasks()
    tasks[task_id] = task_config
    save_tasks(tasks)
    
    await message.answer(
        f"✅ <b>Задача создана!</b>\n\n"
        f"🆔 ID: <code>{task_id}</code>\n"
        f"💬 Чат: <code>{data['chat_id']}</code>\n"
        f"📝 Сообщение: {data['text'][:50]}...\n"
        f"⏱ Интервал: {interval} сек\n\n"
        f"Задача будет запущена после перезапуска userbot",
        parse_mode="HTML"
    )
    await state.clear()

@dp.message(Command("list"))
async def cmd_list(message: Message):
    """Список задач"""
    if message.from_user.id != ADMIN_ID:
        return
    
    tasks = load_tasks()
    
    if not tasks:
        await message.answer("📭 Нет активных задач")
        return
    
    text = "📋 <b>Активные задачи:</b>\n\n"
    for task_id, config in tasks.items():
        status = "🟢 Запущена" if task_id in active_tasks else "🔴 Остановлена"
        text += (
            f"<b>{task_id}</b> {status}\n"
            f"💬 Чат: <code>{config['chat_id']}</code>\n"
            f"⏱ Интервал: {config['interval']} сек\n"
            f"📝 Текст: {config['text'][:50]}...\n\n"
        )
    
    await message.answer(text, parse_mode="HTML")

@dp.message(Command("stop"))
async def cmd_stop(message: Message):
    """Остановка задачи"""
    if message.from_user.id != ADMIN_ID:
        return
    
    tasks = load_tasks()
    if not tasks:
        await message.answer("📭 Нет задач для остановки")
        return
    
    text = "🛑 Введите ID задачи для остановки:\n\n"
    for task_id in tasks.keys():
        status = "🟢" if task_id in active_tasks else "🔴"
        text += f"{status} <code>{task_id}</code>\n"
    
    await message.answer(text, parse_mode="HTML")

@dp.message(F.text.startswith("task_"))
async def process_stop(message: Message):
    """Обработка остановки задачи"""
    if message.from_user.id != ADMIN_ID:
        return
    
    task_id = message.text.strip()
    tasks = load_tasks()
    
    if task_id not in tasks:
        await message.answer("⚠️ Задача не найдена")
        return
    
    # Удаление из файла
    del tasks[task_id]
    save_tasks(tasks)
    
    # Остановка задачи
    if task_id in active_tasks:
        active_tasks[task_id].cancel()
        del active_tasks[task_id]
    
    await message.answer(f"✅ Задача {task_id} остановлена и удалена")

@dp.message(Command("help"))
async def cmd_help(message: Message):
    """Помощь"""
    await message.answer(
        "ℹ️ <b>Инструкция:</b>\n\n"
        "1️⃣ Используйте /add для создания задачи\n"
        "2️⃣ Укажите ID чата (можно получить через @userinfobot)\n"
        "3️⃣ Напишите текст сообщения\n"
        "4️⃣ Установите интервал (мин. 30 сек)\n\n"
        "⚠️ <b>Важно:</b>\n"
        "• Не злоупотребляйте - можно получить бан\n"
        "• Минимальный интервал - 30 секунд\n"
        "• Userbot должен быть запущен отдельно\n\n"
        "🔧 Для запуска userbot: python script.py",
        parse_mode="HTML"
    )

# ==================== PYROGRAM (Userbot) ====================
app = Client(SESSION_NAME, api_id=API_ID, api_hash=API_HASH)

async def send_periodic_message(task_id: str, chat_id: str, text: str, interval: int):
    """Периодическая отправка сообщений"""
    while True:
        try:
            await asyncio.sleep(interval)
            await app.send_message(chat_id, text)
            print(f"[{task_id}] Сообщение отправлено в {chat_id}")
        except FloodWait as e:
            print(f"[{task_id}] FloodWait {e.value} секунд")
            await asyncio.sleep(e.value)
        except Exception as e:
            print(f"[{task_id}] Ошибка: {e}")
            await asyncio.sleep(60)

async def start_userbot():
    """Запуск userbot и задач"""
    await app.start()
    print("✅ Userbot запущен")
    
    # Загрузка и запуск задач
    tasks = load_tasks()
    for task_id, config in tasks.items():
        task = asyncio.create_task(
            send_periodic_message(
                task_id,
                config["chat_id"],
                config["text"],
                config["interval"]
            )
        )
        active_tasks[task_id] = task
        print(f"📌 Запущена задача: {task_id}")
    
    # Держим userbot активным
    await asyncio.Event().wait()

# ==================== MAIN ====================
async def main():
    """Главная функция"""
    print("🚀 Запуск системы...")
    
    # Запуск управляющего бота и userbot параллельно
    await asyncio.gather(
        dp.start_polling(bot),
        start_userbot()
    )

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⛔ Остановка...")
