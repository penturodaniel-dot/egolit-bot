from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton



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


def manager_choice_keyboard() -> InlineKeyboardMarkup:
    """Вибір: залишити заявку або живий чат з менеджером."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📝 Залишити заявку", callback_data="start_lead"),
            InlineKeyboardButton(text="💬 Живий чат",        callback_data="start_chat"),
        ],
        [InlineKeyboardButton(text="🏠 Головне меню", callback_data="main_menu")],
    ])


def lead_cancel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Скасувати", callback_data="cancel_lead")]
    ])


def back_to_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏠 Головне меню", callback_data="main_menu")]
    ])
