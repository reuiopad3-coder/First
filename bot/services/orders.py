import logging
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Optional, Tuple
from aiogram import Bot
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import settings
from bot.database.crud import order as order_crud
from bot.database.crud import setting as setting_crud
from bot.database.models.order import Order, OrderStatus
from bot.services.payments.base import PaymentGateway
from bot.services.payments.cryptobot import CryptoBotService
from bot.services.stars_provider.base import StarsProvider
from bot.services.stars_provider import get_stars_provider

logger = logging.getLogger(__name__)


class OrderService:
    """
    Сервис управления заказами, проверкой оплаты и выдачей звёзд.
    Обеспечивает строгую идемпотентность и безопасность платежей.
    """

    def __init__(
        self,
        session: AsyncSession,
        payment_gateway: Optional[PaymentGateway] = None,
        stars_provider: Optional[StarsProvider] = None,
        bot: Optional[Bot] = None,
    ) -> None:
        self.session = session
        self.payment_gateway = payment_gateway or CryptoBotService()
        self.stars_provider = stars_provider or get_stars_provider()
        self.bot = bot

    async def create_new_order(
        self,
        user_id: int,
        recipient_username: str,
        stars_amount: int,
    ) -> Order:
        """
        Создает заказ, рассчитывает итоговую стоимость в USDT и генерирует счёт CryptoBot.
        """
        # 1. Получаем актуальные цены из БД (или дефолты из .env)
        base_price, markup_percent = await setting_crud.get_current_pricing(self.session)

        # 2. Расчёт цены: Stars * BasePrice * (1 + Markup/100), округляем до 2 знаков в USDT
        total_usdt = (
            Decimal(stars_amount) * base_price * (Decimal("1") + markup_percent / Decimal("100"))
        ).quantize(Decimal("0.01"))

        # 3. Создаем инвойс в CryptoBot
        clean_recipient = recipient_username.lstrip("@").strip()
        description = f"Telegram Stars x{stars_amount} для @{clean_recipient}"
        expires_seconds = settings.PAYMENT_EXPIRE_MINUTES * 60

        invoice = await self.payment_gateway.create_invoice(
            amount=total_usdt,
            asset="USDT",
            description=description,
            expires_in_seconds=expires_seconds,
        )

        now_utc = datetime.now(timezone.utc)
        expires_at = invoice.expiration_date or (now_utc + timedelta(seconds=expires_seconds))

        # 4. Сохраняем заказ в БД
        order = await order_crud.create_order(
            session=self.session,
            user_id=user_id,
            recipient_username=clean_recipient,
            stars_amount=stars_amount,
            price_per_star=base_price,
            markup_percent=markup_percent,
            total_price_usdt=total_usdt,
            payment_id=invoice.invoice_id,
            payment_url=invoice.pay_url,
            payment_expires_at=expires_at,
        )

        logger.info(
            "Создан заказ #%s (Пользователь: %s, Получатель: @%s, Звёзд: %s, Сумма: %s USDT, Invoice: %s)",
            order.id,
            user_id,
            clean_recipient,
            stars_amount,
            total_usdt,
            invoice.invoice_id,
        )
        return order

    async def fulfill_order(self, order_id: int) -> Tuple[bool, Optional[str]]:
        """
        Выдача звёзд с защитой от двойной отправки (идемпотентность).
        """
        order = await order_crud.get_order_by_id(self.session, order_id)
        if not order:
            return False, f"Заказ #{order_id} не найден"

        # Идемпотентность: если звёзды уже выданы, повторная выдача блокируется
        if order.status == OrderStatus.DELIVERED:
            logger.info("Заказ #%s уже выдан ранее (идемпотентность). Пропуск.", order_id)
            return True, None

        # Разрешаем выдачу только для оплаченных или ранее упавших заказов
        if order.status not in (OrderStatus.PAID, OrderStatus.FAILED):
            return False, f"Заказ #{order_id} в статусе {order.status.value}, выдача невозможна"

        # Вызов провайдера звёзд
        result = await self.stars_provider.send_stars(
            recipient_username=order.recipient_username,
            amount=order.stars_amount,
            order_id=order.id,
        )

        if result.success:
            # Успешная выдача
            await order_crud.update_order_status(
                session=self.session,
                order_id=order.id,
                status=OrderStatus.DELIVERED,
                provider_tx_id=result.tx_id,
            )
            logger.info("Заказ #%s успешно доставлен (tx_id=%s)", order.id, result.tx_id)

            # Уведомление пользователя
            if self.bot:
                try:
                    await self.bot.send_message(
                        chat_id=order.user_id,
                        text=(
                            f"⭐️ <b>Заказ #{order.id} успешно выполнен!</b>\n\n"
                            f"Вам или указанному получателю (<b>@{order.recipient_username}</b>) "
                            f"начислено <b>{order.stars_amount}</b> звёзд.\n"
                            f"Спасибо за покупку!"
                        ),
                    )
                except Exception as e:
                    logger.warning("Не удалось отправить уведомление пользователю %s: %s", order.user_id, e)

            return True, None

        else:
            # Сбой выдачи звёзд
            await order_crud.update_order_status(
                session=self.session,
                order_id=order.id,
                status=OrderStatus.FAILED,
                error_message=result.error,
            )
            logger.error("Ошибка выдачи звёзд для заказа #%s: %s", order.id, result.error)

            if self.bot:
                # 1. Уведомление пользователю
                try:
                    await self.bot.send_message(
                        chat_id=order.user_id,
                        text=(
                            f"⏳ <b>Заказ #{order.id} в обработке</b>\n\n"
                            f"Оплата успешно получена, но автоматическая доставка звёзд "
                            f"задержалась. Наш администратор уже оповещён и завершит выдачу вручную.\n"
                            f"По всем вопросам: {settings.SUPPORT_USERNAME}"
                        ),
                    )
                except Exception as e:
                    logger.warning("Не удалось уведомить пользователя о сбое: %s", e)

                # 2. Уведомление администраторам
                for admin_id in settings.ADMIN_IDS:
                    try:
                        await self.bot.send_message(
                            chat_id=admin_id,
                            text=(
                                f"🚨 <b>Сбой автоматической выдачи звёзд!</b>\n\n"
                                f"Заказ: <b>#{order.id}</b>\n"
                                f"Покупатель: <code>{order.user_id}</code>\n"
                                f"Получатель: @{order.recipient_username}\n"
                                f"Количество: {order.stars_amount} звёзд\n"
                                f"Сумма: {order.total_price_usdt} USDT\n"
                                f"Ошибка: <code>{result.error}</code>"
                            ),
                        )
                    except Exception as e:
                        logger.warning("Не удалось отправить алерт админу %s: %s", admin_id, e)

            return False, result.error

    async def check_and_process_payment(self, order_id: int) -> Tuple[bool, Optional[str]]:
        """
        Проверка оплаты заказа через платёжный шлюз и запуск выдачи при подтверждении.
        """
        order = await order_crud.get_order_by_id(self.session, order_id)
        if not order:
            return False, f"Заказ #{order_id} не найден"

        if order.status != OrderStatus.CREATED:
            return False, f"Заказ #{order_id} уже обработан (статус: {order.status.value})"

        if not order.payment_id:
            return False, f"У заказа #{order_id} отсутствует payment_id"

        # Строгая валидация платежа через шлюз
        is_paid, error_reason = await self.payment_gateway.check_invoice_paid(
            invoice_id=order.payment_id,
            expected_amount=order.total_price_usdt,
            expected_asset="USDT",
        )

        if not is_paid:
            # Проверяем, не истёк ли счёт по времени или статусу
            now_utc = datetime.now(timezone.utc)
            is_expired = False
            if order.payment_expires_at:
                exp = order.payment_expires_at
                if exp.tzinfo is None:
                    exp = exp.replace(tzinfo=timezone.utc)
                if now_utc > exp:
                    is_expired = True

            if is_expired or "expired" in (error_reason or "").lower():
                await order_crud.update_order_status(
                    session=self.session,
                    order_id=order.id,
                    status=OrderStatus.EXPIRED,
                    error_message="Срок действия счёта истёк (15 минут)",
                )
                logger.info("Заказ #%s переведён в статус EXPIRED по таймауту.", order.id)
                return False, "Срок действия счёта истёк"

            return False, error_reason

        # Переводим статус в PAID
        await order_crud.update_order_status(
            session=self.session,
            order_id=order.id,
            status=OrderStatus.PAID,
        )
        logger.info("Заказ #%s успешно оплачен (%s USDT)", order.id, order.total_price_usdt)

        # Сразу запускаем выдачу звёзд
        success, fulfill_err = await self.fulfill_order(order.id)
        return success, fulfill_err

    async def process_payment_by_invoice_id(self, invoice_id: str) -> Tuple[bool, Optional[str]]:
        """
        Точка входа для будущих Webhook: поиск заказа по invoice_id и обработка.
        """
        order = await order_crud.get_order_by_payment_id(self.session, invoice_id)
        if not order:
            return False, f"Заказ с payment_id={invoice_id} не найден"

        return await self.check_and_process_payment(order.id)
