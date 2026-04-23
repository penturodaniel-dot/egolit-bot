"""
Dynamic menu button handler.
Uses a custom filter so ONLY known button texts are intercepted here.
Unknown text falls through to search.router as free-form queries.
"""
from aiogram import Router, F, Bot
from aiogram.filters import BaseFilter
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

from bot.menu_cache import (
    ensure_loaded, find_button, sub_menu_keyboard, main_menu_keyboard, BACK_BUTTON
)
from bot.states import SearchFlow

router = Router()


# ── Custom filter: only matches known dynamic button texts ────────────────

class IsDynamicButton(BaseFilter):
    async def __call__(self, message: Message) -> bool:
        if not message.text:
            return False
        await ensure_loaded()
        return find_button(message.text) is not None


# ── Back button ───────────────────────────────────────────────────────────

@router.message(F.text == BACK_BUTTON)
async def handle_back(message: Message, state: FSMContext):
    await state.clear()
    await ensure_loaded()
    await message.answer("🏠 Головне меню", reply_markup=main_menu_keyboard())


# ── Dynamic button dispatcher ─────────────────────────────────────────────
# IsDynamicButton filter ensures only known buttons reach this handler.
# All other text falls through to search.router.

@router.message(IsDynamicButton())
async def handle_dynamic_button(message: Message, bot: Bot, state: FSMContext):
    btn = find_button(message.text)
    if btn is None:
        return  # should never happen due to filter, but safety net

    if btn.action_type == "submenu":
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
