import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from config import settings
from db.connection import get_pool, close_pool
from db.categories_cache import load_categories
from db.human_sessions import init_human_sessions
from db.settings import init_settings
from db.menu_buttons import init_menu_buttons
from db.chat import init_chat_tables
from scrapers.karabas import init_karabas_events
from bot.menu_cache import reload_buttons
from bot.middleware import ChatPersistenceMiddleware
from bot.handlers import start, search, lead
from bot.handlers import human, dynamic_menu

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

bot = Bot(token=settings.BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())

# Middleware — persists every incoming message to chat DB
dp.message.middleware(ChatPersistenceMiddleware())

# Реєструємо роутери
# human.router — ПЕРШИМ, щоб перехоплювати повідомлення юзерів у human-mode
# та обробляти reply від менеджера до того, як search/lead роутери їх побачать
dp.include_router(human.router)         # 1. перехоплює human-mode повідомлення
dp.include_router(start.router)         # 2. /start команда
dp.include_router(lead.router)          # 3. lead flow стани
dp.include_router(dynamic_menu.router)  # 4. кнопки меню (до search!)
dp.include_router(search.router)        # 5. вільний текст — останній


async def on_startup():
    logger.info("Connecting to database...")
    await get_pool()
    logger.info("Database connected.")
    await load_categories()
    logger.info("Categories loaded.")
    await init_human_sessions()
    logger.info("Human sessions table ready.")
    await init_settings()
    logger.info("Settings table ready.")
    await init_menu_buttons()
    logger.info("Menu buttons table ready.")
    await reload_buttons()
    logger.info("Menu buttons loaded.")
    await init_chat_tables()
    logger.info("Chat tables ready.")
    await init_karabas_events()
    logger.info("Karabas events table ready.")
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
