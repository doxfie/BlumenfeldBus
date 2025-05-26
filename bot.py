import os
import asyncio
import logging
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import pytz
import html

# Config
TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    raise RuntimeError("BOT_TOKEN не найден!")

OMSK_TZ = pytz.timezone('Asia/Omsk')

# Водители
DRIVERS = {
    'азово': '+7 913 974 94 29',
    'пришиб': '+7 904 322 27 37'
}

# Расписания
SCHEDULE = {
    "from_omsk": {
        "default": [
            ("9:00", "Омск → Цветнополье", 'пришиб'),
            ("10:30", "Омск → Цветнополье", 'азово'),
            ("14:30", "Омск → Цветнополье", 'пришиб'),
            ("17:00", "Омск → Цветнополье", 'азово'),
            ("19:00", "Омск → Цветнополье", 'пришиб'),
        ],
        "wednesday": [
            ("10:30", "Омск → Цветнополье", 'азово'),
            ("17:00", "Омск → Цветнополье", 'азово'),
        ],
    },
    "from_tsvetnopolye": {
        "default": [
            ("6:30", "Цветнополье → Омск", 'пришиб'),
            ("7:15", "Цветнополье → Омск", 'азово'),
            ("11:00", "Цветнополье → Омск", 'пришиб'),
            ("13:30", "Цветнополье → Омск", 'азово'),
            ("16:30", "Цветнополье → Омск", 'пришиб'),
        ],
        "weekend": [
            ("6:30", "Цветнополье → Омск", 'пришиб'),
            ("8:30", "Цветнополье → Омск", 'азово'),
            ("11:00", "Цветнополье → Омск", 'пришиб'),
            ("13:30", "Цветнополье → Омск", 'азово'),
            ("16:30", "Цветнополье → Омск", 'пришиб'),
        ],
        "wednesday": [
            ("7:15", "Цветнополье → Омск", 'азово'),
            ("13:30", "Цветнополье → Омск", 'азово'),
        ],
    }
}

def get_schedule(direction: str, weekday: int) -> list[tuple[str, str, str]]:
    if weekday == 2:
        return SCHEDULE[direction].get("wednesday", SCHEDULE[direction]["default"])
    elif weekday in [5, 6]:
        return SCHEDULE[direction].get("weekend", SCHEDULE[direction]["default"])
    return SCHEDULE[direction]["default"]

def format_schedule(today_schedule, now):
    past, upcoming = [], []
    for t, label, driver in today_schedule:
        h, m = map(int, t.split(':'))
        sched_time = now.replace(hour=h, minute=m, second=0, microsecond=0)
        (past if sched_time < now else upcoming).append((t, label, driver))
    return past, upcoming

def get_time_to_next(upcoming, now):
    if not upcoming:
        return None
    h, m = map(int, upcoming[0][0].split(':'))
    next_time = now.replace(hour=h, minute=m, second=0, microsecond=0)
    return (next_time - now) if next_time > now else (next_time + timedelta(days=1) - now)

def format_russian_date(now):
    days = ['Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота', 'Воскресенье']
    months = ['января', 'февраля', 'марта', 'апреля', 'мая', 'июня', 'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря']
    return f"{days[now.weekday()]}, {now.day} {months[now.month - 1]} {now.year}, {now.strftime('%H:%M')}"

# Telegram bot
bot = Bot(token=TOKEN)
dp = Dispatcher()

def get_main_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Омск → Цветнополье", callback_data="from_omsk")],
        [InlineKeyboardButton(text="Цветнополье → Омск", callback_data="from_tsvetnopolye")]
    ])

def get_back_keyboard(direction):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_menu")],
        [InlineKeyboardButton(text="🔄 Обновить", callback_data=f"refresh_{direction}")]
    ])

@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer("Выберите направление:", reply_markup=get_main_keyboard())

@dp.callback_query(F.data == "back_to_menu")
async def back_menu(callback: types.CallbackQuery):
    await callback.message.edit_text("Выберите направление:", reply_markup=get_main_keyboard())

@dp.callback_query(F.data.in_(["from_omsk", "from_tsvetnopolye", "refresh_from_omsk", "refresh_from_tsvetnopolye"]))
async def show_schedule(callback: types.CallbackQuery):
    now = datetime.now(OMSK_TZ)
    weekday = now.weekday()
    direction = callback.data.replace("refresh_", "")
    today_schedule = get_schedule(direction, weekday)
    past, upcoming = format_schedule(today_schedule, now)
    day_str = format_russian_date(now)
    dir_text = "Из Омска" if direction == "from_omsk" else "Из Цветнополья"

    msg = f"<b>{html.escape(dir_text)} — расписание на сегодня</b>\n<i>({html.escape(day_str)})</i>\n\n"

    if past:
        msg += "❌ <b>Уже прошли:</b>\n"
        for t, l, driver in past:
            msg += f"<s><b>{html.escape(t)} — {html.escape(l)}</b></s> (водитель: {html.escape(DRIVERS[driver])})\n"

    if upcoming:
        msg += "\n✅ <b>Ещё будут:</b>\n"
        for i, (t, l, driver) in enumerate(upcoming):
            t_fmt = f"<b>{html.escape(t)} — {html.escape(l)}</b>" if i == 0 else f"{html.escape(t)} — {html.escape(l)}"
            msg += f"{t_fmt} (водитель: {html.escape(DRIVERS[driver])})\n"
        delta = get_time_to_next(upcoming, now)
        if delta:
            h, m = divmod(delta.seconds // 60, 60)
            msg += f"\n⏰ <b>До ближайшего рейса:</b> {h} ч {m} мин"
    else:
        msg += "\nСегодня рейсов больше нет."

    if weekday == 2:
        msg += "\n\n⚠️ <b>По средам только 2 рейса Омск → Цветнополье и 2 рейса Цветнополье → Омск!</b>"

    await callback.message.edit_text(msg, reply_markup=get_back_keyboard(direction), parse_mode="HTML")

# Запуск
if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)
    asyncio.run(dp.start_polling(bot))
