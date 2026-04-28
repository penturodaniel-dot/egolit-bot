import asyncio
from datetime import date as _date

from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, URLInputFile
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from ai.parse import parse_intent
from ai.respond import format_intro, generate_match_reasons
from db.queries import search_products, search_karabas_events, search_kino_events, ProductResult, EventResult
from db.chat import get_session_by_user, save_outgoing_message
from bot.keyboards import results_keyboard, manager_choice_keyboard
from bot.calendar_widget import build_calendar, IGN
from bot.states import SearchFlow


# ── Clarification keyboards ────────────────────────────────────────────────

def _event_type_keyboard() -> InlineKeyboardMarkup:
    options = [
        ("🎂 День народження", "scat:birthday"),
        ("🏢 Корпоратив",      "scat:corporate"),
        ("💑 Весілля",         "scat:wedding"),
        ("🎉 Загальний захід", "scat:event"),
        ("🎵 Концерт / Шоу",  "scat:concert"),
        ("👶 Дитяче свято",   "scat:kids"),
        ("❓ Інше",            "scat:other"),
    ]
    rows = [[InlineKeyboardButton(text=label, callback_data=cb)] for label, cb in options]
    rows.append([InlineKeyboardButton(text="❌ Скасувати", callback_data="main_menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _budget_keyboard() -> InlineKeyboardMarkup:
    options = [
        ("до 5 000 грн",          "sbud:5000"),
        ("5 000 – 10 000 грн",    "sbud:10000"),
        ("10 000 – 50 000 грн",   "sbud:50000"),
        ("50 000 – 100 000 грн",  "sbud:100000"),
        ("100 000 – 300 000 грн", "sbud:300000"),
        ("💬 Інше / уточнити",    "sbud:other"),
    ]
    rows = [[InlineKeyboardButton(text=label, callback_data=cb)] for label, cb in options]
    rows.append([InlineKeyboardButton(text="❌ Скасувати", callback_data="main_menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

router = Router()

# Telegram caption limit
CAPTION_LIMIT = 1024

# Results per page (change here to affect both first load and "more" button)
PAGE_SIZE = 2


def _card_keyboard(
    url: str | None,
    url_label: str,
    more_markup: InlineKeyboardMarkup | None = None,
) -> InlineKeyboardMarkup | None:
    """Build inline keyboard: URL button (if url) + rows from more_markup."""
    rows = []
    if url:
        rows.append([InlineKeyboardButton(text=url_label, url=url)])
    if more_markup:
        rows.extend(more_markup.inline_keyboard)
    return InlineKeyboardMarkup(inline_keyboard=rows) if rows else None


def _product_contact_keyboard(
    p: "ProductResult",
    more_markup: InlineKeyboardMarkup | None = None,
) -> InlineKeyboardMarkup | None:
    """Build contact keyboard for a product: best available URL-based contact.
    Phone is shown in card text — tel: links are not supported by Telegram inline buttons.
    Priority: Детальніше (product_url) > Telegram > Instagram > Website.
    """
    rows = []
    if p.product_url:
        rows.append([InlineKeyboardButton(text="🔗 Детальніше", url=p.product_url)])
    if p.telegram_contact:
        handle = p.telegram_contact.lstrip("@")
        rows.append([InlineKeyboardButton(text="💬 Написати в Telegram", url=f"https://t.me/{handle}")])
    elif p.instagram:
        handle = p.instagram.lstrip("@")
        rows.append([InlineKeyboardButton(text="📷 Instagram", url=f"https://instagram.com/{handle}")])
    elif p.website:
        website = p.website if p.website.startswith("http") else f"https://{p.website}"
        rows.append([InlineKeyboardButton(text="🌐 Сайт", url=website)])
    if more_markup:
        rows.extend(more_markup.inline_keyboard)
    return InlineKeyboardMarkup(inline_keyboard=rows) if rows else None


async def _keep_typing(bot: Bot, chat_id: int, stop_event: asyncio.Event) -> None:
    """Resends typing action every 4s so the indicator stays alive during long searches."""
    while not stop_event.is_set():
        try:
            await bot.send_chat_action(chat_id, "typing")
        except Exception:
            pass
        await asyncio.sleep(4)


def _build_product_card(p: ProductResult, index: int, reason: str = "") -> str:
    lines = [f"<b>{index}. {p.name}</b>"]
    if p.category:
        lines.append(f"📂 {p.category}")
    if p.price:
        lines.append(f"💰 від {p.price} грн")
    if reason:
        lines.append(f"✅ <i>{reason}</i>")
    if p.description:
        lines.append(p.description[:200])
    contacts = []
    if p.phone:
        contacts.append(f"📞 {p.phone}")
    if p.instagram:
        contacts.append(f"📷 @{p.instagram}")
    if p.website:
        contacts.append(f"🌐 {p.website}")
    if contacts:
        lines.append(" | ".join(contacts))
    return "\n".join(lines)


def _build_event_card(e: EventResult, index: int, reason: str = "") -> str:
    lines = [f"<b>{index}. {e.title}</b>"]
    date_str = e.date
    if e.time:
        date_str += f" о {e.time}"
    lines.append(f"📅 {date_str}")
    if e.price:
        lines.append(f"💰 {e.price}")
    if reason:
        lines.append(f"✅ <i>{reason}</i>")
    if e.place_name:
        lines.append(f"📍 {e.place_name}")
    if e.place_address:
        lines.append(f"   {e.place_address}")
    return "\n".join(lines)


async def _send_product_card(
    message: Message,
    bot: Bot,
    product: ProductResult,
    index: int,
    reply_markup=None,
    reason: str = "",
):
    """Відправляє картку продукту — з фото якщо є, інакше текстом."""
    card_text = _build_product_card(product, index, reason)

    if product.photo_url:
        try:
            caption = card_text[:CAPTION_LIMIT]
            await bot.send_photo(
                chat_id=message.chat.id,
                photo=URLInputFile(product.photo_url),
                caption=caption,
                parse_mode="HTML",
                reply_markup=reply_markup,
            )
            return
        except (TelegramBadRequest, Exception):
            pass

    await message.answer(card_text, parse_mode="HTML", reply_markup=reply_markup)


async def _send_event_card(
    message: Message,
    bot: Bot,
    event: EventResult,
    index: int,
    reply_markup=None,
    reason: str = "",
):
    """Відправляє картку події — з фото якщо є, інакше текстом."""
    card_text = _build_event_card(event, index, reason)

    if event.photo_url:
        try:
            caption = card_text[:CAPTION_LIMIT]
            await bot.send_photo(
                chat_id=message.chat.id,
                photo=URLInputFile(event.photo_url),
                caption=caption,
                parse_mode="HTML",
                reply_markup=reply_markup,
            )
            return
        except (TelegramBadRequest, Exception):
            pass

    await message.answer(card_text, parse_mode="HTML", reply_markup=reply_markup)


async def _send_results(
    message: Message,
    bot: Bot,
    products: list[ProductResult],
    events: list[EventResult],
    ai_text: str,
    has_more: bool,
    user_query: str = "",
):
    """Відправляє AI-текст і картки результатів."""
    items = products or events

    # ── Нічого не знайдено — одне чітке повідомлення з кнопками менеджера ──
    if not items:
        not_found_text = (
            "😔 На жаль, нічого не знайдено за твоїм запитом.\n\n"
            "Наш менеджер зможе допомогти підібрати варіант особисто 👇"
        )
        await message.answer(not_found_text, reply_markup=manager_choice_keyboard())
        try:
            if message.from_user:
                await save_outgoing_message(message.from_user.id, not_found_text)
        except Exception:
            pass
        return

    # ── Є результати — вступний AI-текст ──
    if not (ai_text or "").strip():
        ai_text = "Ось що знайшов 👇"
    await message.answer(ai_text, parse_mode="HTML")
    try:
        if message.from_user:
            await save_outgoing_message(message.from_user.id, ai_text)
    except Exception:
        pass

    # Generate "why this fits" reasons for all results in one AI call
    reasons: list[str] = []
    if user_query and items:
        try:
            reasons = await generate_match_reasons(
                user_query,
                products=products if products else None,
                events=events if events else None,
            )
        except Exception:
            reasons = [""] * len(items)

    # Progress message — visible between cards, deleted after last one
    progress_msg = None
    if len(items) > 1:
        progress_msg = await message.answer("📤 Показую результати, зачекай...")

    if products:
        for i, p in enumerate(products, 1):
            await bot.send_chat_action(message.chat.id, "upload_photo")
            is_last = i == len(products)
            more = results_keyboard(has_more=has_more) if is_last else None
            markup = _product_contact_keyboard(p, more)
            reason = reasons[i - 1] if i <= len(reasons) else ""
            await _send_product_card(message, bot, p, i, reply_markup=markup, reason=reason)
            if progress_msg and is_last:
                try:
                    await progress_msg.delete()
                except Exception:
                    pass

    elif events:
        for i, e in enumerate(events, 1):
            await bot.send_chat_action(message.chat.id, "upload_photo")
            is_last = i == len(events)
            more = results_keyboard(has_more=has_more) if is_last else None
            markup = _card_keyboard(e.source_url, "🔗 Детальніше", more)
            reason = reasons[i - 1] if i <= len(reasons) else ""
            await _send_event_card(message, bot, e, i, reply_markup=markup, reason=reason)
            if progress_msg and is_last:
                try:
                    await progress_msg.delete()
                except Exception:
                    pass


async def _do_search(message: Message, bot: Bot, state: FSMContext, user_text: str):
    data = await state.get_data()
    history = data.get("history", [])

    thinking_msg = await message.answer("🔍 Шукаю для тебе...")

    # Keep typing indicator alive while search runs
    stop_typing = asyncio.Event()
    typing_task = asyncio.create_task(
        _keep_typing(bot, message.chat.id, stop_typing)
    )

    products: list = []
    events: list = []
    ai_intro = ""

    search_error = False
    try:
        # Крок 1: AI парсить намір → точні category_ids
        parsed = await parse_intent(user_text, history)

        history.append({"role": "user", "content": user_text})
        await state.update_data(
            history=history[-8:],
            last_query=user_text,
            last_intent=parsed.intent,
            last_event_category=parsed.event_category,
            last_category_names=parsed.category_names,
            last_max_price=parsed.max_price,
            last_search_text=parsed.search_text,
            last_offset=0,
        )

        if parsed.needs_clarification and parsed.clarification_question:
            await thinking_msg.delete()
            q = parsed.clarification_question
            if "📅" in q:
                # Show interactive calendar
                today = _date.today()
                await state.set_state(SearchFlow.waiting_date)
                await message.answer(q, parse_mode="HTML",
                                     reply_markup=build_calendar(today.year, today.month))
            elif "🎉" in q:
                # Show event-type buttons
                await state.set_state(SearchFlow.waiting_category)
                await message.answer(q, parse_mode="HTML",
                                     reply_markup=_event_type_keyboard())
            elif "💰" in q:
                # Show budget-range buttons
                await state.set_state(SearchFlow.waiting_budget)
                await message.answer(q, parse_mode="HTML",
                                     reply_markup=_budget_keyboard())
            else:
                await message.answer(q, parse_mode="HTML")
            return

        if parsed.intent == "lead":
            await thinking_msg.delete()
            from bot.handlers.lead import start_lead_flow
            await start_lead_flow(message, state)
            return

        # Крок 2: пошук в БД
        date_filter = parsed.date_filter  # "today" | "weekend" | "week" | "month" | None
        search_text = parsed.search_text
        await state.update_data(last_date_filter=date_filter, last_search_text=search_text)

        products, events = [], []
        has_more = False
        _fetch = PAGE_SIZE + 1  # fetch one extra to detect if more exist

        if parsed.intent == "event":
            if parsed.event_category == "кіно":
                raw = await search_kino_events(
                    limit=_fetch,
                    date_filter=date_filter,
                    search_text=search_text,
                )
            else:
                raw = await search_karabas_events(
                    category=parsed.event_category,
                    limit=_fetch,
                    date_filter=date_filter,
                    search_text=search_text,
                )
            has_more = len(raw) > PAGE_SIZE
            events = raw[:PAGE_SIZE]
        else:
            raw = await search_products(
                category_names=parsed.category_names or None,
                max_price=parsed.max_price,
                search_text=search_text,
                limit=_fetch,
                offset=0,
            )
            has_more = len(raw) > PAGE_SIZE
            products = raw[:PAGE_SIZE]

        # Track shown IDs to prevent duplicates on "load more"
        shown_ids = [p.id for p in products] + [e.id for e in events]
        await state.update_data(shown_ids=shown_ids, last_has_more=has_more)

        # Крок 3: AI генерує короткий вступ (1 речення)
        count = len(products) or len(events)
        ai_intro = await format_intro(user_text, has_results=bool(products or events), count=count)

    except Exception as e:
        search_error = True
        import logging
        logging.getLogger(__name__).exception("Search error for query %r: %s", user_text, e)
    finally:
        stop_typing.set()
        typing_task.cancel()

    if search_error:
        try:
            await thinking_msg.edit_text("⚠️ Виникла помилка під час пошуку. Спробуй ще раз або напиши менеджеру.")
        except Exception:
            await message.answer("⚠️ Виникла помилка під час пошуку. Спробуй ще раз або напиши менеджеру.")
        return

    # Редагуємо thinking message → підсумок замість видалення
    count = len(products) if products else len(events)
    if count:
        try:
            await thinking_msg.edit_text(f"✅ Знайдено {count} результатів:")
        except Exception:
            await thinking_msg.delete()
    else:
        try:
            await thinking_msg.edit_text("🔍 Результати пошуку:")
        except Exception:
            await thinking_msg.delete()

    await _send_results(message, bot, products, events, ai_intro, has_more=has_more, user_query=user_text)


# Фіксовані кнопки видалені — тепер всі кнопки меню динамічні (dynamic_menu.py)


# ── Вільний текст ──────────────────────────────────────────────────────────

@router.message(SearchFlow.waiting_query)
async def handle_free_query_state(message: Message, bot: Bot, state: FSMContext):
    await state.clear()
    await _do_search(message, bot, state, message.text)


@router.message(F.text & ~F.text.startswith("/"))
async def handle_free_text(message: Message, bot: Bot, state: FSMContext):
    # If manager has taken over this chat — don't process with AI
    if message.from_user:
        try:
            session = await get_session_by_user(message.from_user.id)
            if session and session.get("status") == "human":
                return
        except Exception:
            pass
    await _do_search(message, bot, state, message.text)


# ── Ще варіанти ────────────────────────────────────────────────────────────

@router.callback_query(F.data == "more_results")
async def callback_more_results(callback: CallbackQuery, bot: Bot, state: FSMContext):
    data = await state.get_data()
    offset = data.get("last_offset", 0) + PAGE_SIZE
    intent = data.get("last_intent", "service")
    event_category = data.get("last_event_category")
    category_names = data.get("last_category_names", [])
    max_price = data.get("last_max_price")
    date_filter = data.get("last_date_filter")
    search_text = data.get("last_search_text")
    shown_ids: set = set(data.get("shown_ids", []))

    await callback.answer("Шукаю ще...")

    _fetch = PAGE_SIZE * 3  # fetch extra to compensate for duplicates

    if intent == "event":
        if event_category == "кіно":
            raw = await search_kino_events(
                limit=_fetch, offset=offset,
                date_filter=date_filter, search_text=search_text,
            )
        else:
            raw = await search_karabas_events(
                category=event_category, limit=_fetch, offset=offset,
                date_filter=date_filter, search_text=search_text,
            )
        filtered = [e for e in raw if e.id not in shown_ids]
        has_more = len(filtered) > PAGE_SIZE
        results = filtered[:PAGE_SIZE]
        products, events = [], results
    else:
        raw = await search_products(
            category_names=category_names or None,
            max_price=max_price,
            search_text=search_text,
            limit=_fetch,
            offset=offset,
        )
        filtered = [p for p in raw if p.id not in shown_ids]
        has_more = len(filtered) > PAGE_SIZE
        products = filtered[:PAGE_SIZE]
        events = []

    # Save newly shown IDs
    new_ids = [p.id for p in products] + [e.id for e in events]
    shown_ids.update(new_ids)
    await state.update_data(last_offset=offset, shown_ids=list(shown_ids))

    if not products and not events:
        await callback.message.answer(
            "Більше варіантів не знайдено. Спробуй змінити запит.",
            reply_markup=results_keyboard(has_more=False),
        )
        return

    if products:
        for i, p in enumerate(products, 1):
            is_last = i == len(products)
            more = results_keyboard(has_more=has_more) if is_last else None
            markup = _product_contact_keyboard(p, more)
            await _send_product_card(callback.message, bot, p, i, reply_markup=markup)
    elif events:
        for i, e in enumerate(events, 1):
            is_last = i == len(events)
            more = results_keyboard(has_more=has_more) if is_last else None
            markup = _card_keyboard(e.source_url, "🔗 Детальніше", more)
            await _send_event_card(callback.message, bot, e, i, reply_markup=markup)


# ── Clarification: DATE (calendar) ─────────────────────────────────────────

@router.callback_query(F.data == IGN)
async def clarif_calendar_ignore(callback: CallbackQuery):
    await callback.answer()


@router.callback_query(F.data.startswith("CAL:G:"), SearchFlow.waiting_date)
async def clarif_calendar_navigate(callback: CallbackQuery):
    _, _, year, month = callback.data.split(":")
    try:
        await callback.message.edit_reply_markup(
            reply_markup=build_calendar(int(year), int(month))
        )
    except Exception:
        pass
    await callback.answer()


@router.callback_query(F.data.startswith("CAL:D:"), SearchFlow.waiting_date)
async def clarif_calendar_day(callback: CallbackQuery, bot: Bot, state: FSMContext):
    _, _, year, month, day = callback.data.split(":")
    chosen = _date(int(year), int(month), int(day))
    date_str = chosen.strftime("%d.%m.%Y")
    await callback.answer(f"✅ {date_str}")
    try:
        await callback.message.edit_text(f"📅 Дата: <b>{date_str}</b>", parse_mode="HTML")
    except Exception:
        pass
    data = await state.get_data()
    query = data.get("last_query", "")
    await state.clear()
    await _do_search(callback.message, bot, state, f"{query}, дата {date_str}")


# ── Clarification: EVENT TYPE ───────────────────────────────────────────────

_SCAT_LABELS = {
    "birthday":  "День народження",
    "corporate": "Корпоратив",
    "wedding":   "Весілля",
    "event":     "Загальний захід",
    "concert":   "Концерт / Шоу",
    "kids":      "Дитяче свято",
    "other":     "Інший захід",
}

@router.callback_query(F.data.startswith("scat:"), SearchFlow.waiting_category)
async def clarif_category_chosen(callback: CallbackQuery, bot: Bot, state: FSMContext):
    cat_code = callback.data.split(":", 1)[1]
    label = _SCAT_LABELS.get(cat_code, cat_code)
    await callback.answer(f"✅ {label}")
    try:
        await callback.message.edit_text(f"🎉 Тип заходу: <b>{label}</b>", parse_mode="HTML")
    except Exception:
        pass
    data = await state.get_data()
    query = data.get("last_query", "")
    await state.clear()
    await _do_search(callback.message, bot, state, f"{label}: {query}")


# ── Clarification: BUDGET ───────────────────────────────────────────────────

_BUDGET_LABELS = {
    "5000":   "до 5 000 грн",
    "10000":  "5 000 – 10 000 грн",
    "50000":  "10 000 – 50 000 грн",
    "100000": "50 000 – 100 000 грн",
    "300000": "100 000 – 300 000 грн",
    "other":  "бюджет уточнимо",
}

@router.callback_query(F.data.startswith("sbud:"), SearchFlow.waiting_budget)
async def clarif_budget_chosen(callback: CallbackQuery, bot: Bot, state: FSMContext):
    bud_code = callback.data.split(":", 1)[1]
    label = _BUDGET_LABELS.get(bud_code, bud_code)
    max_price = int(bud_code) if bud_code.isdigit() else None
    await callback.answer(f"✅ {label}")
    try:
        await callback.message.edit_text(f"💰 Бюджет: <b>{label}</b>", parse_mode="HTML")
    except Exception:
        pass
    data = await state.get_data()
    query = data.get("last_query", "")
    if max_price:
        await state.update_data(last_max_price=max_price)
    await state.clear()
    await _do_search(callback.message, bot, state, f"{query}, бюджет {label}")
