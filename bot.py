import asyncio
import random
from contextlib import suppress

# === Aiogram (управляющий бот) ===
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import Message

# === Pyrogram (UserBot) ===
from pyrogram import Client

# === Настройки ===
OWNER_ID = 5637504709

BOT_TOKEN = "7588249087:AAG1kbYmKf0RkX7cpO1fT5K1Fb9UDs5QM-4"

API_ID = 32775998
API_HASH = "60a5003072ed6c8dedbf8d4efba97425"
SESSION_NAME = "paco"

# === Конфигурация рассылки ===
class SpamConfig:
    def __init__(self):
        self.chat: str | None = None
        self.messages: list[str] = ["Привет!", "Проверка связи", "Всё работает!"]
        self.interval: int = 60
        self.enabled: bool = False

config = SpamConfig()

# === Инициализация клиентов ===
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

userbot = Client(
    SESSION_NAME,
    api_id=API_ID,
    api_hash=API_HASH
)

# === Функция рассылки (работает в фоне) ===
async def spam_worker():
    while True:
        if config.enabled and config.chat:
            try:
                text = random.choice(config.messages)
                await userbot.send_message(chat_id=config.chat, text=text)
                print(f"✅ Отправлено в {config.chat}: {text}")
            except Exception as e:
                print(f"❌ Ошибка отправки: {e}")
        await asyncio.sleep(config.interval)

# === Фильтр: только владелец ===
def owner_only():
    def wrapper(message: Message):
        return message.from_user.id == OWNER_ID
    return wrapper

# === Команды бота ===
@dp.message(Command("start"))
async def cmd_start(message: Message):
    if message.from_user.id != OWNER_ID:
        return
    await message.answer(
        "✅ Привет! Я управляю UserBot'ом.\n\n"
        "Команды:\n"
        "/setchat @username — выбрать чат\n"
        "/addmsg текст — добавить сообщение\n"
        "/delmsg 1 — удалить по номеру\n"
        "/listmsgs — список сообщений\n"
        "/interval 30 — интервал (сек)\n"
        "/startspam — запустить\n"
        "/stopspam — остановить\n"
        "/status — текущие настройки"
    )

@dp.message(Command("setchat"))
async def cmd_setchat(message: Message):
    if message.from_user.id != OWNER_ID:
        return
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("❌ Использование: /setchat @username")
        return
    config.chat = parts[1].strip()
    await message.answer(f"✅ Чат установлен: {config.chat}")

@dp.message(Command("addmsg"))
async def cmd_addmsg(message: Message):
    if message.from_user.id != OWNER_ID:
        return
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("❌ Использование: /addmsg Текст сообщения")
        return
    config.messages.append(parts[1])
    await message.answer(f"✅ Сообщение добавлено. Всего: {len(config.messages)}")

@dp.message(Command("listmsgs"))
async def cmd_listmsgs(message: Message):
    if message.from_user.id != OWNER_ID:
        return
    if not config.messages:
        await message.answer("📭 Список сообщений пуст.")
        return
    text = "Сообщения:\n" + "\n".join(
        f"{i+1}. {msg}" for i, msg in enumerate(config.messages)
    )
    await message.answer(text)

@dp.message(Command("delmsg"))
async def cmd_delmsg(message: Message):
    if message.from_user.id != OWNER_ID:
        return
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("❌ Использование: /delmsg 1")
        return
    try:
        idx = int(parts[1]) - 1
        if 0 <= idx < len(config.messages):
            removed = config.messages.pop(idx)
            await message.answer(f"✅ Удалено: {removed}")
        else:
            await message.answer("❌ Неверный номер.")
    except ValueError:
        await message.answer("❌ Укажи номер цифрами.")

@dp.message(Command("interval"))
async def cmd_interval(message: Message):
    if message.from_user.id != OWNER_ID:
        return
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("❌ Использование: /interval 30")
        return
    try:
        sec = int(parts[1])
        if sec < 5:
            await message.answer("⚠️ Минимум 5 секунд!")
            return
        config.interval = sec
        await message.answer(f"⏱️ Интервал: {sec} сек")
    except ValueError:
        await message.answer("❌ Укажи число!")

@dp.message(Command("startspam"))
async def cmd_startspam(message: Message):
    if message.from_user.id != OWNER_ID:
        return
    if not config.chat:
        await message.answer("❌ Сначала задай чат: /setchat @username")
        return
    if not config.messages:
        await message.answer("❌ Добавь сообщения: /addmsg ...")
        return
    config.enabled = True
    await message.answer("🚀 Рассылка запущена!")

@dp.message(Command("stopspam"))
async def cmd_stopspam(message: Message):
    if message.from_user.id != OWNER_ID:
        return
    config.enabled = False
    await message.answer("⏹️ Рассылка остановлена.")

@dp.message(Command("status"))
async def cmd_status(message: Message):
    if message.from_user.id != OWNER_ID:
        return
    chat = config.chat or "не задан"
    msgs = len(config.messages)
    state = "✅ ВКЛ" if config.enabled else "🛑 ВЫКЛ"
    await message.answer(
        f"<b>Статус рассылки:</b>\n"
        f"Чат: {chat}\n"
        f"Сообщений: {msgs}\n"
        f"Интервал: {config.interval} сек\n"
        f"Состояние: {state}",
        parse_mode="HTML"
    )

# === Запуск всего ===
async def main():
    # Запускаем UserBot
    await userbot.start()
    print("✅ UserBot (Paco.session) запущен")

    # Запускаем фоновую рассылку
    asyncio.create_task(spam_worker())

    # Запускаем бота
    print("✅ Управляющий бот запущен. Отправь /start")
    await dp.start_polling(bot)

if __name__ == "__main__":
    with suppress(KeyboardInterrupt):
        asyncio.run(main())
