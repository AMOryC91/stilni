# states.py
from aiogram.dispatcher.filters.state import State, StatesGroup

class WithdrawalState(StatesGroup):
    waiting_for_username = State()

class PromoState(StatesGroup):
    waiting_for_promo = State()

class CaptchaState(StatesGroup):
    waiting_for_captcha = State()

class RequiredChannelState(StatesGroup):
    waiting_for_subscription = State()

# НОВЫЕ СОСТОЯНИЯ
class AdminAddChannel(StatesGroup):
    waiting_for_username = State()
    waiting_for_deadline = State()
    waiting_for_max_subscribers = State()

class AdminCreateEvent(StatesGroup):
    waiting_for_name = State()
    waiting_for_type = State()
    waiting_for_multiplier = State()
    waiting_for_bonus = State()
    waiting_for_duration = State()

class AdminBanState(StatesGroup):
    waiting_for_user = State()
    waiting_for_reason = State()

class AdminSearchState(StatesGroup):
    waiting_for_query = State()