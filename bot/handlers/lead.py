from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from bot.keyboards import lead_cancel_keyboard, main_menu_keyboard, back_to_menu_keyboard
from bot.states import LeadFlow
from db.connection import get_pool
from config import settings

router = Router()

# Telegram ID менеджера — поки що захардкожено, потім через .env
MANAGER_CHAT_ID = None  # Встановіть chat_id менеджера


async def start_lead_flow(message: Message, state: FSMContext):
    await state.set_state(LeadFlow.waiting_name)
    await message.answer(
        "📝 Залишити заявку\n\nЯк тебе звати?",
        reply_markup=lead_cancel_keyboard(),
    )


@router.message(F.text == "📞 Поговорити з менеджером")
async def handle_manager_button(message: Message, state: FSMContext):
    await start_lead_flow(message, state)


@router.callback_query(F.data == "start_lead")
async def callback_start_lead(callback: CallbackQuery, state: FSMContext):
    await start_lead_flow(callback.message, state)
    await callback.answer()


@router.callback_query(F.data == "call_manager")
async def callback_call_manager(callback: CallbackQuery, state: FSMContext):
    await start_lead_flow(callback.message, state)
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

    await state.clear()
    await message.answer(
        "✅ <b>Заявку прийнято!</b>\n\n"
        "Менеджер зв'яжеться з тобою найближчим часом.\n\n"
        "Чим ще можу допомогти?",
        reply_markup=main_menu_keyboard(),
        parse_mode="HTML",
    )
