from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, URLInputFile
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest

from ai.parse import parse_intent
from ai.respond import format_response
from db.queries import search_products, search_events, ProductResult, EventResult
from bot.keyboards import results_keyboard, main_menu_keyboard
from bot.states import SearchFlow

router = Router()

# Telegram caption limit
CAPTION_LIMIT = 1024


def _build_product_card(p: ProductResult, index: int) -> str:
    lines = [f"<b>{index}. {p.name}</b>"]
    if p.category:
        lines.append(f"📂 {p.category}")
    if p.price:
        lines.append(f"💰 від {p.price} грн")
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


def _build_event_card(e: EventResult, index: int) -> str:
    lines = [f"<b>{index}. {e.title}</b>"]
    date_str = e.date
    if e.time:
        date_str += f" о {e.time}"
    lines.append(f"📅 {date_str}")
    if e.price:
        lines.append(f"💰 {e.price}")
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
):
    """Відправляє картку продукту — з фото якщо є, інакше текстом."""
    card_text = _build_product_card(product, index)

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
            # Фото недоступне — падаємо на текст
            pass

    # Fallback: текстова картка
    await message.answer(card_text, parse_mode="HTML", reply_markup=reply_markup)


async def _send_results(
    message: Message,
    bot: Bot,
    products: list[ProductResult],
    events: list[EventResult],
    ai_text: str,
    has_more: bool,
):
    """Відправляє AI-текст і картки результатів."""
    # Спочатку AI-текст вступу
    await message.answer(ai_text, parse_mode="HTML")

    if products:
        for i, p in enumerate(products, 1):
            # Кнопки тільки на останній картці
            markup = results_keyboard(has_more=has_more) if i == len(products) else None
            await _send_product_card(message, bot, p, i, reply_markup=markup)

    elif events:
        cards = [_build_event_card(e, i) for i, e in enumerate(events, 1)]
        text = "\n\n".join(cards)
        if len(text) > 4000:
            text = text[:3990] + "..."
        await message.answer(text, parse_mode="HTML", reply_markup=results_keyboard(has_more=has_more))

    else:
        await message.answer(
            "Нічого не знайдено. Спробуй змінити запит або поговори з менеджером.",
            reply_markup=results_keyboard(has_more=False),
        )


async def _do_search(message: Message, bot: Bot, state: FSMContext, user_text: str):
    data = await state.get_data()
    history = data.get("history", [])

    thinking_msg = await message.answer("🔍 Шукаю для тебе...")

    # Крок 1: AI парсить намір → точні category_ids
    parsed = await parse_intent(user_text, history)

    history.append({"role": "user", "content": user_text})
    await state.update_data(
        history=history[-8:],
        last_query=user_text,
        last_intent=parsed.intent,
        last_category_ids=parsed.category_ids,
        last_max_price=parsed.max_price,
        last_offset=0,
    )

    await thinking_msg.delete()

    if parsed.needs_clarification and parsed.clarification_question:
        await message.answer(parsed.clarification_question)
        return

    if parsed.intent == "lead":
        from bot.handlers.lead import start_lead_flow
        await start_lead_flow(message, state)
        return

    # Крок 2: пошук в БД
    products, events = [], []
    if parsed.intent == "event":
        events = await search_events(limit=5)
    else:
        products = await search_products(
            category_ids=parsed.category_ids or None,
            max_price=parsed.max_price,
            limit=5,
            offset=0,
        )

    # Крок 3: AI форматує вступний текст
    ai_text = await format_response(user_text, products or None, events or None)

    await _send_results(message, bot, products, events, ai_text, has_more=bool(products or events))


# ── Кнопки меню ───────────────────────────────────────────────────────────

@router.message(F.text == "📅 Найближчі події")
async def handle_events_button(message: Message, bot: Bot, state: FSMContext):
    await _do_search(message, bot, state, "найближчі події в Дніпрі")


@router.message(F.text == "✍️ Свій запит")
async def handle_custom_query(message: Message, state: FSMContext):
    await state.set_state(SearchFlow.waiting_query)
    await message.answer("✍️ Напиши свій запит — що саме потрібно знайти?")


@router.message(F.text.in_([
    "🎉 Організація свята", "📸 Фото та відео",
    "🎭 Аніматори та шоу", "🌸 Декор та флористи",
]))
async def handle_menu_button(message: Message, bot: Bot, state: FSMContext):
    await _do_search(message, bot, state, message.text)


# ── Вільний текст ──────────────────────────────────────────────────────────

@router.message(SearchFlow.waiting_query)
async def handle_free_query_state(message: Message, bot: Bot, state: FSMContext):
    await state.clear()
    await _do_search(message, bot, state, message.text)


@router.message(F.text & ~F.text.startswith("/"))
async def handle_free_text(message: Message, bot: Bot, state: FSMContext):
    await _do_search(message, bot, state, message.text)


# ── Ще варіанти ────────────────────────────────────────────────────────────

@router.callback_query(F.data == "more_results")
async def callback_more_results(callback: CallbackQuery, bot: Bot, state: FSMContext):
    data = await state.get_data()
    offset = data.get("last_offset", 0) + 5
    intent = data.get("last_intent", "service")
    category_ids = data.get("last_category_ids", [])
    max_price = data.get("last_max_price")

    await callback.answer("Шукаю ще...")

    if intent == "event":
        results = await search_events(limit=5)
        products, events = [], results
    else:
        products = await search_products(
            category_ids=category_ids or None,
            max_price=max_price,
            limit=5,
            offset=offset,
        )
        events = []

    await state.update_data(last_offset=offset)

    if not products and not events:
        await callback.message.answer(
            "Більше варіантів не знайдено. Спробуй змінити запит.",
            reply_markup=results_keyboard(has_more=False),
        )
        return

    if products:
        for i, p in enumerate(products, 1):
            markup = results_keyboard(has_more=True) if i == len(products) else None
            await _send_product_card(callback.message, bot, p, i, reply_markup=markup)
    elif events:
        cards = [_build_event_card(e, i) for i, e in enumerate(events, 1)]
        text = "\n\n".join(cards)
        if len(text) > 4000:
            text = text[:3990] + "..."
        await callback.message.answer(
            text,
            parse_mode="HTML",
            reply_markup=results_keyboard(has_more=True),
        )
