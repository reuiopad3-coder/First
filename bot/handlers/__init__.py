from aiogram import Dispatcher
from bot.handlers.admin import router as admin_router
from bot.handlers.base import router as base_router
from bot.handlers.user import router as user_router


def register_all_handlers(dp: Dispatcher) -> None:
    """
    Регистрация всех роутеров в диспетчере.
    admin_router регистрируется первым, чтобы админ-команды обрабатывались приоритетно.
    """
    dp.include_router(admin_router)
    dp.include_router(base_router)
    dp.include_router(user_router)
