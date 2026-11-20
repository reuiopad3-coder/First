from decimal import Decimal
from typing import Optional, Tuple
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import settings
from bot.database.models.setting import AppSetting


SETTING_BASE_PRICE = "star_base_price_usdt"
SETTING_MARKUP_PERCENT = "star_markup_percent"
SETTING_SUPPORT = "support_username"
SETTING_REVIEWS = "reviews_url"


async def get_setting_value(
    session: AsyncSession,
    key: str,
    default: Optional[str] = None,
) -> Optional[str]:
    """
    Получение значения настройки по ключу.
    """
    stmt = select(AppSetting).where(AppSetting.key == key)
    result = await session.execute(stmt)
    setting_row = result.scalar_one_or_none()
    if setting_row:
        return setting_row.value
    return default


async def set_setting_value(
    session: AsyncSession,
    key: str,
    value: str,
    description: Optional[str] = None,
) -> AppSetting:
    """
    Установка значения настройки (создание или обновление).
    """
    stmt = select(AppSetting).where(AppSetting.key == key)
    result = await session.execute(stmt)
    setting_row = result.scalar_one_or_none()

    if setting_row:
        setting_row.value = value
        if description:
            setting_row.description = description
    else:
        setting_row = AppSetting(key=key, value=value, description=description)
        session.add(setting_row)

    await session.commit()
    await session.refresh(setting_row)
    return setting_row


async def get_current_pricing(session: AsyncSession) -> Tuple[Decimal, Decimal]:
    """
    Возвращает кортеж (base_price_usdt, markup_percent) с учетом значений из БД или дефолтов из .env.
    """
    base_val = await get_setting_value(session, SETTING_BASE_PRICE)
    markup_val = await get_setting_value(session, SETTING_MARKUP_PERCENT)

    base_price = Decimal(base_val) if base_val else settings.STAR_DEFAULT_BASE_PRICE
    markup_percent = Decimal(markup_val) if markup_val else settings.STAR_DEFAULT_MARKUP_PERCENT

    return base_price, markup_percent


async def update_pricing(
    session: AsyncSession,
    base_price: Optional[Decimal] = None,
    markup_percent: Optional[Decimal] = None,
) -> Tuple[Decimal, Decimal]:
    """
    Обновление базовой цены за звезду и/или процента наценки.
    """
    if base_price is not None:
        await set_setting_value(
            session,
            SETTING_BASE_PRICE,
            str(base_price),
            "Базовая цена за 1 звезду в USDT",
        )
    if markup_percent is not None:
        await set_setting_value(
            session,
            SETTING_MARKUP_PERCENT,
            str(markup_percent),
            "Наценка на звёзды в процентах (%)",
        )

    return await get_current_pricing(session)
