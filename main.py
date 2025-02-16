from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from typing import Optional
from aiogram.filters.callback_data import CallbackData
import asyncio
import httpx
import logging
import datetime

API_TOKEN = ''
bot = Bot(token=API_TOKEN)
dp = Dispatcher()
logging.basicConfig(level=logging.DEBUG, filename="py_log.log", filemode="w")

class ServerMonitor:
    def __init__(self):
        self.monitoring_task = None

    async def get_status(self):
        try:
            r = httpx.get("https://status.epicgames.com/api/v2/status.json")
            status = r.json()["status"]["description"]
            if r.status_code != 200:
                logging.error("Unable to retrieve server status")
                return "Error: Unable to retrieve server status."
            return status
        except Exception as e:
            logging.error(f"Error: {e}")
            return "An error occurred while checking the server status."

    async def start_monitoring(self, message: Message):
        if self.monitoring_task is None or self.monitoring_task.done():
            self.monitoring_task = asyncio.create_task(self.monitor_status(message))
            await message.answer("Monitoring started. Server status will be sent to you every 5 minutes.")
        else:
            await message.answer("Monitoring task is already running.")

    async def stop_monitoring(self, message: Message):
        if self.monitoring_task is not None and not self.monitoring_task.done():
            self.monitoring_task.cancel()
            await message.answer("Monitoring stopped.")
        else:
            await message.answer("Monitoring task is not running.")

    async def monitor_status(self, message: Message):
        while self.monitoring_task is not None and not self.monitoring_task.done():
            status = await self.get_status()
            await message.answer(f"Server status: {status}")
            logging.debug(f"Status sent at {datetime.datetime.now()}")
            await asyncio.sleep(300)  # Sleep for 5 minutes

monitor = ServerMonitor()


class MonitorCallback(CallbackData, prefix="monitor"):
    action: str

@dp.message(CommandStart())
async def start_command(message: Message):
    kb = [
        [
            InlineKeyboardButton(text="Start Monitoring", callback_data=MonitorCallback(action="start").pack()),
            InlineKeyboardButton(text="Stop Monitoring", callback_data=MonitorCallback(action="stop").pack()),
            InlineKeyboardButton(text="Status", callback_data=MonitorCallback(action="status").pack())
        ]
    ]
    markup = InlineKeyboardMarkup(inline_keyboard=kb)
    await message.answer("Hello! Please select an option:", reply_markup=markup)

@dp.callback_query(MonitorCallback.filter())
async def handle_callback(callback: CallbackQuery, callback_data: MonitorCallback):
    action = callback_data.action

    if action == "start":
        await monitor.start_monitoring(callback.message)
    elif action == "stop":
        await monitor.stop_monitoring(callback.message)
    elif action == "status":
        status = await monitor.get_status()
        await callback.message.answer(f"Server status: {status}")

    await callback.answer()

@dp.message(Command("startmon"))
async def startmon(message: Message):
    await monitor.start_monitoring(message)

@dp.message(Command("stopmon"))
async def stopmon(message: Message):
    await monitor.stop_monitoring(message)

@dp.message(Command("status"))
async def status(message: Message):
    status = await monitor.get_status()
    await message.answer(f"Server status: {status}")

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
