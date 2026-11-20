import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from bot.config import settings
from bot.database.session import async_session_factory, engine
from bot.handlers import register_all_handlers
from bot.middlewares import DatabaseMiddleware, ThrottlingMiddleware, UserMiddleware
from bot.services import PaymentPollingWorker
from bot.utils.logging import setup_logging

logger = logging.getLogger(__name__)


async def main() -> None:
    """
    Главная функция запуска Telegram-бота.
    """
    # 1. Инициализация логирования
    setup_logging(log_level=logging.INFO)
    logger.info("Запуск Telegram Stars Bot...")
    logger.info("Сеть CryptoBot: %s | Провайдер звёзд: %s", settings.CRYPTOBOT_NETWORK, settings.STARS_PROVIDER)
    logger.info("Администраторы: %s", settings.ADMIN_IDS)

    # 2. Инициализация Bot и Dispatcher
    bot = Bot(
        token=settings.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())

    # 3. Регистрация Middlewares (внешние / outer)
    # Порядок важен:
    # 1) Throttling - отсекает спам до обращения к БД
    # 2) Database - открывает сессию БД
    # 3) User - регистрирует пользователя и проверяет бан через сессию БД
    dp.message.outer_middleware(ThrottlingMiddleware(rate_limit=0.6))
    dp.callback_query.outer_middleware(ThrottlingMiddleware(rate_limit=0.6))

    dp.message.outer_middleware(DatabaseMiddleware(session_pool=async_session_factory))
    dp.callback_query.outer_middleware(DatabaseMiddleware(session_pool=async_session_factory))

    dp.message.outer_middleware(UserMiddleware())
    dp.callback_query.outer_middleware(UserMiddleware())

    # 4. Регистрация роутеров
    register_all_handlers(dp)

    # 5. Фоновый воркер проверки платежей CryptoBot
    polling_worker = PaymentPollingWorker(bot=bot)

    # 6. Запуск Polling и Graceful Shutdown
    try:
        # Запускаем фоновый опрос оплат
        polling_worker.start()

        # Удаляем вебхук и сбрасываем накопившиеся апдейты при старте
        await bot.delete_webhook(drop_pending_updates=True)
        logger.info("Бот успешно запущен и готов к приёму сообщений (polling)...")
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    except asyncio.CancelledError:
        logger.info("Получен сигнал остановки...")
    except Exception as e:
        logger.exception("Критическая ошибка при работе бота: %s", e)
    finally:
        logger.info("Завершение работы: остановка фонового воркера и закрытие сессий...")
        await polling_worker.stop()
        await bot.session.close()
        await engine.dispose()
        logger.info("Бот успешно остановлен.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Бот остановлен пользователем.")
