"""
Dynamic menu button handler — supports unlimited nesting levels via nav stack.
Navigation stack is stored in FSM state: menu_stack = [parent_id, parent_id2, ...]
"""
from __future__ import annotations
import json
import logging
import dataclasses

from aiogram import Router, F, Bot
from aiogram.filters import BaseFilter
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from bot.menu_cache import (
    ensure_loaded, find_button, get_button_by_id,
    sub_menu_keyboard, main_menu_keyboard, BACK_BUTTON, _children,
)
from bot.states import SearchFlow, MenuSearch

router = Router()
logger = logging.getLogger(__name__)


# ── Custom filter: only matches known dynamic button texts ────────────────

class IsDynamicButton(BaseFilter):
    async def __call__(self, message: Message) -> bool:
        if not message.text:
            return False
        if message.text == BACK_BUTTON:
            return True
        await ensure_loaded()
        return find_button(message.text) is not None


# ── Back button ───────────────────────────────────────────────────────────

@router.message(F.text == BACK_BUTTON)
async def handle_back(message: Message, state: FSMContext):
    await ensure_loaded()
    data = await state.get_data()
    stack: list[int] = data.get("menu_stack", [])

    if len(stack) <= 1:
        # At level 1 or root — go to main menu
        await state.update_data(menu_stack=[])
        await message.answer("🏠 Головне меню", reply_markup=main_menu_keyboard())
    else:
        # Pop current level, go to parent's parent
        stack = stack[:-1]
        await state.update_data(menu_stack=stack)
        parent_id = stack[-1] if stack else None
        if parent_id is None:
            await message.answer("🏠 Головне меню", reply_markup=main_menu_keyboard())
        else:
            parent_btn = get_button_by_id(parent_id)
            label = parent_btn.display if parent_btn else "Оберіть варіант:"
            await message.answer(label, reply_markup=sub_menu_keyboard(parent_id))


# ── Dynamic button dispatcher ─────────────────────────────────────────────

@router.message(IsDynamicButton())
async def handle_dynamic_button(message: Message, bot: Bot, state: FSMContext):
    await ensure_loaded()
    btn = find_button(message.text)
    if btn is None:
        return

    if btn.action_type == "submenu":
        data = await state.get_data()
        stack: list[int] = data.get("menu_stack", [])
        stack = stack + [btn.id]
        await state.update_data(menu_stack=stack)
        await message.answer(
            f"{btn.display}\n\nОберіть варіант:",
            reply_markup=sub_menu_keyboard(btn.id),
        )
        return

    if btn.action_type == "direct_search":
        await _do_direct_search(message, bot, state, btn)
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


# ── Direct search (no AI parsing) ────────────────────────────────────────

async def _do_direct_search(message: Message, bot: Bot, state: FSMContext, btn):
    """Execute a direct DB search using button's direct_params JSON — bypasses AI parsing."""
    from bot.handlers.search import _send_results
    from db.queries import search_karabas_events, search_kino_events, search_products
    from ai.rerank import rerank_and_explain, CANDIDATE_FETCH

    if not btn.direct_params:
        await message.answer("⚙️ Параметри пошуку не налаштовано для цієї кнопки.")
        return

    try:
        params = json.loads(btn.direct_params)
    except Exception:
        await message.answer("⚙️ Помилка в параметрах кнопки (невалідний JSON).")
        return

    intent = params.get("intent", "event")
    category = params.get("category")
    categories = params.get("categories", [])
    date_filter = params.get("date_filter")
    search_text = params.get("search_text")
    city = params.get("city") or None
    ask_date = params.get("ask_date", False)

    # If ask_date=true — show date picker inline keyboard instead of searching now
    if ask_date:
        await state.update_data(pending_search_params={**params, "label": btn.display})
        await state.set_state(MenuSearch.waiting_date_pick)
        await message.answer(
            f"{btn.display}\n\nОберіть дату:",
            reply_markup=_date_picker_keyboard(),
        )
        return

    PAGE_SIZE = 2
    _fetch = CANDIDATE_FETCH + 1

    thinking_msg = await message.answer("🔍 Шукаю для тебе...")

    try:
        if intent == "event":
            if category == "кіно":
                raw = await search_kino_events(limit=_fetch, date_filter=date_filter, city=city)
            else:
                raw = await search_karabas_events(
                    category=category, limit=_fetch,
                    date_filter=date_filter, search_text=search_text, city=city,
                )
        else:  # service
            cat_list = categories if categories else ([category] if category else [])
            raw = await search_products(
                category_names=cat_list if cat_list else None,
                limit=_fetch,
                search_text=search_text,
                city=city,
            )

        has_more = len(raw) > CANDIDATE_FETCH
        candidates = raw[:CANDIDATE_FETCH]

        if not candidates:
            from bot.keyboards import manager_choice_keyboard
            not_found_text = (
                "😔 На жаль, нічого не знайдено за твоїм запитом.\n\n"
                "Наш менеджер зможе допомогти підібрати варіант особисто 👇"
            )
            try:
                await thinking_msg.delete()
            except Exception:
                pass
            await message.answer(not_found_text, reply_markup=manager_choice_keyboard())
            return

        rr = await rerank_and_explain(btn.display, candidates, top_n=PAGE_SIZE)
        id_map = {c.id: c for c in candidates}
        top = [id_map[i] for i in rr.top_ids if i in id_map]
        if not top:
            top = candidates[:PAGE_SIZE]

        shown_ids = [r.id for r in top]
        all_as_dicts = [dataclasses.asdict(c) for c in candidates]
        has_more = has_more or len(candidates) > PAGE_SIZE

        await state.update_data(
            last_query=btn.display,
            last_intent=intent,
            all_candidates=all_as_dicts,
            shown_ids=shown_ids,
            last_has_more=has_more,
            last_date_filter=date_filter,
            last_search_text=search_text,
            last_event_category=category,
            last_category_names=categories,
        )

        count = len(top)
        try:
            await thinking_msg.edit_text(f"✅ Знайдено {count} результатів:")
        except Exception:
            await thinking_msg.delete()

        if intent == "event":
            await _send_results(
                message, bot,
                products=[], events=top,
                ai_text=rr.intro, has_more=has_more,
                user_query=btn.display,
                precomputed_reasons=rr.reasons,
            )
        else:
            await _send_results(
                message, bot,
                products=top, events=[],
                ai_text=rr.intro, has_more=has_more,
                user_query=btn.display,
                precomputed_reasons=rr.reasons,
            )

    except Exception as e:
        logger.exception("direct_search error for btn %s: %s", btn.id, e)
        try:
            await thinking_msg.edit_text("⚠️ Помилка пошуку. Спробуй ще раз.")
        except Exception:
            await message.answer("⚠️ Помилка пошуку. Спробуй ще раз.")


# ── Date picker keyboard ─────────────────────────────────────────────────────

def _date_picker_keyboard():
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📅 Сьогодні",    callback_data="dpick:today"),
            InlineKeyboardButton(text="🗓 Ці вихідні",  callback_data="dpick:weekend"),
        ],
        [
            InlineKeyboardButton(text="📆 Цей тиждень", callback_data="dpick:week"),
            InlineKeyboardButton(text="🗓 Цей місяць",  callback_data="dpick:month"),
        ],
        [
            InlineKeyboardButton(text="📆 Вибрати дату у календарі", callback_data="dpick:calendar"),
        ],
        [
            InlineKeyboardButton(text="✨ Всі події",   callback_data="dpick:all"),
        ],
    ])


# ── Execute search from saved params + chosen date ────────────────────────────

async def _exec_pending_search(
    callback,
    bot: Bot,
    state: FSMContext,
    date_filter: str | None = None,
    specific_date: str | None = None,
):
    """Load pending_search_params from state and run the search with chosen date."""
    from bot.handlers.search import _send_results
    from db.queries import search_karabas_events, search_kino_events, search_products
    from ai.rerank import rerank_and_explain, CANDIDATE_FETCH

    data = await state.get_data()
    params = data.get("pending_search_params", {})
    await state.clear()

    intent = params.get("intent", "event")
    category = params.get("category")
    categories = params.get("categories", [])
    search_text = params.get("search_text")
    city = params.get("city") or None

    # Use date from JSON if no date chosen interactively
    if not date_filter and not specific_date:
        date_filter = params.get("date_filter")

    PAGE_SIZE = 2
    _fetch = CANDIDATE_FETCH + 1

    message = callback.message
    try:
        await callback.answer()
    except Exception:
        pass

    thinking_msg = await message.answer("🔍 Шукаю для тебе...")

    try:
        if intent == "event":
            if category == "кіно":
                raw = await search_kino_events(
                    limit=_fetch, date_filter=date_filter,
                    city=city, specific_date=specific_date,
                )
            else:
                raw = await search_karabas_events(
                    category=category, limit=_fetch,
                    date_filter=date_filter, search_text=search_text,
                    city=city, specific_date=specific_date,
                )
        else:
            cat_list = categories if categories else ([category] if category else [])
            raw = await search_products(
                category_names=cat_list if cat_list else None,
                limit=_fetch, search_text=search_text, city=city,
            )

        has_more = len(raw) > CANDIDATE_FETCH
        candidates = raw[:CANDIDATE_FETCH]

        if not candidates:
            from bot.keyboards import manager_choice_keyboard
            not_found_text = (
                "😔 На жаль, нічого не знайдено за твоїм запитом.\n\n"
                "Наш менеджер зможе допомогти підібрати варіант особисто 👇"
            )
            try:
                await thinking_msg.delete()
            except Exception:
                pass
            await message.answer(not_found_text, reply_markup=manager_choice_keyboard())
            return

        label = params.get("label", "")
        rr = await rerank_and_explain(label, candidates, top_n=PAGE_SIZE)
        id_map = {c.id: c for c in candidates}
        top = [id_map[i] for i in rr.top_ids if i in id_map] or candidates[:PAGE_SIZE]

        has_more = has_more or len(candidates) > PAGE_SIZE
        try:
            await thinking_msg.edit_text(f"✅ Знайдено {len(top)} результатів:")
        except Exception:
            await thinking_msg.delete()

        if intent == "event":
            await _send_results(message, bot, products=[], events=top,
                                ai_text=rr.intro, has_more=has_more,
                                user_query=label, precomputed_reasons=rr.reasons)
        else:
            await _send_results(message, bot, products=top, events=[],
                                ai_text=rr.intro, has_more=has_more,
                                user_query=label, precomputed_reasons=rr.reasons)

    except Exception as e:
        logger.exception("pending search error: %s", e)
        try:
            await thinking_msg.edit_text("⚠️ Помилка пошуку. Спробуй ще раз.")
        except Exception:
            await message.answer("⚠️ Помилка пошуку. Спробуй ще раз.")


# ── Date picker callbacks ─────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("dpick:"), MenuSearch.waiting_date_pick)
async def callback_date_pick(callback: CallbackQuery, bot: Bot, state: FSMContext):
    choice = callback.data.split(":", 1)[1]

    if choice == "calendar":
        from datetime import date as _date
        from bot.calendar_widget import build_date_picker_calendar
        today = _date.today()
        try:
            await callback.message.edit_reply_markup(
                reply_markup=build_date_picker_calendar(today.year, today.month)
            )
        except Exception:
            await callback.message.answer(
                "Оберіть дату:",
                reply_markup=build_date_picker_calendar(today.year, today.month),
            )
        await callback.answer()
        return

    if choice == "back":
        try:
            await callback.message.edit_reply_markup(reply_markup=_date_picker_keyboard())
        except Exception:
            await callback.message.answer("Оберіть дату:", reply_markup=_date_picker_keyboard())
        await callback.answer()
        return

    date_filter = None if choice == "all" else choice
    await _exec_pending_search(callback, bot, state, date_filter=date_filter)


# ── Calendar navigation (date picker context) ─────────────────────────────────

@router.callback_query(F.data.startswith("CAL:G:"), MenuSearch.waiting_date_pick)
async def callback_cal_nav_datepick(callback: CallbackQuery, state: FSMContext):
    from bot.calendar_widget import build_date_picker_calendar
    _, _, y, m = callback.data.split(":")
    try:
        await callback.message.edit_reply_markup(
            reply_markup=build_date_picker_calendar(int(y), int(m))
        )
    except Exception:
        pass
    await callback.answer()


@router.callback_query(F.data.startswith("CAL:D:"), MenuSearch.waiting_date_pick)
async def callback_cal_date_datepick(callback: CallbackQuery, bot: Bot, state: FSMContext):
    parts = callback.data.split(":")  # CAL:D:y:m:d
    y, m, d = int(parts[2]), int(parts[3]), int(parts[4])
    specific_date = f"{y:04d}-{m:02d}-{d:02d}"
    await _exec_pending_search(callback, bot, state, specific_date=specific_date)
