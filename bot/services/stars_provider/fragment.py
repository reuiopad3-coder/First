import logging
from bot.services.stars_provider.base import ProviderResult, StarsProvider

logger = logging.getLogger(__name__)


class FragmentProvider(StarsProvider):
    """
    Заготовка для интеграции с Fragment (Telegram Stars through Ton / Fragment API).
    Будет реализована на последующих этапах при подключении боевого шлюза.
    """

    def __init__(self, api_key: str = "", ton_wallet_address: str = "") -> None:
        self.api_key = api_key
        self.ton_wallet_address = ton_wallet_address

    async def send_stars(
        self,
        recipient_username: str,
        amount: int,
        order_id: int,
    ) -> ProviderResult:
        logger.warning(
            "FragmentProvider: вызов метода send_stars для заказа #%s (провайдер ещё не реализован)",
            order_id,
        )
        # Заглушка до реализации боевого шлюза Fragment
        return ProviderResult(
            success=False,
            error="FragmentProvider находится в разработке. Пожалуйста, используйте STARS_PROVIDER=mock в .env",
        )
