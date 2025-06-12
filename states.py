from aiogram.fsm.state import State, StatesGroup

class InvestmentStates(StatesGroup):
    waiting_for_year = State()
    waiting_for_habits = State()
    waiting_for_currency = State()
    waiting_for_daily_cost = State()
    waiting_for_confirmation = State() 