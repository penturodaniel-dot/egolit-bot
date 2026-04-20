"""
Human-mode handlers:
  - IsHumanMode filter  — intercepts all user text when in human mode
  - forward_to_manager  — sends user message to manager's Telegram chat
  - manager_reply       — routes manager's Telegram reply back to user
  - /endchat            — user ends the session
  - /endchat <user_id>  — manager ends a session from their Telegram chat
  - activate_human_mode — called when user requests live chat
"""

import logging
from aiogram import Router, F, Bot
from aiogram.filters import BaseFilter, Command
from aiogram.types import Message

from config import settings
from db.human_sessions import (
    is_human_mode,
    start_human_session,
    end_human_session,
    reply_map,
)
from bot.keyboards import main_menu_keyboard

logger = logging.getLogger(__name__)
router = Router()


# ── Filters ───────────────────────────────────────────────────────────────

class IsHumanMode(BaseFilter):
    """True if this user currently has an active human session."""
    async def __call__(self, message: Message) -> bool:
        if not message.from_user:
            return False
        return await is_human_mode(message.from_user.id)


class IsManagerChat(BaseFilter):
    """True if the message comes from the configured manager Telegram chat."""
    async def __call__(self, message: Message) -> bool:
        mgr = settings.MANAGER_TELEGRAM_ID
        return bool(mgr) and message.chat.id == mgr


# ── Helpers ───────────────────────────────────────────────────────────────

async def activate_human_mode(chat_id: int, user, bot: Bot) -> None:
    """
    Switch user to human mode and notify manager.
    chat_id — the user's private chat with the bot.
    user    — aiogram User object (message.from_user or callback.from_user).
    """
    await start_human_session(user.id, user.username, user.first_name)

    await bot.send_message(
        chat_id,
        "💬 <b>Підключаємо менеджера...</b>\n\n"
        "Пиши — менеджер відповість найближчим часом.\n"
        "Щоб завершити чат, надішли /endchat",
    )

    mgr_id = settings.MANAGER_TELEGRAM_ID
    if not mgr_id:
        logger.warning("MANAGER_TELEGRAM_ID not set — human mode activated but no one to notify")
        return

    tg_ref = f"@{user.username}" if user.username else f"<a href='tg://user?id={user.id}'>{user.full_name}</a>"
    await bot.send_message(
        mgr_id,
        f"🔔 <b>Новий чат з клієнтом</b>\n"
        f"👤 {tg_ref}\n"
        f"🆔 <code>{user.id}</code>\n\n"
        f"Відповідай <b>reply</b> на повідомлення нижче — бот автоматично передасть відповідь.\n"
        f"Щоб завершити сесію: /endchat {user.id}",
    )


async def forward_to_manager(message: Message, bot: Bot) -> None:
    """Forward an in-session user message to the manager."""
    mgr_id = settings.MANAGER_TELEGRAM_ID
    if not mgr_id:
        await message.answer(
            "⚠️ Менеджер зараз недоступний. Залиш заявку і ми зателефонуємо.",
            reply_markup=main_menu_keyboard(),
        )
        return

    user = message.from_user
    tg_ref = f"@{user.username}" if user.username else f"id:{user.id}"

    sent = await bot.send_message(
        mgr_id,
        f"💬 <b>{user.full_name}</b> ({tg_ref}):\n{message.text}",
    )
    # Remember which user sent this so manager reply can be routed back
    reply_map[sent.message_id] = user.id

    await message.answer("✉️ Передано менеджеру")


# ── Intercept all user text while in human mode ───────────────────────────

@router.message(IsHumanMode(), F.text, ~F.text.startswith("/"))
async def intercept_human_mode(message: Message, bot: Bot) -> None:
    """Catch every text message from a user in human mode and forward it."""
    await forward_to_manager(message, bot)


# ── /endchat — user ends the session ─────────────────────────────────────

@router.message(Command("endchat"), IsHumanMode())
async def user_end_chat(message: Message, bot: Bot) -> None:
    user = message.from_user
    await end_human_session(user.id)
    await message.answer(
        "✅ Чат завершено. Дякуємо!\n\nЧим ще можу допомогти?",
        reply_markup=main_menu_keyboard(),
    )
    mgr_id = settings.MANAGER_TELEGRAM_ID
    if mgr_id:
        tg_ref = f"@{user.username}" if user.username else str(user.id)
        await bot.send_message(mgr_id, f"🔴 Чат завершено клієнтом: {tg_ref} (id: {user.id})")


# ── /endchat <user_id> — manager ends a session from Telegram ────────────

@router.message(IsManagerChat(), Command("endchat"))
async def manager_end_chat(message: Message, bot: Bot) -> None:
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("Використання: /endchat <user_id>")
        return
    try:
        target_id = int(parts[1])
    except ValueError:
        await message.answer("Невірний user_id")
        return

    await end_human_session(target_id)
    await message.answer(f"✅ Чат з {target_id} завершено.")
    try:
        await bot.send_message(
            target_id,
            "✅ Менеджер завершив чат. Дякуємо!\n\nЧим ще можу допомогти?",
            reply_markup=main_menu_keyboard(),
        )
    except Exception as e:
        logger.warning(f"Could not notify user {target_id}: {e}")


# ── Manager reply → route back to user ───────────────────────────────────

@router.message(IsManagerChat(), F.reply_to_message, F.text)
async def manager_reply_handler(message: Message, bot: Bot) -> None:
    original_user_id = reply_map.get(message.reply_to_message.message_id)
    if not original_user_id:
        return  # Reply to some other message in manager's chat — ignore

    try:
        await bot.send_message(
            original_user_id,
            f"👨‍💼 <b>Менеджер:</b>\n{message.text}",
        )
    except Exception as e:
        logger.warning(f"Could not deliver manager reply to {original_user_id}: {e}")
        await message.answer(f"⚠️ Не вдалось доставити повідомлення користувачу {original_user_id}")
