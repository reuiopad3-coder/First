from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class ProviderResult:
    """
    Результат выполнения операции выдачи Telegram Stars.
    """
    success: bool
    tx_id: Optional[str] = None
    error: Optional[str] = None


class StarsProvider(ABC):
    """
    Абстрактный интерфейс провайдера выдачи Telegram Stars.
    """

    @abstractmethod
    async def send_stars(
        self,
        recipient_username: str,
        amount: int,
        order_id: int,
    ) -> ProviderResult:
        """
        Отправка звёзд получателю.

        :param recipient_username: Username получателя без '@'
        :param amount: Количество отправляемых звёзд
        :param order_id: Идентификатор заказа (для идемпотентности)
        :return: ProviderResult
        """
        pass
