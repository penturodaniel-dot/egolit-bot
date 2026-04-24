from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
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

# Lead categories — shown as inline buttons
LEAD_CATEGORIES = [
    ("🎂 День народження", "birthday"),
    ("🏢 Корпоратив", "corporate"),
    ("💑 Побачення під ключ", "date"),
    ("🎉 Організація заходу", "event"),
    ("🎵 Пошук виконавця", "performer"),
    ("❓ Просто питання", "question"),
    ("✏️ Інше", "other"),
]


def _category_keyboard() -> InlineKeyboardMarkup:
    rows = []
    for label, code in LEAD_CATEGORIES:
        rows.append([InlineKeyboardButton(text=label, callback_data=f"lead_cat:{code}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _skip_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⏭ Пропустити", callback_data="lead_skip")],
        [InlineKeyboardButton(text="❌ Скасувати", callback_data="cancel_lead")],
    ])


def _category_label(code: str) -> str:
    for label, c in LEAD_CATEGORIES:
        if c == code:
            return label
    return code


async def _notify_manager(
    name: str, phone: str, username: str,
    category: str, details: str, budget: str, date: str, people: str
) -> None:
    """Send a Telegram notification to the configured chat when a new lead arrives."""
    if not await get_notification_enabled():
        return
    chat_id = await get_notification_chat_id()
    if not chat_id:
        return

    extras = ""
    if budget:
        extras += f"💰 <b>Бюджет:</b> {budget}\n"
    if date:
        extras += f"📅 <b>Дата:</b> {date}\n"
    if people:
        extras += f"👥 <b>Людей:</b> {people}\n"

    text = (
        "🔔 <b>Нова заявка!</b>\n\n"
        f"👤 <b>Ім'я:</b> {name}\n"
        f"📞 <b>Телефон:</b> {phone}\n"
        f"💬 <b>Telegram:</b> {username}\n"
        f"🏷 <b>Категорія:</b> {_category_label(category)}\n"
        f"{extras}"
        f"\n📝 <b>Деталі:</b>\n{details or '—'}"
    )

    try:
        async with httpx.AsyncClient(timeout=5) as client:
            await client.post(
                f"https://api.telegram.org/bot{settings.BOT_TOKEN}/sendMessage",
                json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
            )
    except Exception as e:
        logger.warning(f"Lead notification failed: {e}")


async def _save_lead(
    user_id: int, name: str, phone: str, username: str,
    category: str, details: str, budget: str, date: str, people: str
) -> None:
    """Save lead to bot_leads. Creates table if needed, adds missing columns."""
    pool = await get_pool()

    # Create table if it doesn't exist yet
    await pool.execute("""
        CREATE TABLE IF NOT EXISTS bot_leads (
            id           SERIAL PRIMARY KEY,
            name         TEXT,
            phone        TEXT,
            telegram_id  TEXT,
            username     TEXT,
            details      TEXT,
            category     TEXT,
            budget       TEXT,
            date_needed  TEXT,
            people_count TEXT,
            status       TEXT NOT NULL DEFAULT 'new',
            manager_note TEXT,
            created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)

    # Ensure extra columns exist (safe migration for older DBs)
    for col, coltype in [("category", "TEXT"), ("budget", "TEXT"), ("date_needed", "TEXT"), ("people_count", "TEXT"), ("manager_note", "TEXT")]:
        try:
            await pool.execute(f"ALTER TABLE bot_leads ADD COLUMN IF NOT EXISTS {col} {coltype}")
        except Exception:
            pass

    combined = details or ""
    if budget:
        combined += f"\nБюджет: {budget}"
    if date:
        combined += f"\nДата: {date}"
    if people:
        combined += f"\nКількість людей: {people}"

    try:
        await pool.execute("""
            INSERT INTO bot_leads (name, phone, telegram_id, username, details, category, budget, date_needed, people_count, status)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, 'new')
        """, name, phone, str(user_id), username, combined.strip(),
            category, budget or None, date or None, people or None)
    except Exception:
        # Fallback without new columns
        await pool.execute("""
            INSERT INTO bot_leads (name, phone, telegram_id, username, details, status)
            VALUES ($1, $2, $3, $4, $5, 'new')
        """, name, phone, str(user_id), username, combined.strip())


# ── Entry points ───────────────────────────────────────────────────────────

async def start_lead_flow(message: Message, state: FSMContext, prefill: dict | None = None):
    """Start lead collection. prefill can contain category, details etc from context."""
    if prefill:
        await state.update_data(**prefill)
    await state.set_state(LeadFlow.waiting_name)
    await message.answer(
        "📝 <b>Залишити заявку</b>\n\nЯк тебе звати?",
        reply_markup=lead_cancel_keyboard(),
    )


@router.message(F.text == "📞 Поговорити з менеджером")
async def handle_manager_button(message: Message, state: FSMContext):
    online = await get_manager_online()
    status_line = "🟢 Менеджер зараз <b>онлайн</b>" if online else "🔴 Менеджер зараз <b>офлайн</b>"
    chat_note = (
        "💬 <b>Живий чат</b> — пиши прямо тут, менеджер відповість у Telegram"
        if online else
        "💬 <b>Живий чат</b> — менеджер офлайн, залиш заявку"
    )
    await message.answer(
        f"👨‍💼 <b>Зв'язок з менеджером</b>\n{status_line}\n\n"
        "📝 <b>Залишити заявку</b> — вкажи контакти, менеджер зателефонує\n"
        f"{chat_note}",
        reply_markup=manager_choice_keyboard(),
    )


@router.callback_query(F.data == "start_lead")
async def callback_start_lead(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await start_lead_flow(callback.message, state)


@router.callback_query(F.data == "call_manager")
async def callback_call_manager(callback: CallbackQuery, state: FSMContext):
    online = await get_manager_online()
    status_line = "🟢 Менеджер зараз <b>онлайн</b>" if online else "🔴 Менеджер зараз <b>офлайн</b>"
    await callback.message.answer(
        f"👨‍💼 <b>Зв'язок з менеджером</b>\n{status_line}\n\n"
        "📝 <b>Залишити заявку</b> — вкажи контакти, менеджер зателефонує\n"
        "💬 <b>Живий чат</b> — пиши прямо тут, менеджер відповість у Telegram",
        reply_markup=manager_choice_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "start_chat")
async def callback_start_chat(callback: CallbackQuery, bot: Bot, state: FSMContext):
    online = await get_manager_online()
    if not online:
        await callback.answer()
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


# ── Step 1: Name ───────────────────────────────────────────────────────────

@router.message(LeadFlow.waiting_name)
async def lead_got_name(message: Message, state: FSMContext):
    await state.update_data(lead_name=message.text.strip())
    await state.set_state(LeadFlow.waiting_phone)
    await message.answer(
        f"Приємно, {message.text.split()[0]}! 👋\n\n"
        "Вкажи номер телефону або Telegram username для зв'язку:",
        reply_markup=lead_cancel_keyboard(),
    )


# ── Step 2: Phone ──────────────────────────────────────────────────────────

@router.message(LeadFlow.waiting_phone)
async def lead_got_phone(message: Message, state: FSMContext):
    await state.update_data(lead_phone=message.text.strip())
    await state.set_state(LeadFlow.waiting_category)
    await message.answer(
        "Обери категорію звернення:",
        reply_markup=_category_keyboard(),
    )


# ── Step 3: Category (inline) ──────────────────────────────────────────────

@router.callback_query(F.data.startswith("lead_cat:"))
async def lead_got_category(callback: CallbackQuery, state: FSMContext):
    category = callback.data.split(":", 1)[1]
    await state.update_data(lead_category=category)
    await callback.answer()
    await state.set_state(LeadFlow.waiting_budget)
    await callback.message.answer(
        f"✅ {_category_label(category)}\n\n"
        "💰 Який приблизний бюджет?\n"
        "<i>Наприклад: до 5000 грн, 10 000–15 000 грн</i>",
        reply_markup=_skip_keyboard(),
    )


# ── Step 4: Budget ─────────────────────────────────────────────────────────

@router.message(LeadFlow.waiting_budget)
async def lead_got_budget(message: Message, state: FSMContext):
    await state.update_data(lead_budget=message.text.strip())
    await _ask_date(message, state)


@router.callback_query(F.data == "lead_skip", LeadFlow.waiting_budget)
async def lead_skip_budget(callback: CallbackQuery, state: FSMContext):
    await state.update_data(lead_budget="")
    await callback.answer()
    await _ask_date(callback.message, state)


async def _ask_date(message: Message, state: FSMContext):
    await state.set_state(LeadFlow.waiting_date)
    await message.answer(
        "📅 Яка бажана дата або період?\n"
        "<i>Наприклад: 15 травня, наступні вихідні, червень</i>",
        reply_markup=_skip_keyboard(),
    )


# ── Step 5: Date ───────────────────────────────────────────────────────────

@router.message(LeadFlow.waiting_date)
async def lead_got_date(message: Message, state: FSMContext):
    await state.update_data(lead_date=message.text.strip())
    await _ask_people(message, state)


@router.callback_query(F.data == "lead_skip", LeadFlow.waiting_date)
async def lead_skip_date(callback: CallbackQuery, state: FSMContext):
    await state.update_data(lead_date="")
    await callback.answer()
    await _ask_people(callback.message, state)


async def _ask_people(message: Message, state: FSMContext):
    await state.set_state(LeadFlow.waiting_people)
    await message.answer(
        "👥 Скільки людей?\n"
        "<i>Наприклад: 2, компанія 10 осіб, до 50</i>",
        reply_markup=_skip_keyboard(),
    )


# ── Step 6: People ─────────────────────────────────────────────────────────

@router.message(LeadFlow.waiting_people)
async def lead_got_people(message: Message, state: FSMContext):
    await state.update_data(lead_people=message.text.strip())
    await _ask_details(message, state)


@router.callback_query(F.data == "lead_skip", LeadFlow.waiting_people)
async def lead_skip_people(callback: CallbackQuery, state: FSMContext):
    await state.update_data(lead_people="")
    await callback.answer()
    await _ask_details(callback.message, state)


async def _ask_details(message: Message, state: FSMContext):
    await state.set_state(LeadFlow.waiting_details)
    await message.answer(
        "📝 Розкажи детальніше про запит\n"
        "<i>Що саме потрібно, побажання, будь-які деталі</i>",
        reply_markup=_skip_keyboard(),
    )


# ── Step 7: Details → Submit ───────────────────────────────────────────────

@router.message(LeadFlow.waiting_details)
async def lead_got_details(message: Message, state: FSMContext):
    await state.update_data(lead_details=message.text.strip())
    await _submit_lead(message, state)


@router.callback_query(F.data == "lead_skip", LeadFlow.waiting_details)
async def lead_skip_details(callback: CallbackQuery, state: FSMContext):
    await state.update_data(lead_details="")
    await callback.answer()
    await _submit_lead(callback.message, state)


async def _submit_lead(message: Message, state: FSMContext):
    data = await state.get_data()
    user = message.from_user if message.from_user else None
    # When coming from callback, from_user may be None on message obj
    # We stored user_id in state data potentially; use message.chat.id as fallback
    user_id = user.id if user else message.chat.id
    username = f"@{user.username}" if (user and user.username) else f"id:{user_id}"

    lead_name = data.get("lead_name", "—")
    lead_phone = data.get("lead_phone", "—")
    lead_category = data.get("lead_category", "other")
    lead_budget = data.get("lead_budget", "")
    lead_date = data.get("lead_date", "")
    lead_people = data.get("lead_people", "")
    lead_details = data.get("lead_details", "")

    await _save_lead(
        user_id=user_id,
        name=lead_name,
        phone=lead_phone,
        username=username,
        category=lead_category,
        details=lead_details,
        budget=lead_budget,
        date=lead_date,
        people=lead_people,
    )

    await _notify_manager(
        name=lead_name, phone=lead_phone, username=username,
        category=lead_category, details=lead_details,
        budget=lead_budget, date=lead_date, people=lead_people,
    )

    await state.clear()
    await message.answer(
        "✅ <b>Заявку прийнято!</b>\n\n"
        "Менеджер зв'яжеться з тобою найближчим часом.\n\n"
        "Чим ще можу допомогти?",
        reply_markup=main_menu_keyboard(),
    )
