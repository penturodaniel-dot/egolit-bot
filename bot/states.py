from aiogram.fsm.state import State, StatesGroup


class SearchFlow(StatesGroup):
    waiting_query = State()
    waiting_date = State()      # clarification: pick date via calendar
    waiting_category = State()  # clarification: pick event type
    waiting_budget = State()    # clarification: pick budget range


class MenuSearch(StatesGroup):
    waiting_date_pick = State()  # date picker calendar after menu button with ask_date=true


class LeadFlow(StatesGroup):
    waiting_name = State()
    waiting_phone = State()
    waiting_category = State()
    waiting_budget = State()
    waiting_date = State()
    waiting_people = State()
    waiting_details = State()
