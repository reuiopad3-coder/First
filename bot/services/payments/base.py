from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Optional, Tuple


@dataclass
class PaymentInvoice:
    """
    Унифицированное представление счёта на оплату.
    """
    invoice_id: str
    pay_url: str
    amount: Decimal
    asset: str
    status: str
    created_at: Optional[datetime] = None
    expiration_date: Optional[datetime] = None


class PaymentGateway(ABC):
    """
    Абстрактный класс платёжного шлюза.
    """

    @abstractmethod
    async def create_invoice(
        self,
        amount: Decimal,
        asset: str = "USDT",
        description: str = "",
        expires_in_seconds: int = 900,
    ) -> PaymentInvoice:
        """
        Создание инвойса в платёжной системе.
        """
        pass

    @abstractmethod
    async def get_invoice(self, invoice_id: str) -> Optional[PaymentInvoice]:
        """
        Получение данных инвойса по его ID.
        """
        pass

    @abstractmethod
    async def check_invoice_paid(
        self,
        invoice_id: str,
        expected_amount: Decimal,
        expected_asset: str = "USDT",
    ) -> Tuple[bool, Optional[str]]:
        """
        Проверка оплаты инвойса:
        - статус 'paid'
        - валюта совпадает с expected_asset
        - сумма совпадает с expected_amount (Decimal)
        :return: (is_paid_and_valid, error_reason)
        """
        pass
