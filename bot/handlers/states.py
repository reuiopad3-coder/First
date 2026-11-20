from aiogram.fsm.state import State, StatesGroup


class PurchaseStates(StatesGroup):
    """
    FSM-состояния процесса покупки Telegram Stars.
    """
    waiting_for_custom_stars = State()         # Ожидание ввода своего количества звёзд
    waiting_for_recipient_username = State()   # Ожидание ввода @username получателя
    confirming_order = State()                 # Экран подтверждения перед генерацией инвойса


class AdminStates(StatesGroup):
    """
    FSM-состояния панели администратора.
    """
    waiting_for_base_price = State()           # Ввод новой базовой цены за 1 звезду
    waiting_for_markup = State()               # Ввод процента наценки
    waiting_for_search_query = State()         # Ввод ID или username для поиска заказа
    waiting_for_broadcast_message = State()    # Ввод текста рассылки
    waiting_for_ban_target = State()           # Ввод ID или username для бана
    waiting_for_unban_target = State()         # Ввод ID или username для разбана
