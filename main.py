from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.filters.callback_data import CallbackData
import asyncio
import httpx
import logging
import datetime
import sqlite3

API_TOKEN = ''
bot = Bot(token=API_TOKEN)
dp = Dispatcher()
logging.basicConfig(level=logging.DEBUG, filename="py_log.log", filemode="w")

with sqlite3.connect('users.db') as db:
    c = db.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS users (
        userid BIGINTEGER PRIMARY KEY,
        username TEXT,
        errors BIGINTEGER,
        last_error TEXT,
        last_status TEXT
    )""")
    db.commit()
    logging.debug("Table 'users' initialized if it didn't exist.")


class ServerMonitor:
    def __init__(self):
        self.monitoring_task = None

    async def get_status(self, message: Message, userid: int):
        try:
            r = httpx.get("https://status.epicgames.com/api/v2/status.json")
            if r.status_code != 200:
                logging.error("Unable to retrieve server status")
                return "Error: Unable to retrieve server status."

            status = r.json()["status"]["description"]

            logging.debug(f"Received status: {status}")

            c.execute("SELECT errors, last_status FROM users WHERE userid = ?", (userid,))
            user_data = c.fetchone()
            if user_data is None:
                await message.answer("User not found in the database.")
                return

            errors, last_status = user_data

            if status == "All Systems Operational":
                await message.answer(f"Alles in Ordnung: Server status: {status}")
            else:
                errors += 1
                last_error = f"{status} at {datetime.datetime.now()}"
                await message.answer(f"ERROR: Server status: {status}")

            try:
                c.execute("UPDATE users SET errors = ?, last_error = ?, last_status = ? WHERE userid = ?",
                           (errors, last_error if status != "All Systems Operational" else None, status, userid))
                db.commit()
                logging.info(f"Updated user {userid}: errors={errors}, last_status={status}")
            except sqlite3.Error as e:
                logging.error(f"Error updating user data: {e}")

            return status

        except Exception as e:
            logging.error(f"Error: {e}")
            return "An error occurred while checking the server status."

    async def start_monitoring(self, message: Message, userid: int):
        if self.monitoring_task is None or self.monitoring_task.done():
            self.monitoring_task = asyncio.create_task(self.monitor_status(message, userid))
            await message.answer("Monitoring started. Server status will be sent to you every 5 minutes.")
        else:
            await message.answer("Monitoring task is already running.")

    async def stop_monitoring(self, message: Message):
        if self.monitoring_task is not None and not self.monitoring_task.done():
            self.monitoring_task.cancel()
            await message.answer("Monitoring stopped.")
        else:
            await message.answer("Monitoring task is not running.")

    async def monitor_status(self, message: Message, userid: int):
        while self.monitoring_task is not None and not self.monitoring_task.done():
            await self.get_status(message, userid)
            await asyncio.sleep(300)


monitor = ServerMonitor()


class MonitorCallback(CallbackData, prefix="monitor"):
    action: str


@dp.message(CommandStart())
async def start_command(message: Message):
    userid = message.from_user.id
    username = message.from_user.username
    kb = [
        [
            InlineKeyboardButton(text="Start Monitoring", callback_data=MonitorCallback(action="start").pack()),
            InlineKeyboardButton(text="Stop Monitoring", callback_data=MonitorCallback(action="stop").pack()),
            InlineKeyboardButton(text="Status", callback_data=MonitorCallback(action="status").pack())
        ]
    ]
    markup = InlineKeyboardMarkup(inline_keyboard=kb)
    await message.answer("Hello! Please select an option:", reply_markup=markup)
    await add_user(userid, username)


@dp.callback_query(MonitorCallback.filter())
async def handle_callback(callback: CallbackQuery, callback_data: MonitorCallback):
    action = callback_data.action
    userid = callback.from_user.id

    if action == "start":
        await monitor.start_monitoring(callback.message, userid)
    elif action == "stop":
        await monitor.stop_monitoring(callback.message)
    elif action == "status":
        await monitor.get_status(callback.message, userid)

    await callback.answer()


@dp.message(Command("startmon"))
async def startmon(message: Message):
    userid = message.from_user.id
    await monitor.start_monitoring(message, userid)


@dp.message(Command("stopmon"))
async def stopmon(message: Message):
    await monitor.stop_monitoring(message)


@dp.message(Command("status"))
async def status(message: Message):
    userid = message.from_user.id
    await monitor.get_status(message, userid)


async def add_user(userid, username):
    try:
        c.execute("SELECT * FROM users WHERE userid = ?", (userid,))
        user = c.fetchone()
        if user is None:
            c.execute("INSERT INTO users (userid, username, errors, last_error, last_status) VALUES (?, ?, ?, ?, ?)",
                       (userid, username, 0, None, None))
            db.commit()
            logging.info(f"New user added: {userid} with username {username}")
        else:
            logging.warning(f"User {userid} already exists in the database")
    except sqlite3.Error as e:
        logging.error(f"Database error: {e}")


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
