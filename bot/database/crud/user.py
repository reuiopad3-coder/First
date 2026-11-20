from typing import List, Optional
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models.user import User


async def get_or_create_user(
    session: AsyncSession,
    user_id: int,
    username: Optional[str] = None,
    first_name: Optional[str] = None,
    last_name: Optional[str] = None,
) -> tuple[User, bool]:
    """
    Получает пользователя по ID или создает нового.
    Обновляет username и имена, если они изменились.
    Возвращает (User, created: bool).
    """
    stmt = select(User).where(User.id == user_id)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()

    if user:
        # Проверяем и обновляем изменившиеся данные профиля
        changed = False
        if user.username != username:
            user.username = username
            changed = True
        if user.first_name != first_name:
            user.first_name = first_name
            changed = True
        if user.last_name != last_name:
            user.last_name = last_name
            changed = True
        if changed:
            await session.commit()
        return user, False

    new_user = User(
        id=user_id,
        username=username,
        first_name=first_name,
        last_name=last_name,
    )
    session.add(new_user)
    await session.commit()
    await session.refresh(new_user)
    return new_user, True


async def get_user_by_id(session: AsyncSession, user_id: int) -> Optional[User]:
    """
    Получение пользователя по Telegram ID.
    """
    stmt = select(User).where(User.id == user_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_user_by_username(session: AsyncSession, username: str) -> Optional[User]:
    """
    Поиск пользователя по username (без учета @).
    """
    clean_username = username.lstrip("@").lower()
    stmt = select(User).where(User.username.ilike(clean_username))
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def set_user_ban_status(session: AsyncSession, user_id: int, is_banned: bool) -> Optional[User]:
    """
    Блокировка или разблокировка пользователя в боте.
    """
    stmt = (
        update(User)
        .where(User.id == user_id)
        .values(is_banned=is_banned)
        .returning(User)
    )
    result = await session.execute(stmt)
    await session.commit()
    return result.scalar_one_or_none()


async def get_all_active_user_ids(session: AsyncSession) -> List[int]:
    """
    Получение списка ID всех незабаненных пользователей (для рассылки).
    """
    stmt = select(User.id).where(User.is_banned.is_(False))
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def count_total_users(session: AsyncSession) -> int:
    """
    Общее количество зарегистрированных пользователей.
    """
    from sqlalchemy import func
    stmt = select(func.count(User.id))
    result = await session.execute(stmt)
    return result.scalar_one() or 0
