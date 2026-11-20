from typing import Any, Awaitable, Callable, Dict
from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject
from cachetools import TTLCache


class ThrottlingMiddleware(BaseMiddleware):
    """
    Middleware антифлуда на основе TTLCache.
    Ограничивает частоту запросов от одного пользователя.
    """
    def __init__(self, rate_limit: float = 0.6) -> None:
        self.rate_limit = rate_limit
        # Хранит ID пользователей, недавно отправивших запрос
        self.cache = TTLCache(maxsize=10_000, ttl=rate_limit)
        # Хранит пользователей, которых мы уже предупредили (чтобы не спамить в ответ)
        self.alert_cache = TTLCache(maxsize=10_000, ttl=2.0)

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        user_id = None
        from_user = getattr(event, "from_user", None)
        if from_user:
            user_id = getattr(from_user, "id", None)

        if user_id:
            if user_id in self.cache:
                # Пользователь отправляет запросы слишком часто
                if user_id not in self.alert_cache:
                    self.alert_cache[user_id] = True
                    if isinstance(event, Message):
                        await event.answer("⚠️ Слишком много запросов. Пожалуйста, подождите секунду.")
                    elif isinstance(event, CallbackQuery):
                        await event.answer("⚠️ Слишком быстро! Подождите секунду.", show_alert=False)
                return None

            self.cache[user_id] = True

        return await handler(event, data)
