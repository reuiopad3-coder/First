from decimal import Decimal
from typing import List, Literal
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Конфигурация проекта. Все переменные подгружаются из .env или окружения.
    """
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Telegram Bot
    BOT_TOKEN: str = "1234567890:ABCdefGHIjklMNOpqrsTUVwxyz"

    # Принимаем строку вида "123,456" из .env
    ADMIN_IDS_STR: str = Field(default="", alias="ADMIN_IDS")

    @property
    def ADMIN_IDS(self) -> List[int]:
        """
        Парсинг списка Telegram ID администраторов из строки с разделителем-запятой.
        """
        raw = self.ADMIN_IDS_STR.strip()
        if not raw:
            return []
        result = []
        for item in raw.split(","):
            item_clean = item.strip()
            if item_clean.isdigit():
                result.append(int(item_clean))
        return result

    # База данных
    DATABASE_URL: str = "sqlite+aiosqlite:///bot.db"

    # CryptoBot (Crypto Pay API)
    CRYPTOBOT_TOKEN: str = ""
    CRYPTOBOT_NETWORK: Literal["main", "testnet"] = "testnet"

    # Выдача звёзд: 'mock' или 'fragment'
    STARS_PROVIDER: Literal["mock", "fragment"] = "mock"

    # Ценообразование в USDT
    STAR_DEFAULT_BASE_PRICE: Decimal = Decimal("0.0180")
    STAR_DEFAULT_MARKUP_PERCENT: Decimal = Decimal("15.0")

    # Лимиты покупки
    MIN_STARS: int = 50
    MAX_STARS: int = 10000

    # Платёжные таймауты
    PAYMENT_EXPIRE_MINUTES: int = 15
    PAYMENT_CHECK_INTERVAL_SECONDS: int = 10

    # Поддержка и отзывы
    SUPPORT_USERNAME: str = "@support"
    REVIEWS_URL: str = "https://t.me"

    @property
    def is_postgres(self) -> bool:
        return self.DATABASE_URL.startswith("postgresql")


settings = Settings()
