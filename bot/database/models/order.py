import enum
from decimal import Decimal
from datetime import datetime
from typing import TYPE_CHECKING, Optional
from sqlalchemy import BigInteger, DateTime, Enum, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from bot.database.base import Base, TimestampMixin

if TYPE_CHECKING:
    from bot.database.models.user import User


class OrderStatus(str, enum.Enum):
    CREATED = "created"       # Счёт создан, ожидает оплаты
    PAID = "paid"             # Оплачен, ожидает выдачи звёзд
    DELIVERED = "delivered"   # Звёзды успешно зачислены
    FAILED = "failed"         # Ошибка выдачи звёзд (требуется внимание админа)
    REFUNDED = "refunded"     # Возврат средств
    EXPIRED = "expired"       # Счёт истёк по таймауту (15 минут)
    CANCELED = "canceled"     # Отменён пользователем


class Order(Base, TimestampMixin):
    """
    Модель заказа Telegram Stars.
    Все расчёты хранятся в USDT в формате Decimal.
    """
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    recipient_username: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    stars_amount: Mapped[int] = mapped_column(Integer, nullable=False)

    # Ценообразование в USDT
    price_per_star: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False)
    markup_percent: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    total_price_usdt: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)

    # Статус
    status: Mapped[OrderStatus] = mapped_column(
        Enum(OrderStatus, native_enum=False, length=20),
        default=OrderStatus.CREATED,
        nullable=False,
        index=True,
    )

    # Платёжная информация (CryptoBot)
    payment_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)
    payment_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    payment_expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Информация о выдаче звёзд
    provider_tx_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    user: Mapped["User"] = relationship("User", back_populates="orders")

    def __repr__(self) -> str:
        return (
            f"<Order(id={self.id}, user_id={self.user_id}, stars={self.stars_amount}, "
            f"total_usdt={self.total_price_usdt}, status={self.status})>"
        )
