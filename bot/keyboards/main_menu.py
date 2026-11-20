from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from bot.config import settings


def get_main_menu_keyboard() -> InlineKeyboardMarkup:
    """
    Главное меню бота.
    """
    buttons = [
        [
            InlineKeyboardButton(text="⭐️ Купить звёзды", callback_data="menu_buy"),
        ],
        [
            InlineKeyboardButton(text="📦 Мои заказы", callback_data="my_orders:0"),
            InlineKeyboardButton(text="💬 Поддержка", callback_data="menu_support"),
        ],
        [
            InlineKeyboardButton(text="📖 Отзывы и FAQ", callback_data="menu_faq"),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_back_to_menu_keyboard() -> InlineKeyboardMarkup:
    """
    Кнопка быстрого возврата в главное меню.
    """
    buttons = [
        [
            InlineKeyboardButton(text="◀️ В главное меню", callback_data="menu_main"),
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)
