from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

import logging
import httpx
from bot.keyboards import lead_cancel_keyboard, back_to_menu_keyboard, manager_choice_keyboard
from bot.menu_cache import main_menu_keyboard
from bot.states import LeadFlow
from db.connection import get_pool
from db.settings import get_notification_chat_id, get_notification_enabled, get_manager_online
from config import settings

logger = logging.getLogger(__name__)
router = Router()


async def _notify_manager(name: str, phone: str, username: str, details: str) -> None:
    """Send a Telegram notification to the configured chat when a new lead arrives."""
    if not await get_notification_enabled():
        return
    chat_id = await get_notification_chat_id()
    if not chat_id:
        return

    text = (
        "🔔 <b>Нова заявка!</b>\n\n"
        f"👤 <b>Ім'я:</b> {name}\n"
        f"📞 <b>Телефон:</b> {phone}\n"
        f"💬 <b>Telegram:</b> {username}\n"
        f"\n📝 <b>Деталі:</b>\n{details}"
    )

    try:
        async with httpx.AsyncClient(timeout=5) as client:
            await client.post(
                f"https://api.telegram.org/bot{settings.BOT_TOKEN}/sendMessage",
                json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
            )
    except Exception as e:
        logger.warning(f"Lead notification failed: {e}")


async def start_lead_flow(message: Message, state: FSMContext):
    await state.set_state(LeadFlow.waiting_name)
    await message.answer(
        "📝 Залишити заявку\n\nЯк тебе звати?",
        reply_markup=lead_cancel_keyboard(),
    )


@router.message(F.text == "📞 Поговорити з менеджером")
async def handle_manager_button(message: Message, state: FSMContext):
    online = await get_manager_online()
    status_line = "🟢 Менеджер зараз <b>онлайн</b>" if online else "🔴 Менеджер зараз <b>офлайн</b>"
    chat_note = "💬 <b>Живий чат</b> — пиши прямо тут, менеджер відповість у Telegram" if online else "💬 <b>Живий чат</b> — менеджер офлайн, залиш заявку"
    await message.answer(
        f"👨‍💼 <b>Зв'язок з менеджером</b>\n{status_line}\n\n"
        "📝 <b>Залишити заявку</b> — вкажи контакти, менеджер зателефонує\n"
        f"{chat_note}",
        reply_markup=manager_choice_keyboard(),
    )


@router.callback_query(F.data == "start_lead")
async def callback_start_lead(callback: CallbackQuery, state: FSMContext):
    await start_lead_flow(callback.message, state)
    await callback.answer()


@router.callback_query(F.data == "call_manager")
async def callback_call_manager(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer(
        "👨‍💼 <b>Як зв'яжемось з менеджером?</b>\n\n"
        "📝 <b>Залишити заявку</b> — вкажи контакти, менеджер зателефонує\n"
        "💬 <b>Живий чат</b> — пиши прямо тут, менеджер відповість у Telegram",
        reply_markup=manager_choice_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "start_chat")
async def callback_start_chat(callback: CallbackQuery, bot: Bot, state: FSMContext):
    # Check if manager is currently online
    online = await get_manager_online()
    if not online:
        await callback.answer("", show_alert=False)
        await callback.message.answer(
            "😔 <b>Менеджер зараз офлайн.</b>\n\n"
            "Залиш заявку — ми зателефонуємо найближчим часом! 👇",
        )
        await start_lead_flow(callback.message, state)
        return

    from bot.handlers.human import activate_human_mode
    await state.clear()
    await activate_human_mode(callback.message.chat.id, callback.from_user, bot)
    await callback.answer()


@router.callback_query(F.data == "cancel_lead")
async def callback_cancel_lead(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.answer(
        "Скасовано. Чим ще можу допомогти?",
        reply_markup=main_menu_keyboard(),
    )
    await callback.answer()


@router.message(LeadFlow.waiting_name)
async def lead_got_name(message: Message, state: FSMContext):
    await state.update_data(lead_name=message.text)
    await state.set_state(LeadFlow.waiting_phone)
    await message.answer(
        f"Приємно, {message.text}! 👋\n\nВкажи номер телефону або Telegram username для зв'язку:",
        reply_markup=lead_cancel_keyboard(),
    )


@router.message(LeadFlow.waiting_phone)
async def lead_got_phone(message: Message, state: FSMContext):
    await state.update_data(lead_phone=message.text)
    await state.set_state(LeadFlow.waiting_details)
    await message.answer(
        "Коротко опиши що потрібно (захід, дата, кількість людей, бюджет):",
        reply_markup=lead_cancel_keyboard(),
    )


@router.message(LeadFlow.waiting_details)
async def lead_got_details(message: Message, state: FSMContext):
    data = await state.get_data()

    lead_name = data.get("lead_name", "—")
    lead_phone = data.get("lead_phone", "—")
    lead_details = message.text
    user = message.from_user
    tg_username = f"@{user.username}" if user.username else f"id:{user.id}"

    # Зберігаємо ліда в bot_leads
    pool = await get_pool()
    await pool.execute("""
        INSERT INTO bot_leads (name, phone, telegram_id, username, details, status)
        VALUES ($1, $2, $3, $4, $5, 'new')
    """, lead_name, lead_phone, str(user.id), tg_username, lead_details)

    # Сповіщення менеджеру в Telegram
    await _notify_manager(lead_name, lead_phone, tg_username, lead_details)

    await state.clear()
    await message.answer(
        "✅ <b>Заявку прийнято!</b>\n\n"
        "Менеджер зв'яжеться з тобою найближчим часом.\n\n"
        "Чим ще можу допомогти?",
        reply_markup=main_menu_keyboard(),
        parse_mode="HTML",
    )
