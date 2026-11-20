import asyncio
import logging
import time
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional

from aiogram import F, Router
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import settings
from bot.database.crud import order as order_crud
from bot.database.crud import setting as setting_crud
from bot.database.crud import user as user_crud
from bot.database.models.order import Order, OrderStatus
from bot.filters.admin import IsAdminFilter
from bot.handlers.states import AdminStates
from bot.keyboards.admin import (
    get_admin_menu_keyboard,
    get_broadcast_confirm_keyboard,
    get_confirmation_keyboard,
    get_order_manage_keyboard,
    get_orders_admin_pagination_keyboard,
    get_pricing_keyboard,
    get_stats_keyboard,
)

logger = logging.getLogger(__name__)

router = Router(name="admin_router")

# Защита всего роутера: только для администраторов из settings.ADMIN_IDS
router.message.filter(IsAdminFilter())
router.callback_query.filter(IsAdminFilter())


# ==============================================================================
# Главное меню админки
# ==============================================================================

@router.message(Command("admin"))
async def handle_admin_command(message: Message, state: FSMContext) -> None:
    """
    Команда /admin: открытие панели администратора.
    """
    await state.clear()
    text = (
        "🔐 <b>Панель администратора</b>\n\n"
        "Выберите интересующий раздел:"
    )
    await message.answer(text, reply_markup=get_admin_menu_keyboard())


@router.callback_query(F.data == "admin_main")
async def handle_admin_main_callback(callback: CallbackQuery, state: FSMContext) -> None:
    """
    Возврат в главное меню панели администратора.
    """
    await state.clear()
    text = (
        "🔐 <b>Панель администратора</b>\n\n"
        "Выберите раздел:"
    )
    try:
        await callback.message.edit_text(text, reply_markup=get_admin_menu_keyboard())
    except Exception:
        await callback.message.answer(text, reply_markup=get_admin_menu_keyboard())
    await callback.answer()


# ==============================================================================
# Статистика (День / Неделя / Месяц / Всё время)
# ==============================================================================

@router.callback_query(F.data == "admin_stats")
async def handle_admin_stats_menu(callback: CallbackQuery) -> None:
    """
    Меню выбора периода для просмотра статистики.
    """
    text = "📊 <b>Статистика сервиса</b>\n\nВыберите период для отчёта:"
    await callback.message.edit_text(text, reply_markup=get_stats_keyboard())
    await callback.answer()


@router.callback_query(F.data.startswith("stats_period:"))
async def handle_stats_period(callback: CallbackQuery, session: AsyncSession) -> None:
    """
    Вывод агрегированной статистики за выбранный период.
    """
    period = callback.data.split(":")[1]
    now_utc = datetime.now(timezone.utc)
    since_dt: Optional[datetime] = None
    period_title = "За всё время"

    if period == "day":
        since_dt = now_utc - timedelta(days=1)
        period_title = "За последние 24 часа"
    elif period == "week":
        since_dt = now_utc - timedelta(days=7)
        period_title = "За последние 7 дней"
    elif period == "month":
        since_dt = now_utc - timedelta(days=30)
        period_title = "За последние 30 дней"

    stats = await order_crud.get_orders_stats(session, since=since_dt)
    total_users = await user_crud.count_total_users(session)

    text = (
        f"📊 <b>Отчёт по заказам ({period_title})</b>\n\n"
        f"👥 Всего пользователей: <b>{total_users}</b>\n\n"
        f"📦 Создано заказов: <b>{stats['total_orders']}</b>\n"
        f"💵 Общий оборот: <b>{stats['total_revenue']} USDT</b>\n"
        f"⭐️ Всего звёзд в заказах: <b>{stats['total_stars']}</b>\n\n"
        f"✅ Успешно доставлено: <b>{stats['delivered_orders']}</b>\n"
        f"💰 Оплаченная выручка: <b>{stats['delivered_revenue']} USDT</b>"
    )
    await callback.message.edit_text(text, reply_markup=get_stats_keyboard())
    await callback.answer()


# ==============================================================================
# Управление ценообразованием (/setprice и инлайн-меню)
# ==============================================================================

@router.callback_query(F.data == "admin_pricing")
async def handle_admin_pricing_menu(callback: CallbackQuery, session: AsyncSession) -> None:
    """
    Просмотр текущих цен и наценки.
    """
    base_price, markup = await setting_crud.get_current_pricing(session)
    effective_rate = (base_price * (Decimal("1") + markup / Decimal("100"))).quantize(Decimal("0.0001"))

    text = (
        f"💰 <b>Настройки ценообразования</b>\n\n"
        f"🔹 Базовая себестоимость 1 ⭐️: <b>{base_price} USDT</b>\n"
        f"🔹 Наценка: <b>{markup}%</b>\n"
        f"🔹 Итоговая цена для клиента: <b>{effective_rate} USDT</b> за 1 ⭐️\n"
        f"   (100 ⭐️ = <b>{(effective_rate * 100).quantize(Decimal('0.01'))} USDT</b>)\n\n"
        f"Выберите параметр для изменения:"
    )
    await callback.message.edit_text(text, reply_markup=get_pricing_keyboard())
    await callback.answer()


@router.callback_query(F.data == "set_price_base")
async def handle_ask_base_price(callback: CallbackQuery, state: FSMContext) -> None:
    """
    Запрос новой базовой цены.
    """
    await state.set_state(AdminStates.waiting_for_base_price)
    text = (
        "✏️ <b>Введите новую базовую себестоимость 1 звезды в USDT</b>\n\n"
        "Пример: <code>0.0180</code>\n"
        "(Допустимый диапазон: от 0.0001 до 1.0000 USDT):"
    )
    await callback.message.edit_text(text, reply_markup=get_pricing_keyboard())
    await callback.answer()


@router.message(AdminStates.waiting_for_base_price)
async def handle_save_base_price(message: Message, session: AsyncSession, state: FSMContext) -> None:
    """
    Валидация и сохранение новой базовой цены.
    """
    raw_val = (message.text or "").strip().replace(",", ".")
    try:
        new_price = Decimal(raw_val)
    except Exception:
        await message.answer("⚠️ Введите корректное положительное десятичное число (например: <code>0.018</code>):")
        return

    if new_price <= Decimal("0.0") or new_price > Decimal("1.0"):
        await message.answer("⚠️ Цена должна быть больше 0 и не превышать 1.0 USDT за звезду. Попробуйте ещё раз:")
        return

    old_price, current_markup = await setting_crud.get_current_pricing(session)
    await setting_crud.update_pricing(session, base_price=new_price)
    await state.clear()

    logger.info("Администратор %s изменил базовую цену с %s на %s USDT", message.from_user.id, old_price, new_price)
    await message.answer(
        f"✅ <b>Базовая цена успешно обновлена!</b>\n\n"
        f"Старое значение: <code>{old_price} USDT</code>\n"
        f"Новое значение: <b>{new_price} USDT</b>",
        reply_markup=get_admin_menu_keyboard(),
    )


@router.callback_query(F.data == "set_price_markup")
async def handle_ask_markup(callback: CallbackQuery, state: FSMContext) -> None:
    """
    Запрос нового процента наценки.
    """
    await state.set_state(AdminStates.waiting_for_markup)
    text = (
        "✏️ <b>Введите новый процент наценки (%)</b>\n\n"
        "Пример: <code>15.0</code> или <code>20</code>\n"
        "(Допустимый диапазон: от 0.0% до 500.0%):"
    )
    await callback.message.edit_text(text, reply_markup=get_pricing_keyboard())
    await callback.answer()


@router.message(AdminStates.waiting_for_markup)
async def handle_save_markup(message: Message, session: AsyncSession, state: FSMContext) -> None:
    """
    Валидация и сохранение процента наценки.
    """
    raw_val = (message.text or "").strip().replace(",", ".")
    try:
        new_markup = Decimal(raw_val)
    except Exception:
        await message.answer("⚠️ Введите корректное число процентов (например: <code>15.5</code>):")
        return

    if new_markup < Decimal("0.0") or new_markup > Decimal("500.0"):
        await message.answer("⚠️ Наценка должна быть от 0% до 500%. Попробуйте ещё раз:")
        return

    current_base, old_markup = await setting_crud.get_current_pricing(session)
    await setting_crud.update_pricing(session, markup_percent=new_markup)
    await state.clear()

    logger.info("Администратор %s изменил наценку с %s%% на %s%%", message.from_user.id, old_markup, new_markup)
    await message.answer(
        f"✅ <b>Наценка успешно обновлена!</b>\n\n"
        f"Старое значение: <code>{old_markup}%</code>\n"
        f"Новое значение: <b>{new_markup}%</b>",
        reply_markup=get_admin_menu_keyboard(),
    )


@router.message(Command("setprice"))
async def handle_setprice_command(message: Message, session: AsyncSession) -> None:
    """
    Быстрая команда: /setprice <базовая_цена> [наценка_%]
    Пример: /setprice 0.018 15
    """
    parts = (message.text or "").strip().split()
    if len(parts) < 2:
        await message.answer(
            "⚠️ <b>Использование:</b> <code>/setprice &lt;цена&gt; [наценка_%]</code>\n"
            "Пример: <code>/setprice 0.0180 15</code>"
        )
        return

    try:
        new_base = Decimal(parts[1].replace(",", "."))
        if new_base <= Decimal("0.0") or new_base > Decimal("1.0"):
            await message.answer("⚠️ Цена за звезду должна быть от 0.0001 до 1.0 USDT.")
            return
    except Exception:
        await message.answer("⚠️ Некорректный формат базовой цены.")
        return

    new_markup = None
    if len(parts) >= 3:
        try:
            new_markup = Decimal(parts[2].replace(",", "."))
            if new_markup < Decimal("0.0") or new_markup > Decimal("500.0"):
                await message.answer("⚠️ Наценка должна быть от 0 до 500%.")
                return
        except Exception:
            await message.answer("⚠️ Некорректный формат наценки.")
            return

    old_base, old_markup = await setting_crud.get_current_pricing(session)
    await setting_crud.update_pricing(session, base_price=new_base, markup_percent=new_markup)

    res_lines = [
        "✅ <b>Цены успешно обновлены!</b>\n",
        f"🔹 Базовая цена: <code>{old_base}</code> ➔ <b>{new_base} USDT</b>",
    ]
    if new_markup is not None:
        res_lines.append(f"🔹 Наценка: <code>{old_markup}%</code> ➔ <b>{new_markup}%</b>")

    await message.answer("\n".join(res_lines), reply_markup=get_admin_menu_keyboard())


# ==============================================================================
# Управление заказами, поиск и ручная смена статусов
# ==============================================================================

@router.callback_query(F.data.startswith("admin_orders:"))
async def handle_admin_orders_list(callback: CallbackQuery, session: AsyncSession) -> None:
    """
    Список последних заказов с пагинацией.
    """
    raw_page = callback.data.split(":")[1]
    page = int(raw_page) if raw_page.isdigit() else 0
    limit = 5
    offset = page * limit

    from sqlalchemy import select, func
    count_stmt = select(func.count(Order.id))
    total_count = (await session.execute(count_stmt)).scalar_one() or 0

    orders_stmt = select(Order).order_by(Order.id.desc()).limit(limit).offset(offset)
    orders = list((await session.execute(orders_stmt)).scalars().all())

    if not orders:
        await callback.message.edit_text("📦 В базе данных пока нет заказов.", reply_markup=get_admin_menu_keyboard())
        await callback.answer()
        return

    total_pages = (total_count + limit - 1) // limit

    lines = [f"📦 <b>Последние заказы (Стр. {page + 1}/{total_pages}, всего: {total_count})</b>\n"]
    for ord_item in orders:
        lines.append(
            f"<b>Заказ #{ord_item.id}</b> | <code>{ord_item.status.value}</code>\n"
            f"⭐️ {ord_item.stars_amount} для @{ord_item.recipient_username} | {ord_item.total_price_usdt} USDT\n"
            f"Управление: /order_{ord_item.id}\n"
        )

    await callback.message.edit_text(
        "\n".join(lines),
        reply_markup=get_orders_admin_pagination_keyboard(page, total_pages),
    )
    await callback.answer()


@router.message(F.text.regexp(r"^/order_(\d+)$"))
async def handle_order_view_command(message: Message, session: AsyncSession) -> None:
    """
    Просмотр подробной информации о заказе: /order_<ID>
    """
    match = F.text.regexp(r"^/order_(\d+)$").resolve(message)
    order_id = int(message.text.split("_")[1])
    order = await order_crud.get_order_by_id(session, order_id)
    if not order:
        await message.answer(f"⚠️ Заказ #{order_id} не найден.")
        return

    created_str = order.created_at.strftime("%d.%m.%Y %H:%M:%S") if order.created_at else "-"
    text = (
        f"📦 <b>Информация о заказе #{order.id}</b>\n\n"
        f"👤 Покупатель (ID): <code>{order.user_id}</code>\n"
        f"🎁 Получатель: <b>@{order.recipient_username}</b>\n"
        f"⭐️ Количество звёзд: <b>{order.stars_amount}</b>\n"
        f"💵 Сумма к оплате: <b>{order.total_price_usdt} USDT</b>\n"
        f"📊 Текущий статус: <b>{order.status.value}</b>\n"
        f"💳 Invoice ID: <code>{order.payment_id or '-'}</code>\n"
        f"🚀 TX Provider ID: <code>{order.provider_tx_id or '-'}</code>\n"
        f"⚠️ Ошибка: <code>{order.error_message or 'нет'}</code>\n"
        f"🕒 Создан: {created_str}\n\n"
        f"Выберите действие с заказом:"
    )
    await message.answer(text, reply_markup=get_order_manage_keyboard(order.id, order.status))


@router.callback_query(F.data == "admin_search_order")
async def handle_search_order_prompt(callback: CallbackQuery, state: FSMContext) -> None:
    """
    Запрос данных для поиска заказа.
    """
    await state.set_state(AdminStates.waiting_for_search_query)
    text = (
        "🔍 <b>Поиск заказа</b>\n\n"
        "Введите ID заказа (число) или @username получателя:"
    )
    await callback.message.edit_text(text, reply_markup=get_admin_menu_keyboard())
    await callback.answer()


@router.message(AdminStates.waiting_for_search_query)
async def handle_search_order_exec(message: Message, session: AsyncSession, state: FSMContext) -> None:
    """
    Выполнение поиска заказа.
    """
    query = (message.text or "").strip()
    await state.clear()

    results = await order_crud.search_orders(session, query=query, limit=10)
    if not results:
        await message.answer(f"🔍 По запросу <code>{query}</code> ничего не найдено.", reply_markup=get_admin_menu_keyboard())
        return

    lines = [f"🔍 <b>Найдено заказов: {len(results)}</b>\n"]
    for ord_item in results:
        lines.append(
            f"<b>Заказ #{ord_item.id}</b> | <code>{ord_item.status.value}</code>\n"
            f"⭐️ {ord_item.stars_amount} звёзд для @{ord_item.recipient_username} ({ord_item.total_price_usdt} USDT)\n"
            f"Перейти: /order_{ord_item.id}\n"
        )

    await message.answer("\n".join(lines), reply_markup=get_admin_menu_keyboard())


# ==============================================================================
# Смена статуса заказа и возврат с подтверждением "Да / Нет"
# ==============================================================================

@router.callback_query(F.data.startswith("ask_status:"))
async def handle_ask_status_change(callback: CallbackQuery, session: AsyncSession) -> None:
    """
    Запрос подтверждения перед сменой статуса.
    Защита: если заказ DELIVERED, нельзя перевести в CREATED или PAID.
    """
    _, raw_id, target_status = callback.data.split(":")
    order_id = int(raw_id)
    order = await order_crud.get_order_by_id(session, order_id)

    if not order:
        await callback.answer("⚠️ Заказ не найден.", show_alert=True)
        return

    # Запрет перевода уже доставленного заказа в created или paid
    if order.status == OrderStatus.DELIVERED and target_status in (OrderStatus.CREATED.value, OrderStatus.PAID.value):
        await callback.answer(
            "⚠️ Нельзя перевести уже выполненный заказ (delivered) обратно в created или paid!",
            show_alert=True,
        )
        return

    text = (
        f"❓ <b>Подтверждение смены статуса</b>\n\n"
        f"Вы действительно хотите изменить статус заказа <b>#{order.id}</b> "
        f"с <code>{order.status.value}</code> на <b>{target_status}</b>?"
    )
    payload = f"{order.id}_{target_status}"
    await callback.message.edit_text(text, reply_markup=get_confirmation_keyboard("status", payload))
    await callback.answer()


@router.callback_query(F.data.startswith("ask_refund:"))
async def handle_ask_refund(callback: CallbackQuery, session: AsyncSession) -> None:
    """
    Запрос подтверждения оформления возврата.
    """
    order_id = int(callback.data.split(":")[1])
    order = await order_crud.get_order_by_id(session, order_id)
    if not order:
        await callback.answer("⚠️ Заказ не найден.", show_alert=True)
        return

    text = (
        f"❓ <b>Подтверждение возврата</b>\n\n"
        f"Оформить возврат (Refund) для заказа <b>#{order.id}</b>?\n"
        f"Сумма: <b>{order.total_price_usdt} USDT</b>, Получатель: @{order.recipient_username}.\n"
        f"Статус будет изменён на <code>refunded</code>."
    )
    await callback.message.edit_text(text, reply_markup=get_confirmation_keyboard("refund", str(order.id)))
    await callback.answer()


@router.callback_query(F.data.startswith("confirm:"))
async def handle_confirm_action(callback: CallbackQuery, session: AsyncSession) -> None:
    """
    Обработка подтверждения действия (Да).
    """
    _, action_tag, payload = callback.data.split(":")

    if action_tag == "status":
        order_id_str, new_status_str = payload.split("_")
        order_id = int(order_id_str)
        target_status = OrderStatus(new_status_str)

        order = await order_crud.get_order_by_id(session, order_id)
        if order and order.status == OrderStatus.DELIVERED and target_status in (OrderStatus.CREATED, OrderStatus.PAID):
            await callback.answer("⚠️ Запрещено менять delivered на created/paid!", show_alert=True)
            return

        await order_crud.update_order_status(session, order_id, status=target_status)
        logger.info("Админ %s вручную изменил статус заказа #%s на %s", callback.from_user.id, order_id, target_status.value)
        await callback.answer("Статус успешно обновлён!", show_alert=True)
        await callback.message.edit_text(
            f"✅ Статус заказа <b>#{order_id}</b> изменён на <b>{target_status.value}</b>.",
            reply_markup=get_admin_menu_keyboard(),
        )

    elif action_tag == "refund":
        order_id = int(payload)
        await order_crud.update_order_status(session, order_id, status=OrderStatus.REFUNDED)
        logger.info("Админ %s оформил возврат по заказу #%s", callback.from_user.id, order_id)
        await callback.answer("Возврат зафиксирован!", show_alert=True)
        await callback.message.edit_text(
            f"✅ По заказу <b>#{order_id}</b> успешно установлен статус <b>refunded</b>.",
            reply_markup=get_admin_menu_keyboard(),
        )


@router.callback_query(F.data.startswith("cancel_act:"))
async def handle_cancel_action(callback: CallbackQuery) -> None:
    """
    Отмена действия (Нет).
    """
    await callback.answer("Действие отменено.")
    await callback.message.edit_text("❌ Действие отменено.", reply_markup=get_admin_menu_keyboard())


# ==============================================================================
# Массовая рассылка сообщений (Rate limiting, обработка блокировок)
# ==============================================================================

@router.callback_query(F.data == "admin_broadcast")
async def handle_broadcast_prompt(callback: CallbackQuery, state: FSMContext) -> None:
    """
    Запрос текста для рассылки.
    """
    await state.set_state(AdminStates.waiting_for_broadcast_message)
    text = (
        "📢 <b>Массовая рассылка сообщений</b>\n\n"
        "Отправьте текст сообщения, которое получат все пользователи бота.\n"
        "Поддерживается HTML-разметка."
    )
    await callback.message.edit_text(text, reply_markup=get_admin_menu_keyboard())
    await callback.answer()


@router.message(AdminStates.waiting_for_broadcast_message)
async def handle_broadcast_preview(message: Message, session: AsyncSession, state: FSMContext) -> None:
    """
    Предпросмотр сообщения рассылки перед запуском.
    """
    broadcast_text = message.text or message.caption or ""
    if not broadcast_text:
        await message.answer("⚠️ Сообщение не должно быть пустым. Отправьте текст:")
        return

    active_user_ids = await user_crud.get_all_active_user_ids(session)
    await state.update_data(broadcast_text=broadcast_text)

    preview_text = (
        f"📢 <b>Предпросмотр рассылки</b>\n\n"
        f"────────────────────\n"
        f"{broadcast_text}\n"
        f"────────────────────\n\n"
        f"👥 Получателей: <b>{len(active_user_ids)} чел.</b>\n"
        f"Подтвердите отправку:"
    )
    await message.answer(preview_text, reply_markup=get_broadcast_confirm_keyboard())


@router.callback_query(F.data == "broadcast_cancel")
async def handle_broadcast_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    """Отмена рассылки."""
    await state.clear()
    await callback.answer("Рассылка отменена.")
    await callback.message.edit_text("❌ Рассылка отменена.", reply_markup=get_admin_menu_keyboard())


@router.callback_query(F.data == "broadcast_start")
async def handle_broadcast_start(callback: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    """
    Выполнение рассылки с контролем скорости и обработкой исключений.
    """
    data = await state.get_data()
    broadcast_text = data.get("broadcast_text")
    await state.clear()

    if not broadcast_text:
        await callback.answer("⚠️ Текст рассылки утерян. Попробуйте снова.", show_alert=True)
        return

    user_ids = await user_crud.get_all_active_user_ids(session)
    if not user_ids:
        await callback.message.edit_text("⚠️ Нет активных пользователей для рассылки.", reply_markup=get_admin_menu_keyboard())
        await callback.answer()
        return

    status_msg = await callback.message.edit_text(
        f"🚀 <b>Рассылка запущена...</b>\nОтправка для {len(user_ids)} пользователей."
    )

    sent_count = 0
    blocked_count = 0
    error_count = 0
    start_time = time.time()

    bot = callback.bot
    for uid in user_ids:
        try:
            await bot.send_message(chat_id=uid, text=broadcast_text)
            sent_count += 1
            # Защита от лимитов Telegram (~20-25 сообщений в секунду)
            await asyncio.sleep(0.05)
        except TelegramRetryAfter as e:
            logger.warning("Telegram flood limit: сон %s сек", e.retry_after)
            await asyncio.sleep(e.retry_after)
            try:
                await bot.send_message(chat_id=uid, text=broadcast_text)
                sent_count += 1
            except Exception:
                error_count += 1
        except TelegramForbiddenError:
            # Пользователь заблокировал бота
            blocked_count += 1
        except Exception as e:
            logger.error("Ошибка при отправке рассылки пользователю %s: %s", uid, e)
            error_count += 1

    duration = round(time.time() - start_time, 1)
    report_text = (
        f"📊 <b>Отчёт о рассылке завершён!</b>\n\n"
        f"✅ Успешно доставлено: <b>{sent_count}</b>\n"
        f"🚫 Заблокировали бота: <b>{blocked_count}</b>\n"
        f"❌ Ошибок при отправке: <b>{error_count}</b>\n"
        f"⏱ Затраченное время: <b>{duration} сек</b>"
    )
    await status_msg.edit_text(report_text, reply_markup=get_admin_menu_keyboard())
    await callback.answer("Рассылка завершена!", show_alert=True)


# ==============================================================================
# Бан и Разбан пользователей
# ==============================================================================

@router.callback_query(F.data == "admin_ban_menu")
async def handle_ban_menu(callback: CallbackQuery) -> None:
    """
    Меню управления блокировками пользователей.
    """
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🚫 Заблокировать", callback_data="ask_ban_user"),
            InlineKeyboardButton(text="✅ Разблокировать", callback_data="ask_unban_user"),
        ],
        [
            InlineKeyboardButton(text="◀️ В панель админа", callback_data="admin_main"),
        ]
    ])
    text = (
        "🚫 <b>Управление блокировками</b>\n\n"
        "Заблокированный пользователь не может отправлять сообщения и оформлять заказы.\n"
        "<i>Администраторов заблокировать нельзя.</i>"
    )
    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data == "ask_ban_user")
async def handle_prompt_ban(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminStates.waiting_for_ban_target)
    await callback.message.edit_text(
        "🚫 Введите Telegram ID (число) или @username пользователя для <b>блокировки</b>:",
        reply_markup=get_admin_menu_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "ask_unban_user")
async def handle_prompt_unban(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminStates.waiting_for_unban_target)
    await callback.message.edit_text(
        "✅ Введите Telegram ID (число) или @username пользователя для <b>разблокировки</b>:",
        reply_markup=get_admin_menu_keyboard(),
    )
    await callback.answer()


@router.message(AdminStates.waiting_for_ban_target)
async def handle_exec_ban(message: Message, session: AsyncSession, state: FSMContext) -> None:
    await state.clear()
    raw = (message.text or "").strip().lstrip("@")

    target_user = None
    if raw.isdigit():
        target_user = await user_crud.get_user_by_id(session, int(raw))
    else:
        target_user = await user_crud.get_user_by_username(session, raw)

    if not target_user:
        await message.answer(f"⚠️ Пользователь <code>{raw}</code> не найден в базе данных.", reply_markup=get_admin_menu_keyboard())
        return

    # Защита: администратора забанить нельзя
    if target_user.id in settings.ADMIN_IDS:
        await message.answer("❌ <b>Ошибка:</b> Нельзя заблокировать администратора бота!", reply_markup=get_admin_menu_keyboard())
        return

    await user_crud.set_user_ban_status(session, target_user.id, is_banned=True)
    logger.info("Админ %s забанил пользователя %s (@%s)", message.from_user.id, target_user.id, target_user.username)
    await message.answer(
        f"🚫 Пользователь <b>{target_user.first_name}</b> (ID: <code>{target_user.id}</code>, @{target_user.username}) успешно <b>заблокирован</b>.",
        reply_markup=get_admin_menu_keyboard(),
    )


@router.message(AdminStates.waiting_for_unban_target)
async def handle_exec_unban(message: Message, session: AsyncSession, state: FSMContext) -> None:
    await state.clear()
    raw = (message.text or "").strip().lstrip("@")

    target_user = None
    if raw.isdigit():
        target_user = await user_crud.get_user_by_id(session, int(raw))
    else:
        target_user = await user_crud.get_user_by_username(session, raw)

    if not target_user:
        await message.answer(f"⚠️ Пользователь <code>{raw}</code> не найден в базе данных.", reply_markup=get_admin_menu_keyboard())
        return

    await user_crud.set_user_ban_status(session, target_user.id, is_banned=False)
    logger.info("Админ %s разбанил пользователя %s (@%s)", message.from_user.id, target_user.id, target_user.username)
    await message.answer(
        f"✅ Пользователь <b>{target_user.first_name}</b> (ID: <code>{target_user.id}</code>, @{target_user.username}) успешно <b>разблокирован</b>.",
        reply_markup=get_admin_menu_keyboard(),
    )


@router.message(Command("ban"))
async def handle_ban_command(message: Message, session: AsyncSession) -> None:
    """Команда /ban <user_id>"""
    parts = (message.text or "").strip().split()
    if len(parts) < 2 or not parts[1].isdigit():
        await message.answer("⚠️ Использование: <code>/ban &lt;user_id&gt;</code>")
        return

    target_id = int(parts[1])
    if target_id in settings.ADMIN_IDS:
        await message.answer("❌ Нельзя заблокировать администратора бота.")
        return

    user = await user_crud.set_user_ban_status(session, target_id, is_banned=True)
    if user:
        await message.answer(f"🚫 Пользователь <code>{target_id}</code> заблокирован.")
    else:
        await message.answer(f"⚠️ Пользователь <code>{target_id}</code> не найден.")


@router.message(Command("unban"))
async def handle_unban_command(message: Message, session: AsyncSession) -> None:
    """Команда /unban <user_id>"""
    parts = (message.text or "").strip().split()
    if len(parts) < 2 or not parts[1].isdigit():
        await message.answer("⚠️ Использование: <code>/unban &lt;user_id&gt;</code>")
        return

    target_id = int(parts[1])
    user = await user_crud.set_user_ban_status(session, target_id, is_banned=False)
    if user:
        await message.answer(f"✅ Пользователь <code>{target_id}</code> разблокирован.")
    else:
        await message.answer(f"⚠️ Пользователь <code>{target_id}</code> не найден.")
