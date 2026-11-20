from typing import Any, Awaitable, Callable, Dict, Optional
from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.crud import user as user_crud


class UserMiddleware(BaseMiddleware):
    """
    Middleware для:
    1. Автоматической регистрации или обновления профиля пользователя в БД.
    2. Проверки статуса блокировки (is_banned).
    3. Передачи объекта пользователя в data['user'].
    """
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        session: Optional[AsyncSession] = data.get("session")
        if not session:
            # Если по какой-то причине сессия не передана, продолжаем
            return await handler(event, data)

        tg_user = getattr(event, "from_user", None)
        if not tg_user:
            return await handler(event, data)

        # Получаем или регистрируем пользователя в БД
        db_user, _ = await user_crud.get_or_create_user(
            session=session,
            user_id=tg_user.id,
            username=tg_user.username,
            first_name=tg_user.first_name,
            last_name=tg_user.last_name,
        )

        # Проверка бана
        if db_user.is_banned:
            if hasattr(event, "answer"):
                if isinstance(event, CallbackQuery):
                    await event.answer("⛔ Доступ заблокирован администратором.", show_alert=True)
                else:
                    await event.answer("⛔ <b>Доступ заблокирован</b>\nВы были заблокированы администратором.")
            return None

        data["user"] = db_user
        return await handler(event, data)
