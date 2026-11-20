from aiogram.filters import Filter
from aiogram.types import TelegramObject

from bot.config import settings


class IsAdminFilter(Filter):
    """
    Фильтр для проверки, является ли пользователь администратором бота.
    Сверяет ID пользователя со списком settings.ADMIN_IDS.
    """
    async def __call__(self, event: TelegramObject) -> bool:
        from_user = getattr(event, "from_user", None)
        if not from_user:
            return False
        return from_user.id in settings.ADMIN_IDS
