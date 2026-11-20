from bot.config import settings
from bot.services.stars_provider.base import ProviderResult, StarsProvider
from bot.services.stars_provider.fragment import FragmentProvider
from bot.services.stars_provider.mock import MockProvider


def get_stars_provider() -> StarsProvider:
    """
    Фабрика провайдеров выдачи звёзд на основе переменной STARS_PROVIDER из .env.
    """
    provider_name = settings.STARS_PROVIDER.lower().strip()
    if provider_name == "fragment":
        return FragmentProvider()
    return MockProvider()


__all__ = ["StarsProvider", "ProviderResult", "MockProvider", "FragmentProvider", "get_stars_provider"]
