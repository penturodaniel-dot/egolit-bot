import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from config import settings
from db.connection import get_pool, close_pool
from bot.handlers import start, search, lead

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

bot = Bot(token=settings.BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())

# Реєструємо роутери
dp.include_router(start.router)
dp.include_router(lead.router)
dp.include_router(search.router)   # search останній — ловить весь вільний текст


async def on_startup():
    logger.info("Connecting to database...")
    await get_pool()
    logger.info("Database connected.")
    me = await bot.get_me()
    logger.info(f"Bot started: @{me.username}")


async def on_shutdown():
    logger.info("Closing database pool...")
    await close_pool()
    logger.info("Bot stopped.")


async def main():
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    logger.info("Starting polling...")
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


if __name__ == "__main__":
    asyncio.run(main())
