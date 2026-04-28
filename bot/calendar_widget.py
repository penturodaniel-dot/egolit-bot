"""
Inline-calendar widget for aiogram 3.

Callback data format (all under 64 bytes):
  CAL:IGN          — ignore tap (past day, header, empty cell)
  CAL:G:{y}:{m}    — navigate to year/month
  CAL:D:{y}:{m}:{d} — user picked this date
"""
import calendar
from datetime import date
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

MONTHS_UA = {
    1: "Січень",   2: "Лютий",    3: "Березень", 4: "Квітень",
    5: "Травень",  6: "Червень",  7: "Липень",   8: "Серпень",
    9: "Вересень", 10: "Жовтень", 11: "Листопад", 12: "Грудень",
}
DAYS_UA = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Нд"]
IGN = "CAL:IGN"


def _prev_next(year: int, month: int):
    prev_m = month - 1 if month > 1 else 12
    prev_y = year     if month > 1 else year - 1
    next_m = month + 1 if month < 12 else 1
    next_y = year     if month < 12 else year + 1
    return prev_y, prev_m, next_y, next_m


def build_calendar(year: int, month: int) -> InlineKeyboardMarkup:
    today = date.today()
    prev_y, prev_m, next_y, next_m = _prev_next(year, month)
    can_prev = (prev_y, prev_m) >= (today.year, today.month)
    rows = []

    # ── Row 1: navigation ──────────────────────────────────────────────────
    rows.append([
        InlineKeyboardButton(
            text="◀️" if can_prev else " ",
            callback_data=f"CAL:G:{prev_y}:{prev_m}" if can_prev else IGN,
        ),
        InlineKeyboardButton(
            text=f"{MONTHS_UA[month]} {year}",
            callback_data=IGN,
        ),
        InlineKeyboardButton(
            text="▶️",
            callback_data=f"CAL:G:{next_y}:{next_m}",
        ),
    ])

    # ── Row 2: day-of-week headers ─────────────────────────────────────────
    rows.append([
        InlineKeyboardButton(text=d, callback_data=IGN) for d in DAYS_UA
    ])

    # ── Rows 3+: calendar grid ─────────────────────────────────────────────
    for week in calendar.monthcalendar(year, month):
        row = []
        for day in week:
            if day == 0:
                # Empty cell (padding)
                row.append(InlineKeyboardButton(text=" ", callback_data=IGN))
                continue

            d = date(year, month, day)
            if d < today:
                # Past — muted dot, not selectable
                row.append(InlineKeyboardButton(text="·", callback_data=IGN))
            elif d == today:
                # Today — green highlight
                row.append(InlineKeyboardButton(
                    text=f"🟢{day}",
                    callback_data=f"CAL:D:{year}:{month}:{day}",
                ))
            else:
                # Future — normal
                row.append(InlineKeyboardButton(
                    text=str(day),
                    callback_data=f"CAL:D:{year}:{month}:{day}",
                ))
        rows.append(row)

    # ── Last row: skip / cancel ────────────────────────────────────────────
    rows.append([
        InlineKeyboardButton(text="⏭ Пропустити", callback_data="lead_skip"),
        InlineKeyboardButton(text="❌ Скасувати",  callback_data="cancel_lead"),
    ])

    return InlineKeyboardMarkup(inline_keyboard=rows)
