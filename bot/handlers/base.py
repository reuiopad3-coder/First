import logging
from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models.user import User
from bot.filters.admin import IsAdminFilter

logger = logging.getLogger(__name__)

router = Router(name="base_router")


@router.message(CommandStart())
async def handle_start(message: Message, user: User) -> None:
    """
    Базовый хэндлер команды /start.
    """
    logger.info("Пользователь %s (%s) вызвал /start", user.id, user.username)
    await message.answer(
        f"👋 Привет, <b>{user.first_name or 'пользователь'}</b>!\n\n"
        f"⭐️ Бот продажи Telegram Stars успешно запущен и работает.\n"
        f"Используйте меню для навигации."
    )


@router.message(Command("ping"))
async def handle_ping(message: Message, session: AsyncSession) -> None:
    """
    Служебная команда проверки работоспособности (health check).
    """
    await message.answer("🏓 <b>Pong!</b> Бот онлайн, база данных подключена.")


@router.message(Command("admin_check"), IsAdminFilter())
async def handle_admin_check(message: Message) -> None:
    """
    Проверка прав администратора.
    """
    await message.answer("🔐 <b>Доступ подтверждён:</b> Вы являетесь администратором бота.")
