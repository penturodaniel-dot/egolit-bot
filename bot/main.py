import asyncio
import logging

import asyncio as _asyncio
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage


class LoggingBot(Bot):
    """Bot subclass that auto-saves every outgoing message to CRM chat history."""

    async def send_message(self, chat_id, text=None, **kwargs):
        result = await super().send_message(chat_id, text=text, **kwargs)
        if text and isinstance(chat_id, int):
            _asyncio.create_task(self._log_out(chat_id, text, "text", None, result.message_id))
        return result

    async def send_photo(self, chat_id, photo, caption=None, **kwargs):
        result = await super().send_photo(chat_id, photo, caption=caption, **kwargs)
        if isinstance(chat_id, int):
            # Extract URL from URLInputFile or plain string
            media_url = None
            if hasattr(photo, 'url'):
                media_url = photo.url
            elif isinstance(photo, str) and photo.startswith('http'):
                media_url = photo
            _asyncio.create_task(
                self._log_out(chat_id, caption or '', "photo", media_url, result.message_id)
            )
        return result

    @staticmethod
    async def _log_out(user_id: int, content: str, msg_type: str,
                       media_url, tg_msg_id: int):
        try:
            from db.chat import save_outgoing_message
            await save_outgoing_message(
                user_id, content, msg_type=msg_type,
                media_url=media_url, tg_msg_id=tg_msg_id,
            )
        except Exception:
            pass

from config import settings
from db.connection import get_pool, close_pool
from db.categories_cache import load_categories
from db.human_sessions import init_human_sessions
from db.settings import init_settings
from db.menu_buttons import init_menu_buttons
from db.chat import init_chat_tables
from db.content import init_content_tables
from scrapers.egolist import init_egolist_products
from scrapers.egolist_events import init_egolist_events
from bot.menu_cache import reload_buttons
from bot.middleware import ChatPersistenceMiddleware
from bot.handlers import start, search, lead
from bot.handlers import human, dynamic_menu

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

bot = LoggingBot(token=settings.BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
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
    await init_content_tables()
    logger.info("Content tables ready.")
    await init_egolist_events()
    logger.info("Egolist events table ready.")
    await init_egolist_products()
    logger.info("Egolist products table ready.")
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
