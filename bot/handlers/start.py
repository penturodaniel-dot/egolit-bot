from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from bot.keyboards import main_menu_keyboard

router = Router()

WELCOME_TEXT = """👋 Привіт! Я — помічник <b>Egolist</b>.

Допоможу знайти виконавців і послуги для твого заходу чи свята в Дніпрі.

Обери категорію або напиши що потрібно:"""


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        WELCOME_TEXT,
        reply_markup=main_menu_keyboard(),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "main_menu")
async def callback_main_menu(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.answer(
        "🏠 Головне меню\n\nОбери категорію або напиши запит:",
        reply_markup=main_menu_keyboard(),
    )
    await callback.answer()
