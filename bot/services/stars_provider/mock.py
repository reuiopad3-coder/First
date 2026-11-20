import asyncio
import logging
from typing import List, Dict, Any
from bot.services.stars_provider.base import ProviderResult, StarsProvider

logger = logging.getLogger(__name__)


class MockProvider(StarsProvider):
    """
    Тестовый провайдер для эмуляции выдачи звёзд без реальных денег.
    Позволяет настраивать задержку, эмуляцию сбоев и проверять идемпотентность.
    """

    def __init__(
        self,
        delay: float = 0.0,
        should_fail: bool = False,
        error_message: str = "MockProvider: имитация ошибки выдачи звёзд",
    ) -> None:
        self.delay = delay
        self.should_fail = should_fail
        self.error_message = error_message
        # Журнал выполненных доставок для проверки идемпотентности в тестах
        self.deliveries_history: List[Dict[str, Any]] = []

    async def send_stars(
        self,
        recipient_username: str,
        amount: int,
        order_id: int,
    ) -> ProviderResult:
        logger.info(
            "MockProvider: запрос на выдачу %s звёзд пользователю @%s (Заказ #%s)",
            amount,
            recipient_username,
            order_id,
        )

        if self.delay > 0:
            await asyncio.sleep(self.delay)

        if self.should_fail:
            logger.warning(
                "MockProvider: имитация сбоя при выдаче звёзд для заказа #%s: %s",
                order_id,
                self.error_message,
            )
            return ProviderResult(
                success=False,
                error=self.error_message,
            )

        tx_id = f"mock_tx_{order_id}_{amount}stars"
        self.deliveries_history.append({
            "order_id": order_id,
            "recipient_username": recipient_username,
            "amount": amount,
            "tx_id": tx_id,
        })

        logger.info(
            "MockProvider: успешно выдано %s звёзд для заказа #%s (tx_id=%s)",
            amount,
            order_id,
            tx_id,
        )
        return ProviderResult(
            success=True,
            tx_id=tx_id,
        )
