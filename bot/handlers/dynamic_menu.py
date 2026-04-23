"""
Dynamic menu button handler.
Intercepts reply-keyboard button presses and dispatches to the correct action.
Registered BEFORE search.router so menu buttons are handled first.
"""
from aiogram import Router, F, Bot
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

from bot.menu_cache import (
    ensure_loaded, find_button, sub_menu_keyboard, main_menu_keyboard, BACK_BUTTON
)
from bot.states import SearchFlow

router = Router()


# ── Back button ───────────────────────────────────────────────────────────

@router.message(F.text == BACK_BUTTON)
async def handle_back(message: Message, state: FSMContext):
    await state.clear()
    await ensure_loaded()
    await message.answer("🏠 Головне меню", reply_markup=main_menu_keyboard())


# ── Dynamic button dispatcher ─────────────────────────────────────────────

@router.message(F.text)
async def handle_dynamic_button(message: Message, bot: Bot, state: FSMContext):
    await ensure_loaded()
    btn = find_button(message.text)
    if btn is None:
        return   # not a menu button — let search.router handle free text

    if btn.action_type == "submenu":
        # Show child buttons
        await message.answer(
            f"{btn.display}\n\nОберіть варіант:",
            reply_markup=sub_menu_keyboard(btn.id),
        )
        return

    if btn.action_type == "ai_search":
        from bot.handlers.search import _do_search
        await _do_search(message, bot, state, btn.ai_prompt or btn.display)
        return

    if btn.action_type == "custom_query":
        await state.set_state(SearchFlow.waiting_query)
        await message.answer("✍️ Напиши свій запит — що саме потрібно знайти?")
        return

    if btn.action_type == "lead_form":
        from bot.handlers.lead import start_lead_flow
        await start_lead_flow(message, state)
        return

    if btn.action_type == "manager":
        from bot.keyboards import manager_choice_keyboard
        await message.answer(
            "👨‍💼 Як вам допомогти?\n\n"
            "Залиште заявку — менеджер зв'яжеться з вами, "
            "або підключіться до живого чату прямо зараз.",
            reply_markup=manager_choice_keyboard(),
        )
        return
