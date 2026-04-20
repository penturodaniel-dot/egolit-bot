from aiogram.fsm.state import State, StatesGroup


class SearchFlow(StatesGroup):
    waiting_query = State()


class LeadFlow(StatesGroup):
    waiting_name = State()
    waiting_phone = State()
    waiting_details = State()
