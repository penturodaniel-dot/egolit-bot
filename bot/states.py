from aiogram.fsm.state import State, StatesGroup


class SearchFlow(StatesGroup):
    waiting_query = State()
    waiting_date = State()      # clarification: pick date via calendar
    waiting_category = State()  # clarification: pick event type
    waiting_budget = State()    # clarification: pick budget range


class LeadFlow(StatesGroup):
    waiting_name = State()
    waiting_phone = State()
    waiting_category = State()
    waiting_budget = State()
    waiting_date = State()
    waiting_people = State()
    waiting_details = State()
