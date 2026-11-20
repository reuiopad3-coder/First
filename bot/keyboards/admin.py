from decimal import Decimal
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from bot.database.models.order import OrderStatus


def get_admin_menu_keyboard() -> InlineKeyboardMarkup:
    """
    Главное меню панели администратора.
    """
    buttons = [
        [
            InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats"),
            InlineKeyboardButton(text="💰 Цены и наценка", callback_data="admin_pricing"),
        ],
        [
            InlineKeyboardButton(text="📦 Последние заказы", callback_data="admin_orders:0"),
            InlineKeyboardButton(text="🔍 Поиск заказа", callback_data="admin_search_order"),
        ],
        [
            InlineKeyboardButton(text="📢 Рассылка всем", callback_data="admin_broadcast"),
            InlineKeyboardButton(text="🚫 Бан / Разбан", callback_data="admin_ban_menu"),
        ],
        [
            InlineKeyboardButton(text="◀️ Выйти в главное меню", callback_data="menu_main"),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_stats_keyboard() -> InlineKeyboardMarkup:
    """
    Кнопки выбора периода статистики.
    """
    buttons = [
        [
            InlineKeyboardButton(text="📅 За сегодня", callback_data="stats_period:day"),
            InlineKeyboardButton(text="🗓 За 7 дней", callback_data="stats_period:week"),
        ],
        [
            InlineKeyboardButton(text="📆 За 30 дней", callback_data="stats_period:month"),
            InlineKeyboardButton(text="🌐 За всё время", callback_data="stats_period:all"),
        ],
        [
            InlineKeyboardButton(text="◀️ В панель админа", callback_data="admin_main"),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_pricing_keyboard() -> InlineKeyboardMarkup:
    """
    Кнопки управления ценами и наценкой.
    """
    buttons = [
        [
            InlineKeyboardButton(text="✏️ Изменить базовую цену (USDT)", callback_data="set_price_base"),
        ],
        [
            InlineKeyboardButton(text="✏️ Изменить наценку (%)", callback_data="set_price_markup"),
        ],
        [
            InlineKeyboardButton(text="◀️ В панель админа", callback_data="admin_main"),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_order_manage_keyboard(order_id: int, current_status: OrderStatus) -> InlineKeyboardMarkup:
    """
    Управление конкретным заказом: статус, возврат.
    """
    buttons = []

    # Разрешенные переходы статусов
    status_row = []
    if current_status != OrderStatus.DELIVERED:
        status_row.append(InlineKeyboardButton(text="🟢 Выдать звёзды", callback_data=f"ask_status:{order_id}:delivered"))
    if current_status != OrderStatus.FAILED:
        status_row.append(InlineKeyboardButton(text="🔴 Статус Failed", callback_data=f"ask_status:{order_id}:failed"))
    if status_row:
        buttons.append(status_row)

    if current_status != OrderStatus.REFUNDED:
        buttons.append([
            InlineKeyboardButton(text="↩️ Оформить возврат (Refund)", callback_data=f"ask_refund:{order_id}")
        ])

    buttons.append([
        InlineKeyboardButton(text="◀️ К списку заказов", callback_data="admin_orders:0"),
        InlineKeyboardButton(text="Админ-меню", callback_data="admin_main"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_confirmation_keyboard(action_tag: str, payload: str) -> InlineKeyboardMarkup:
    """
    Универсальная клавиатура подтверждения действия (Да / Нет).
    """
    buttons = [
        [
            InlineKeyboardButton(text="✅ Да, подтвердить", callback_data=f"confirm:{action_tag}:{payload}"),
            InlineKeyboardButton(text="❌ Нет, отмена", callback_data=f"cancel_act:{action_tag}:{payload}"),
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_broadcast_confirm_keyboard() -> InlineKeyboardMarkup:
    """
    Клавиатура подтверждения рассылки.
    """
    buttons = [
        [
            InlineKeyboardButton(text="🚀 Запустить рассылку", callback_data="broadcast_start"),
            InlineKeyboardButton(text="❌ Отменить", callback_data="broadcast_cancel"),
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_orders_admin_pagination_keyboard(page: int, total_pages: int) -> InlineKeyboardMarkup:
    """
    Пагинация списка заказов в админке.
    """
    buttons = []
    if total_pages > 1:
        nav = []
        if page > 0:
            nav.append(InlineKeyboardButton(text="⬅️ Назад", callback_data=f"admin_orders:{page - 1}"))
        nav.append(InlineKeyboardButton(text=f"{page + 1}/{total_pages}", callback_data="noop"))
        if page < total_pages - 1:
            nav.append(InlineKeyboardButton(text="Вперёд ➡️", callback_data=f"admin_orders:{page + 1}"))
        buttons.append(nav)

    buttons.append([
        InlineKeyboardButton(text="◀️ В панель админа", callback_data="admin_main"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)
