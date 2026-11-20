import logging
import re
from decimal import Decimal
from aiogram import F, Router
from aiogram.filters import Command, CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import settings
from bot.database.crud import order as order_crud
from bot.database.crud import setting as setting_crud
from bot.database.models.order import Order, OrderStatus
from bot.database.models.user import User
from bot.handlers.states import PurchaseStates
from bot.keyboards import (
    get_back_to_menu_keyboard,
    get_cancel_custom_keyboard,
    get_confirmation_keyboard,
    get_main_menu_keyboard,
    get_orders_pagination_keyboard,
    get_packages_keyboard,
    get_payment_keyboard,
    get_recipient_keyboard,
)
from bot.services.orders import OrderService

logger = logging.getLogger(__name__)

router = Router(name="user_router")

USERNAME_REGEX = re.compile(r"^[a-zA-Z0-9_]{4,32}$")


# ==============================================================================
# Главное меню и инфо-разделы
# ==============================================================================

@router.message(CommandStart())
async def handle_start(message: Message, user: User, session: AsyncSession, state: FSMContext) -> None:
    """
    Команда /start: приветствие, текущий курс и главное меню.
    """
    await state.clear()
    base_price, markup = await setting_crud.get_current_pricing(session)
    price_100 = (Decimal(100) * base_price * (Decimal("1") + markup / Decimal("100"))).quantize(Decimal("0.01"))

    text = (
        f"👋 Привет, <b>{user.first_name or 'пользователь'}</b>!\n\n"
        f"⭐️ Здесь вы можете быстро и безопасно купить <b>Telegram Stars</b> с автоматической выдачей.\n\n"
        f"📊 <b>Текущий курс:</b> 100 ⭐️ ≈ <b>{price_100} USDT</b>\n"
        f"💳 Оплата через <b>CryptoBot</b> (USDT / TON / BTC)\n\n"
        f"Выберите действие в меню:"
    )
    await message.answer(text, reply_markup=get_main_menu_keyboard())


@router.callback_query(F.data == "menu_main")
async def handle_menu_main(callback: CallbackQuery, user: User, session: AsyncSession, state: FSMContext) -> None:
    """
    Возврат в главное меню.
    """
    await state.clear()
    base_price, markup = await setting_crud.get_current_pricing(session)
    price_100 = (Decimal(100) * base_price * (Decimal("1") + markup / Decimal("100"))).quantize(Decimal("0.01"))

    text = (
        f"👋 Привет, <b>{user.first_name or 'пользователь'}</b>!\n\n"
        f"⭐️ Здесь вы можете купить <b>Telegram Stars</b> с автоматической доставкой.\n\n"
        f"📊 <b>Текущий курс:</b> 100 ⭐️ ≈ <b>{price_100} USDT</b>\n"
        f"💳 Оплата через <b>CryptoBot</b>\n\n"
        f"Выберите действие:"
    )
    try:
        await callback.message.edit_text(text, reply_markup=get_main_menu_keyboard())
    except Exception:
        await callback.message.answer(text, reply_markup=get_main_menu_keyboard())
    await callback.answer()


@router.callback_query(F.data == "menu_support")
async def handle_menu_support(callback: CallbackQuery) -> None:
    """
    Раздел поддержки.
    """
    text = (
        f"💬 <b>Служба поддержки</b>\n\n"
        f"Если у вас возникли вопросы по оплате или получению звёзд, "
        f"напишите нашему оператору:\n"
        f"👉 <b>{settings.SUPPORT_USERNAME}</b>\n\n"
        f"Время ответа: обычно в течение 10–15 минут."
    )
    await callback.message.edit_text(text, reply_markup=get_back_to_menu_keyboard())
    await callback.answer()


@router.callback_query(F.data == "menu_faq")
async def handle_menu_faq(callback: CallbackQuery) -> None:
    """
    Раздел FAQ и отзывы.
    """
    text = (
        f"📖 <b>Отзывы и часто задаваемые вопросы</b>\n\n"
        f"<b>1. Как быстро приходят звёзды?</b>\n"
        f"Звёзды начисляются автоматически сразу после подтверждения транзакции платёжной системой (1–2 минуты).\n\n"
        f"<b>2. Можно ли отправить звёзды другу?</b>\n"
        f"Да, при оформлении заказа просто укажите его @username.\n\n"
        f"<b>3. Что делать, если платёж прошёл, а звёзды не поступили?</b>\n"
        f"Заказ никуда не пропадёт. Нажмите «Проверить оплату» или напишите в поддержку {settings.SUPPORT_USERNAME}.\n\n"
        f"⭐️ <b>Канал с отзывами:</b> {settings.REVIEWS_URL}"
    )
    await callback.message.edit_text(text, reply_markup=get_back_to_menu_keyboard())
    await callback.answer()


# ==============================================================================
# Сценарий покупки звёзд (FSM)
# ==============================================================================

@router.callback_query(F.data == "menu_buy")
async def handle_start_purchase(callback: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    """
    Старт покупки: выбор пакета или ввод своего количества.
    """
    await state.clear()
    base_price, markup = await setting_crud.get_current_pricing(session)
    effective_rate = (base_price * (Decimal("1") + markup / Decimal("100"))).quantize(Decimal("0.0001"))

    text = (
        f"⭐️ <b>Покупка Telegram Stars</b>\n\n"
        f"Курс: <b>1 ⭐️ = {effective_rate} USDT</b>\n"
        f"Выберите готовый пакет звёзд или укажите своё количество (от {settings.MIN_STARS} до {settings.MAX_STARS}):"
    )
    await callback.message.edit_text(text, reply_markup=get_packages_keyboard())
    await callback.answer()


@router.callback_query(F.data.startswith("buy_package:"))
async def handle_package_selected(callback: CallbackQuery, user: User, state: FSMContext) -> None:
    """
    Выбран предустановленный пакет (50, 100, 250, 500, 1000).
    """
    package_val = callback.data.split(":")[1]
    stars_amount = int(package_val)

    await state.update_data(stars_amount=stars_amount)

    has_username = bool(user.username)
    text = (
        f"⭐️ Выбрано: <b>{stars_amount} звёзд</b>\n\n"
        f"👤 <b>Кому доставить звёзды?</b>\n"
        f"Вы можете получить их на свой профиль или отправить в подарок по @username:"
    )
    await callback.message.edit_text(
        text,
        reply_markup=get_recipient_keyboard(has_username=has_username, username=user.username),
    )
    await callback.answer()


@router.callback_query(F.data == "stars_custom")
async def handle_custom_stars_prompt(callback: CallbackQuery, state: FSMContext) -> None:
    """
    Запрос на ввод произвольного количества звёзд.
    """
    await state.set_state(PurchaseStates.waiting_for_custom_stars)
    text = (
        f"✏️ <b>Введите количество звёзд</b>\n\n"
        f"Число должно быть целым, от <b>{settings.MIN_STARS}</b> до <b>{settings.MAX_STARS}</b>.\n"
        f"Отправьте число в ответном сообщении:"
    )
    await callback.message.edit_text(text, reply_markup=get_cancel_custom_keyboard())
    await callback.answer()


@router.message(PurchaseStates.waiting_for_custom_stars)
async def handle_custom_stars_input(message: Message, user: User, state: FSMContext) -> None:
    """
    Обработка введённого пользователем количества звёзд.
    """
    raw_text = message.text.strip() if message.text else ""
    if not raw_text.isdigit():
        await message.answer(
            f"⚠️ Пожалуйста, введите корректное целое число от {settings.MIN_STARS} до {settings.MAX_STARS}:",
            reply_markup=get_cancel_custom_keyboard(),
        )
        return

    amount = int(raw_text)
    if amount < settings.MIN_STARS or amount > settings.MAX_STARS:
        await message.answer(
            f"⚠️ Количество должно быть от <b>{settings.MIN_STARS}</b> до <b>{settings.MAX_STARS}</b> звёзд. Попробуйте ещё раз:",
            reply_markup=get_cancel_custom_keyboard(),
        )
        return

    await state.update_data(stars_amount=amount)

    has_username = bool(user.username)
    text = (
        f"⭐️ Выбрано: <b>{amount} звёзд</b>\n\n"
        f"👤 <b>Кому доставить звёзды?</b>\n"
        f"Вы можете получить их на свой профиль или отправить в подарок по @username:"
    )
    await message.answer(
        text,
        reply_markup=get_recipient_keyboard(has_username=has_username, username=user.username),
    )


@router.callback_query(F.data == "recipient_self")
async def handle_recipient_self(callback: CallbackQuery, user: User, session: AsyncSession, state: FSMContext) -> None:
    """
    Получатель - сам пользователь.
    """
    if not user.username:
        await callback.answer("⚠️ У вашего аккаунта не задан @username в настройках Telegram.", show_alert=True)
        return

    await state.update_data(recipient=user.username)
    await show_order_confirmation(callback, session, state)
    await callback.answer()


@router.callback_query(F.data == "recipient_custom")
async def handle_recipient_custom_prompt(callback: CallbackQuery, state: FSMContext) -> None:
    """
    Запрос на ввод чужого @username.
    """
    await state.set_state(PurchaseStates.waiting_for_recipient_username)
    text = (
        f"🎁 <b>Ввод получателя</b>\n\n"
        f"Введите Telegram <b>@username</b> получателя (например, <code>@durov</code>):"
    )
    await callback.message.edit_text(text, reply_markup=get_cancel_custom_keyboard())
    await callback.answer()


@router.message(PurchaseStates.waiting_for_recipient_username)
async def handle_recipient_custom_input(message: Message, session: AsyncSession, state: FSMContext) -> None:
    """
    Валидация введённого @username.
    """
    raw_input = (message.text or "").strip().lstrip("@")

    if not USERNAME_REGEX.match(raw_input):
        await message.answer(
            "⚠️ <b>Некорректный username.</b>\n"
            "Имя пользователя должно содержать от 4 до 32 символов (латинские буквы, цифры и символ подчёркивания).\n"
            "Попробуйте ещё раз:",
            reply_markup=get_cancel_custom_keyboard(),
        )
        return

    await state.update_data(recipient=raw_input)
    await show_order_confirmation(message, session, state)


async def show_order_confirmation(
    event: Message | CallbackQuery,
    session: AsyncSession,
    state: FSMContext,
) -> None:
    """
    Экран подтверждения параметров заказа перед генерацией счёта.
    """
    data = await state.get_data()
    stars_amount = data.get("stars_amount", 100)
    recipient = data.get("recipient", "username")

    base_price, markup = await setting_crud.get_current_pricing(session)
    total_usdt = (
        Decimal(stars_amount) * base_price * (Decimal("1") + markup / Decimal("100"))
    ).quantize(Decimal("0.01"))

    await state.update_data(total_usdt=str(total_usdt))
    await state.set_state(PurchaseStates.confirming_order)

    text = (
        f"📋 <b>Подтверждение заказа</b>\n\n"
        f"⭐️ Товар: <b>{stars_amount} Telegram Stars</b>\n"
        f"👤 Получатель: <b>@{recipient}</b>\n"
        f"💵 Сумма к оплате: <b>{total_usdt} USDT</b>\n\n"
        f"Нажмите <b>«Перейти к оплате»</b>, чтобы создать счёт в CryptoBot. Счёт будет действовать 15 минут."
    )

    if isinstance(event, CallbackQuery):
        await event.message.edit_text(text, reply_markup=get_confirmation_keyboard())
    else:
        await event.answer(text, reply_markup=get_confirmation_keyboard())


# ==============================================================================
# Создание счёта в CryptoBot и защита от двойного нажатия
# ==============================================================================

@router.callback_query(F.data == "confirm_and_pay")
async def handle_confirm_and_pay(
    callback: CallbackQuery,
    user: User,
    session: AsyncSession,
    state: FSMContext,
) -> None:
    """
    Генерация счёта в CryptoBot.
    Защита от двойного нажатия: состояние мгновенно сбрасывается.
    """
    current_state = await state.get_state()
    if current_state != PurchaseStates.confirming_order.state:
        # Защита от повторного клика
        await callback.answer("⚠️ Счёт уже формируется или был создан.", show_alert=True)
        return

    data = await state.get_data()
    # Сбрасываем состояние FSM сразу, чтобы исключить повторное нажатие
    await state.clear()

    stars_amount = data.get("stars_amount")
    recipient = data.get("recipient")

    if not stars_amount or not recipient:
        await callback.answer("⚠️ Данные заказа устарели. Начните выбор заново.", show_alert=True)
        return

    # Показываем уведомление пользователю о генерации инвойса
    await callback.answer("Создаём счёт в CryptoBot...", show_alert=False)

    order_service = OrderService(session=session, bot=callback.bot)
    try:
        order = await order_service.create_new_order(
            user_id=user.id,
            recipient_username=recipient,
            stars_amount=stars_amount,
        )
    except Exception as e:
        logger.error("Ошибка при создании заказа для пользователя %s: %s", user.id, e)
        await callback.message.edit_text(
            "❌ <b>Ошибка платёжного сервиса</b>\n\n"
            "Не удалось связаться с платёжной системой CryptoBot. Пожалуйста, попробуйте позже.",
            reply_markup=get_back_to_menu_keyboard(),
        )
        return

    text = (
        f"🧾 <b>Счёт на оплату #{order.id}</b>\n\n"
        f"⭐️ Товар: <b>{order.stars_amount} Telegram Stars</b>\n"
        f"👤 Получатель: <b>@{order.recipient_username}</b>\n"
        f"💳 Сумма к оплате: <b>{order.total_price_usdt} USDT</b>\n"
        f"⏳ Срок действия счёта: <b>15 минут</b>\n\n"
        f"1. Нажмите кнопку <b>«Оплатить»</b> ниже для перехода в CryptoBot.\n"
        f"2. После оплаты звёзды будут начислены автоматически, либо нажмите <b>«Проверить оплату»</b>."
    )
    await callback.message.edit_text(
        text,
        reply_markup=get_payment_keyboard(
            pay_url=order.payment_url or "",
            order_id=order.id,
            total_usdt=order.total_price_usdt,
        ),
    )


# ==============================================================================
# Проверка оплаты, отмена заказа и обработка старых кнопок
# ==============================================================================

@router.callback_query(F.data.startswith("check_pay:"))
async def handle_check_payment(callback: CallbackQuery, session: AsyncSession) -> None:
    """
    Ручная проверка оплаты пользователем по кнопке.
    Безопасная обработка любых устаревших или повреждённых ID.
    """
    raw_id = callback.data.split(":")[1]
    if not raw_id.isdigit():
        await callback.answer("⚠️ Некорректный номер заказа.", show_alert=True)
        return

    order_id = int(raw_id)
    order = await order_crud.get_order_by_id(session, order_id)
    if not order:
        await callback.answer("⚠️ Заказ не найден (возможно, удалён).", show_alert=True)
        return

    # 1. Если заказ уже доставлен
    if order.status == OrderStatus.DELIVERED:
        await callback.answer("⭐️ Заказ уже выполнен! Звёзды начислены.", show_alert=True)
        await callback.message.edit_text(
            f"✅ <b>Заказ #{order.id} успешно выполнен!</b>\n\n"
            f"⭐️ Начислено: <b>{order.stars_amount}</b> звёзд\n"
            f"👤 Получатель: <b>@{order.recipient_username}</b>\n"
            f"Спасибо за покупку!",
            reply_markup=get_back_to_menu_keyboard(),
        )
        return

    # 2. Если заказ истёк по таймауту
    if order.status == OrderStatus.EXPIRED:
        await callback.answer("⌛ Срок действия счёта истёк. Звёзды не выданы.", show_alert=True)
        await callback.message.edit_text(
            f"⌛ <b>Заказ #{order.id} закрыт (истёк срок оплаты)</b>\n\n"
            f"Счёт на оплату был активен 15 минут. Звёзды не списывались и не выдавались.\n"
            f"Вы можете создать новый заказ в любое удобное время.",
            reply_markup=get_back_to_menu_keyboard(),
        )
        return

    # 3. Если заказ отменён
    if order.status == OrderStatus.CANCELED:
        await callback.answer("❌ Этот заказ был отменён.", show_alert=True)
        return

    # 4. Проверяем платёж через OrderService
    order_service = OrderService(session=session, bot=callback.bot)
    try:
        success, err_reason = await order_service.check_and_process_payment(order.id)
    except Exception as e:
        logger.error("Ошибка при ручной проверке оплаты заказа #%s: %s", order.id, e)
        await callback.answer("⚠️ Ошибка проверки счёта. Попробуйте ещё раз через 10 секунд.", show_alert=True)
        return

    if success:
        await callback.answer("⭐️ Оплата подтверждена! Звёзды успешно начислены.", show_alert=True)
        await callback.message.edit_text(
            f"✅ <b>Заказ #{order.id} успешно оплачен и выполнен!</b>\n\n"
            f"⭐️ Начислено: <b>{order.stars_amount}</b> звёзд\n"
            f"👤 Получатель: <b>@{order.recipient_username}</b>\n"
            f"Спасибо, что выбрали наш сервис!",
            reply_markup=get_back_to_menu_keyboard(),
        )
    else:
        # Проверяем, не перешёл ли статус в EXPIRED в ходе проверки
        refreshed_order = await order_crud.get_order_by_id(session, order.id)
        if refreshed_order and refreshed_order.status == OrderStatus.EXPIRED:
            await callback.answer("⌛ Время оплаты истекло (15 минут).", show_alert=True)
            await callback.message.edit_text(
                f"⌛ <b>Срок оплаты заказа #{order.id} истёк</b>\n\n"
                f"Счёт закрыт. Создайте новый заказ через меню.",
                reply_markup=get_back_to_menu_keyboard(),
            )
        else:
            await callback.answer("⏳ Оплата ещё не поступила. Попробуйте через несколько секунд.", show_alert=True)


@router.callback_query(F.data.startswith("cancel_order:"))
async def handle_cancel_order(callback: CallbackQuery, session: AsyncSession) -> None:
    """
    Отмена неоплаченного заказа пользователем.
    """
    raw_id = callback.data.split(":")[1]
    if not raw_id.isdigit():
        await callback.answer("⚠️ Некорректный номер заказа.", show_alert=True)
        return

    order_id = int(raw_id)
    order = await order_crud.get_order_by_id(session, order_id)
    if not order:
        await callback.answer("⚠️ Заказ не найден.", show_alert=True)
        return

    if order.status != OrderStatus.CREATED:
        await callback.answer(f"⚠️ Нельзя отменить заказ со статусом {order.status.value}.", show_alert=True)
        return

    await order_crud.update_order_status(session, order.id, status=OrderStatus.CANCELED)
    await callback.answer("Заказ отменён.", show_alert=False)
    await callback.message.edit_text(
        f"❌ <b>Заказ #{order.id} успешно отменён.</b>\n"
        f"Вы можете оформить новый заказ в любое время.",
        reply_markup=get_back_to_menu_keyboard(),
    )


# ==============================================================================
# Мои заказы (История заказов с пагинацией)
# ==============================================================================

STATUS_EMOJIS = {
    OrderStatus.CREATED: "🟡 Ожидает оплаты",
    OrderStatus.PAID: "🔵 Оплачен (доставляется)",
    OrderStatus.DELIVERED: "🟢 Выполнен",
    OrderStatus.FAILED: "🔴 Ошибка (в обработке)",
    OrderStatus.REFUNDED: "🟣 Возврат средств",
    OrderStatus.EXPIRED: "⚫ Срок счёта истёк",
    OrderStatus.CANCELED: "⚪ Отменён",
}


@router.callback_query(F.data.startswith("my_orders:"))
async def handle_my_orders(callback: CallbackQuery, user: User, session: AsyncSession) -> None:
    """
    Просмотр истории заказов пользователя с пагинацией.
    """
    raw_page = callback.data.split(":")[1]
    page = int(raw_page) if raw_page.isdigit() else 0
    limit = 5
    offset = page * limit

    orders, total_count = await order_crud.get_user_orders(session, user_id=user.id, limit=limit, offset=offset)

    if not orders:
        await callback.message.edit_text(
            "📦 <b>История заказов</b>\n\n"
            "У вас пока нет оформленных заказов.\n"
            "Нажмите «Купить звёзды», чтобы сделать первый заказ!",
            reply_markup=get_back_to_menu_keyboard(),
        )
        await callback.answer()
        return

    total_pages = (total_count + limit - 1) // limit

    lines = [f"📦 <b>Ваши заказы (Всего: {total_count})</b>\n"]
    for ord_item in orders:
        status_text = STATUS_EMOJIS.get(ord_item.status, ord_item.status.value)
        dt_str = ord_item.created_at.strftime("%d.%m.%Y %H:%M") if ord_item.created_at else ""
        lines.append(
            f"<b>Заказ #{ord_item.id}</b> от {dt_str}\n"
            f"⭐️ <b>{ord_item.stars_amount}</b> звёзд для @{ord_item.recipient_username}\n"
            f"💵 {ord_item.total_price_usdt} USDT | {status_text}\n"
        )

    text = "\n".join(lines)
    await callback.message.edit_text(
        text,
        reply_markup=get_orders_pagination_keyboard(current_page=page, total_pages=total_pages),
    )
    await callback.answer()


@router.callback_query(F.data == "noop")
async def handle_noop(callback: CallbackQuery) -> None:
    """Заглушка для инфо-кнопок пагинации."""
    await callback.answer()
