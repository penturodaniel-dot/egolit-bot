from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from bot.menu_cache import ensure_loaded, main_menu_keyboard, main_menu_keyboard_for_state, reload_buttons
from bot.fsm_helpers import preserve_clear

router = Router()

WELCOME_TEXT = """👋 Привіт! Я — помічник <b>Egolist</b>.

Допоможу знайти заклади, події та ідеї для відпочинку в Дніпрі.

Обери категорію або напиши що потрібно:"""


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await preserve_clear(state)
    await reload_buttons()          # завжди свіжі кнопки при /start

    # Reset human mode — both old sessions table and new chat_sessions
    if message.from_user:
        try:
            from db.human_sessions import end_human_session
            await end_human_session(message.from_user.id)
        except Exception:
            pass
        try:
            from db.chat import set_session_status
            await set_session_status(message.from_user.id, "ai")
        except Exception:
            pass

    await message.answer(
        WELCOME_TEXT,
        reply_markup=main_menu_keyboard(),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "main_menu")
async def callback_main_menu(callback: CallbackQuery, state: FSMContext):
    await preserve_clear(state)
    await ensure_loaded()
    data = await state.get_data()
    city = data.get("user_city")
    city_line = f"\n📍 Місто: <b>{city}</b>" if city else ""
    await callback.message.answer(
        f"🏠 Головне меню{city_line}\n\nОбери категорію:",
        reply_markup=await main_menu_keyboard_for_state(state),
        parse_mode="HTML",
    )
    await callback.answer()
