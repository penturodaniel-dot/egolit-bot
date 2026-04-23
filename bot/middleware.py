"""
ChatPersistenceMiddleware — saves every incoming user message to
chat_sessions + chat_messages so admin CRM has full history.
"""
from __future__ import annotations
import logging
from typing import Callable, Awaitable, Any

from aiogram import BaseMiddleware
from aiogram.types import Message, TelegramObject

from db.chat import upsert_session, save_message

logger = logging.getLogger(__name__)

# user_ids that belong to manager/bot — don't persist their own messages
_SKIP_USER_IDS: set[int] = set()


class ChatPersistenceMiddleware(BaseMiddleware):
    """Persists every incoming user message to the chat DB."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        if isinstance(event, Message) and event.from_user:
            user = event.from_user
            if user.id not in _SKIP_USER_IDS and not user.is_bot:
                try:
                    await upsert_session(
                        user_id=user.id,
                        username=user.username,
                        first_name=user.first_name,
                        last_name=user.last_name,
                    )
                    # Determine message type
                    msg_type = "text"
                    if event.photo:
                        msg_type = "photo"
                    elif event.document:
                        msg_type = "document"
                    elif event.sticker:
                        msg_type = "sticker"
                    elif event.voice:
                        msg_type = "voice"
                    elif event.video:
                        msg_type = "video"

                    content = event.text or event.caption or f"[{msg_type}]"

                    await save_message(
                        user_id=user.id,
                        direction="in",
                        content=content,
                        msg_type=msg_type,
                        tg_msg_id=event.message_id,
                    )
                except Exception as e:
                    logger.warning(f"ChatPersistenceMiddleware error: {e}")

        return await handler(event, data)
