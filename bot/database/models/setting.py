from typing import Optional
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from bot.database.base import Base, TimestampMixin


class AppSetting(Base, TimestampMixin):
    """
    Таблица динамических настроек бота (цена за звезду, наценка, ссылки и т.д.).
    Позволяет админу менять параметры без перезапуска бота.
    """
    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(String(256), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)

    def __repr__(self) -> str:
        return f"<AppSetting(key='{self.key}', value='{self.value}')>"
