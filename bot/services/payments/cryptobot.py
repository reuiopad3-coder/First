import logging
from datetime import datetime
from decimal import Decimal
from typing import Optional, Tuple
import httpx

from bot.config import settings
from bot.services.payments.base import PaymentGateway, PaymentInvoice

logger = logging.getLogger(__name__)


class CryptoBotService(PaymentGateway):
    """
    Интеграция с Crypto Pay API (CryptoBot).
    Поддерживает mainnet и testnet. Токены и секреты маскируются и не выводятся в логи.
    """

    MAINNET_URL = "https://pay.crypt.bot/api"
    TESTNET_URL = "https://testnet-pay.crypt.bot/api"

    def __init__(self, token: Optional[str] = None, network: Optional[str] = None) -> None:
        self.token = token if token is not None else settings.CRYPTOBOT_TOKEN
        self.network = (network or settings.CRYPTOBOT_NETWORK).lower().strip()
        self.base_url = self.MAINNET_URL if self.network == "main" else self.TESTNET_URL

    def _get_headers(self) -> dict:
        return {
            "Crypto-Pay-API-Token": self.token,
            "Content-Type": "application/json",
        }

    async def create_invoice(
        self,
        amount: Decimal,
        asset: str = "USDT",
        description: str = "",
        expires_in_seconds: int = 900,
    ) -> PaymentInvoice:
        """
        Создает счёт на оплату через Crypto Pay API.
        """
        url = f"{self.base_url}/createInvoice"
        payload = {
            "asset": asset.upper(),
            "amount": str(amount),
            "description": description[:1024] if description else "Покупка Telegram Stars",
            "expires_in": expires_in_seconds,
        }

        # Безопасное логирование без токена
        logger.info(
            "CryptoBot: создание счёта на сумму %s %s (сеть %s, истекает через %s сек)",
            amount,
            asset,
            self.network,
            expires_in_seconds,
        )

        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                response = await client.post(url, headers=self._get_headers(), json=payload)
                data = response.json()
            except Exception as e:
                logger.error("CryptoBot: сетевая ошибка при вызове createInvoice: %s", e)
                raise ConnectionError(f"Ошибка соединения с CryptoBot API: {e}") from e

        if not data.get("ok"):
            err_msg = data.get("error", {}).get("name", "Unknown error")
            logger.error("CryptoBot: ошибка API при createInvoice: %s", err_msg)
            raise ValueError(f"CryptoBot API вернул ошибку: {err_msg}")

        result = data["result"]
        created_at_dt = None
        expires_at_dt = None

        if result.get("created_at"):
            try:
                created_at_dt = datetime.fromisoformat(result["created_at"].replace("Z", "+00:00"))
            except Exception:
                pass

        if result.get("expiration_date"):
            try:
                expires_at_dt = datetime.fromisoformat(result["expiration_date"].replace("Z", "+00:00"))
            except Exception:
                pass

        return PaymentInvoice(
            invoice_id=str(result["invoice_id"]),
            pay_url=result.get("bot_invoice_url") or result.get("pay_url") or "",
            amount=Decimal(str(result["amount"])),
            asset=result.get("asset", asset),
            status=result.get("status", "active"),
            created_at=created_at_dt,
            expiration_date=expires_at_dt,
        )

    async def get_invoice(self, invoice_id: str) -> Optional[PaymentInvoice]:
        """
        Запрашивает информацию об инвойсе по его ID.
        """
        url = f"{self.base_url}/getInvoices"
        params = {"invoice_ids": invoice_id}

        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                response = await client.get(url, headers=self._get_headers(), params=params)
                data = response.json()
            except Exception as e:
                logger.error("CryptoBot: ошибка при запросе инвойса #%s: %s", invoice_id, e)
                return None

        if not data.get("ok"):
            return None

        items = data.get("result", {}).get("items", [])
        if not items:
            return None

        inv = items[0]
        created_at_dt = None
        expires_at_dt = None

        if inv.get("created_at"):
            try:
                created_at_dt = datetime.fromisoformat(inv["created_at"].replace("Z", "+00:00"))
            except Exception:
                pass

        if inv.get("expiration_date"):
            try:
                expires_at_dt = datetime.fromisoformat(inv["expiration_date"].replace("Z", "+00:00"))
            except Exception:
                pass

        return PaymentInvoice(
            invoice_id=str(inv["invoice_id"]),
            pay_url=inv.get("bot_invoice_url") or inv.get("pay_url") or "",
            amount=Decimal(str(inv["amount"])),
            asset=inv.get("asset", "USDT"),
            status=inv.get("status", "active"),
            created_at=created_at_dt,
            expiration_date=expires_at_dt,
        )

    async def check_invoice_paid(
        self,
        invoice_id: str,
        expected_amount: Decimal,
        expected_asset: str = "USDT",
    ) -> Tuple[bool, Optional[str]]:
        """
        Строгая валидация статуса, валюты и суммы платежа.
        """
        invoice = await self.get_invoice(invoice_id)
        if not invoice:
            return False, "Счёт не найден в платёжной системе"

        # 1. Проверка статуса
        if invoice.status != "paid":
            return False, f"Счёт не оплачен (текущий статус: {invoice.status})"

        # 2. Проверка валюты
        if invoice.asset.upper() != expected_asset.upper():
            return False, f"Несовпадение валюты: получено {invoice.asset}, ожидалось {expected_asset}"

        # 3. Проверка суммы через Decimal с округлением до сотых
        invoice_amount = invoice.amount.quantize(Decimal("0.01"))
        target_amount = expected_amount.quantize(Decimal("0.01"))

        if invoice_amount < target_amount:
            return False, f"Недоплата: оплачено {invoice_amount} {invoice.asset}, требуется {target_amount}"

        return True, None
