import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional
from aiogram import Bot

from bot.config import settings
from bot.database.crud import order as order_crud
from bot.database.session import async_session_factory
from bot.services.orders import OrderService
from bot.services.payments.cryptobot import CryptoBotService
from bot.services.stars_provider import get_stars_provider

logger = logging.getLogger(__name__)


class PaymentPollingWorker:
    """
    Фоновый воркер для периодической проверки статуса неоплаченных инвойсов CryptoBot.
    Запускается при старте бота и работает каждые N секунд.
    """

    def __init__(self, bot: Optional[Bot] = None) -> None:
        self.bot = bot
        self.is_running = False
        self._task: Optional[asyncio.Task] = None
        self.interval = settings.PAYMENT_CHECK_INTERVAL_SECONDS
        self.payment_gateway = CryptoBotService()
        self.stars_provider = get_stars_provider()

    def start(self) -> None:
        """
        Запуск фоновой задачи поллинга платежей.
        """
        if self.is_running:
            return
        self.is_running = True
        self._task = asyncio.create_task(self._poll_loop())
        logger.info(
            "PaymentPollingWorker запущен (интервал: %s сек, экспирация: %s мин)",
            self.interval,
            settings.PAYMENT_EXPIRE_MINUTES,
        )

    async def stop(self) -> None:
        """
        Остановка фонового воркера.
        """
        self.is_running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("PaymentPollingWorker успешно остановлен.")

    async def _poll_loop(self) -> None:
        while self.is_running:
            try:
                await self._check_pending_orders()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.exception("Ошибка в цикле PaymentPollingWorker: %s", e)

            await asyncio.sleep(self.interval)

    async def _check_pending_orders(self) -> None:
        """
        Один проход проверки всех ожидающих оплаты заказов.
        """
        async with async_session_factory() as session:
            pending_orders = await order_crud.get_pending_payment_orders(session)
            if not pending_orders:
                return

            order_service = OrderService(
                session=session,
                payment_gateway=self.payment_gateway,
                stars_provider=self.stars_provider,
                bot=self.bot,
            )

            now_utc = datetime.now(timezone.utc)
            for order in pending_orders:
                # Проверка на истечение времени (если заказ протух более чем на 15 мин)
                if order.payment_expires_at:
                    expires_at = order.payment_expires_at
                    if expires_at.tzinfo is None:
                        expires_at = expires_at.replace(tzinfo=timezone.utc)

                    if now_utc > expires_at:
                        # Проверяем последний раз, не был ли счёт оплачен в последние секунды
                        is_paid, _ = await self.payment_gateway.check_invoice_paid(
                            invoice_id=order.payment_id,
                            expected_amount=order.total_price_usdt,
                            expected_asset="USDT",
                        )
                        if not is_paid:
                            logger.info("Инвойс заказа #%s (invoice_id=%s) истёк по таймауту.", order.id, order.payment_id)
                            from bot.database.models.order import OrderStatus
                            await order_crud.update_order_status(
                                session=session,
                                order_id=order.id,
                                status=OrderStatus.EXPIRED,
                                error_message="Срок действия счёта истёк",
                            )
                            continue

                try:
                    await order_service.check_and_process_payment(order.id)
                except Exception as e:
                    logger.error("Ошибка при проверке оплаты заказа #%s: %s", order.id, e)
