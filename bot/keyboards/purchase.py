from decimal import Decimal
from typing import Optional
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def get_packages_keyboard() -> InlineKeyboardMarkup:
    """
    Клавиатура выбора предустановленного пакета звёзд или ввода своего количества.
    """
    buttons = [
        [
            InlineKeyboardButton(text="⭐️ 50 звёзд", callback_data="buy_package:50"),
            InlineKeyboardButton(text="⭐️ 100 звёзд", callback_data="buy_package:100"),
        ],
        [
            InlineKeyboardButton(text="⭐️ 250 звёзд", callback_data="buy_package:250"),
            InlineKeyboardButton(text="⭐️ 500 звёзд", callback_data="buy_package:500"),
        ],
        [
            InlineKeyboardButton(text="⭐️ 1 000 звёзд", callback_data="buy_package:1000"),
        ],
        [
            InlineKeyboardButton(text="✏️ Ввести другое количество", callback_data="stars_custom"),
        ],
        [
            InlineKeyboardButton(text="◀️ В главное меню", callback_data="menu_main"),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_recipient_keyboard(has_username: bool, username: Optional[str] = None) -> InlineKeyboardMarkup:
    """
    Клавиатура выбора получателя звёзд: себе или другому пользователю.
    """
    buttons = []
    if has_username and username:
        buttons.append([
            InlineKeyboardButton(text=f"👤 Себе (@{username})", callback_data="recipient_self")
        ])

    buttons.append([
        InlineKeyboardButton(text="🎁 Ввести @username получателя", callback_data="recipient_custom")
    ])
    buttons.append([
        InlineKeyboardButton(text="◀️ Назад к выбору звёзд", callback_data="menu_buy")
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_confirmation_keyboard() -> InlineKeyboardMarkup:
    """
    Клавиатура предпросмотра заказа перед созданием счёта на оплату.
    """
    buttons = [
        [
            InlineKeyboardButton(text="✅ Перейти к оплате", callback_data="confirm_and_pay"),
        ],
        [
            InlineKeyboardButton(text="◀️ Выбрать заново", callback_data="menu_buy"),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_payment_keyboard(
    pay_url: str,
    order_id: int,
    total_usdt: Decimal,
) -> InlineKeyboardMarkup:
    """
    Экран подтверждения и оплаты заказа.
    """
    buttons = [
        [
            InlineKeyboardButton(text=f"💳 Оплатить {total_usdt} USDT", url=pay_url),
        ],
        [
            InlineKeyboardButton(text="🔄 Проверить оплату", callback_data=f"check_pay:{order_id}"),
        ],
        [
            InlineKeyboardButton(text="❌ Отменить заказ", callback_data=f"cancel_order:{order_id}"),
            InlineKeyboardButton(text="◀️ В меню", callback_data="menu_main"),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_cancel_custom_keyboard() -> InlineKeyboardMarkup:
    """
    Кнопка отмены ввода вручную.
    """
    buttons = [
        [
            InlineKeyboardButton(text="❌ Отмена", callback_data="menu_buy"),
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)
