from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton


def main_menu_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🎉 Організація свята"),   KeyboardButton(text="📸 Фото та відео")],
            [KeyboardButton(text="🎭 Аніматори та шоу"),    KeyboardButton(text="🌸 Декор та флористи")],
            [KeyboardButton(text="📅 Найближчі події"),     KeyboardButton(text="✍️ Свій запит")],
            [KeyboardButton(text="📞 Поговорити з менеджером")],
        ],
        resize_keyboard=True,
        input_field_placeholder="Або напишіть запит вільно...",
    )


def results_keyboard(has_more: bool = True) -> InlineKeyboardMarkup:
    buttons = []
    if has_more:
        buttons.append([InlineKeyboardButton(text="🔄 Ще варіанти", callback_data="more_results")])
    buttons.append([
        InlineKeyboardButton(text="📝 Залишити заявку", callback_data="start_lead"),
        InlineKeyboardButton(text="👨‍💼 Менеджер",         callback_data="call_manager"),
    ])
    buttons.append([InlineKeyboardButton(text="🏠 Головне меню", callback_data="main_menu")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def lead_cancel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Скасувати", callback_data="cancel_lead")]
    ])


def back_to_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏠 Головне меню", callback_data="main_menu")]
    ])
