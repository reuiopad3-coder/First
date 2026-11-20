from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def get_orders_pagination_keyboard(current_page: int, total_pages: int) -> InlineKeyboardMarkup:
    """
    Клавиатура с пагинацией для просмотра истории заказов пользователя.
    """
    buttons = []

    if total_pages > 1:
        nav_row = []
        if current_page > 0:
            nav_row.append(
                InlineKeyboardButton(text="⬅️ Назад", callback_data=f"my_orders:{current_page - 1}")
            )

        nav_row.append(
            InlineKeyboardButton(text=f"Стр. {current_page + 1}/{total_pages}", callback_data="noop")
        )

        if current_page < total_pages - 1:
            nav_row.append(
                InlineKeyboardButton(text="Вперёд ➡️", callback_data=f"my_orders:{current_page + 1}")
            )

        buttons.append(nav_row)

    buttons.append([
        InlineKeyboardButton(text="⭐️ Купить ещё звёзд", callback_data="menu_buy"),
    ])
    buttons.append([
        InlineKeyboardButton(text="◀️ В главное меню", callback_data="menu_main"),
    ])

    return InlineKeyboardMarkup(inline_keyboard=buttons)
