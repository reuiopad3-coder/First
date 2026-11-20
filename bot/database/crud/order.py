from datetime import datetime
from decimal import Decimal
from typing import List, Optional, Tuple
from sqlalchemy import desc, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models.order import Order, OrderStatus


async def create_order(
    session: AsyncSession,
    user_id: int,
    recipient_username: str,
    stars_amount: int,
    price_per_star: Decimal,
    markup_percent: Decimal,
    total_price_usdt: Decimal,
    payment_id: Optional[str] = None,
    payment_url: Optional[str] = None,
    payment_expires_at: Optional[datetime] = None,
) -> Order:
    """
    Создание нового заказа.
    """
    order = Order(
        user_id=user_id,
        recipient_username=recipient_username.lstrip("@"),
        stars_amount=stars_amount,
        price_per_star=price_per_star,
        markup_percent=markup_percent,
        total_price_usdt=total_price_usdt,
        status=OrderStatus.CREATED,
        payment_id=payment_id,
        payment_url=payment_url,
        payment_expires_at=payment_expires_at,
    )
    session.add(order)
    await session.commit()
    await session.refresh(order)
    return order


async def get_order_by_id(session: AsyncSession, order_id: int) -> Optional[Order]:
    """
    Получение заказа по его ID.
    """
    stmt = select(Order).where(Order.id == order_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_order_by_payment_id(session: AsyncSession, payment_id: str) -> Optional[Order]:
    """
    Поиск заказа по идентификатору платежа (invoice_id).
    """
    stmt = select(Order).where(Order.payment_id == payment_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_user_orders(
    session: AsyncSession,
    user_id: int,
    limit: int = 10,
    offset: int = 0,
) -> Tuple[List[Order], int]:
    """
    Получение заказов конкретного пользователя с пагинацией и общего количества.
    """
    count_stmt = select(func.count(Order.id)).where(Order.user_id == user_id)
    total_count = (await session.execute(count_stmt)).scalar_one() or 0

    stmt = (
        select(Order)
        .where(Order.user_id == user_id)
        .order_by(desc(Order.id))
        .limit(limit)
        .offset(offset)
    )
    orders = list((await session.execute(stmt)).scalars().all())
    return orders, total_count


async def get_pending_payment_orders(session: AsyncSession) -> List[Order]:
    """
    Получение списка заказов в статусе ожидания оплаты (для фонового поллинга).
    """
    stmt = (
        select(Order)
        .where(Order.status == OrderStatus.CREATED)
        .where(Order.payment_id.is_not(None))
        .order_by(Order.id)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def update_order_status(
    session: AsyncSession,
    order_id: int,
    status: OrderStatus,
    provider_tx_id: Optional[str] = None,
    error_message: Optional[str] = None,
) -> Optional[Order]:
    """
    Обновление статуса заказа и связанных полей.
    """
    order = await get_order_by_id(session, order_id)
    if not order:
        return None

    order.status = status
    if provider_tx_id:
        order.provider_tx_id = provider_tx_id
    if error_message:
        order.error_message = error_message

    await session.commit()
    await session.refresh(order)
    return order


async def get_recent_orders(
    session: AsyncSession,
    limit: int = 15,
) -> List[Order]:
    """
    Получение последних N заказов в системе (для админки).
    """
    stmt = select(Order).order_by(desc(Order.id)).limit(limit)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def search_orders(
    session: AsyncSession,
    query: str,
    limit: int = 10,
) -> List[Order]:
    """
    Поиск заказов по ID или username получателя.
    """
    clean = query.strip().lstrip("@")
    conditions = [Order.recipient_username.ilike(f"%{clean}%")]

    if clean.isdigit():
        conditions.append(Order.id == int(clean))

    stmt = select(Order).where(or_(*conditions)).order_by(desc(Order.id)).limit(limit)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_orders_stats(
    session: AsyncSession,
    since: Optional[datetime] = None,
) -> dict:
    """
    Подсчет агрегированной статистики (число заказов, выручка, выполненные, проваленные).
    """
    query = select(
        func.count(Order.id).label("total_orders"),
        func.coalesce(func.sum(Order.total_price_usdt), Decimal("0.00")).label("total_revenue"),
        func.coalesce(func.sum(Order.stars_amount), 0).label("total_stars"),
    )

    delivered_query = select(
        func.count(Order.id).label("delivered_orders"),
        func.coalesce(func.sum(Order.total_price_usdt), Decimal("0.00")).label("delivered_revenue"),
    ).where(Order.status == OrderStatus.DELIVERED)

    if since:
        query = query.where(Order.created_at >= since)
        delivered_query = delivered_query.where(Order.created_at >= since)

    total_res = (await session.execute(query)).one()
    delivered_res = (await session.execute(delivered_query)).one()

    return {
        "total_orders": total_res.total_orders,
        "total_revenue": total_res.total_revenue,
        "total_stars": total_res.total_stars,
        "delivered_orders": delivered_res.delivered_orders,
        "delivered_revenue": delivered_res.delivered_revenue,
    }
