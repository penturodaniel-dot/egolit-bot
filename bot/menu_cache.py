"""
In-memory cache for dynamic menu buttons.
Reloads from DB at startup and every CACHE_TTL seconds.
"""
from __future__ import annotations
import time
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from db.menu_buttons import MenuButton, load_all_buttons

CACHE_TTL = 30          # seconds — changes propagate within 30 sec
BACK_BUTTON = "⬅️ Назад"

_cache: list[MenuButton] = []
_loaded_at: float = 0.0


# ── Load / refresh ────────────────────────────────────────────────────────

async def reload_buttons() -> None:
    global _cache, _loaded_at
    _cache = await load_all_buttons()
    _loaded_at = time.time()


async def ensure_loaded() -> None:
    if time.time() - _loaded_at > CACHE_TTL:
        await reload_buttons()


# ── Lookups ───────────────────────────────────────────────────────────────

def _root_buttons() -> list[MenuButton]:
    return [b for b in _cache if b.parent_id is None and b.is_active]


def _children(parent_id: int) -> list[MenuButton]:
    return [b for b in _cache if b.parent_id == parent_id and b.is_active]


def find_button(display_text: str) -> MenuButton | None:
    """Find button whose display text matches exactly."""
    for b in _cache:
        if b.is_active and b.display == display_text:
            return b
    return None


def get_button_by_id(btn_id: int) -> MenuButton | None:
    """Find button by its ID (used for nav stack back-navigation)."""
    for b in _cache:
        if b.id == btn_id:
            return b
    return None


def has_children(btn_id: int) -> bool:
    return any(b.parent_id == btn_id and b.is_active for b in _cache)


# ── Keyboard builders ─────────────────────────────────────────────────────

def _buttons_to_rows(buttons: list[MenuButton]) -> list[list[KeyboardButton]]:
    """Pack buttons 2 per row (last row is single if odd count)."""
    rows = []
    for i in range(0, len(buttons), 2):
        pair = buttons[i:i + 2]
        rows.append([KeyboardButton(text=b.display) for b in pair])
    return rows


def main_menu_keyboard() -> ReplyKeyboardMarkup:
    rows = _buttons_to_rows(_root_buttons())
    return ReplyKeyboardMarkup(
        keyboard=rows,
        resize_keyboard=True,
        input_field_placeholder="Або напишіть запит вільно...",
    )


def sub_menu_keyboard(parent_id: int) -> ReplyKeyboardMarkup:
    rows = _buttons_to_rows(_children(parent_id))
    rows.append([KeyboardButton(text=BACK_BUTTON)])
    return ReplyKeyboardMarkup(
        keyboard=rows,
        resize_keyboard=True,
        input_field_placeholder="Оберіть або напишіть...",
    )
