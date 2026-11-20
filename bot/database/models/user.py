from typing import TYPE_CHECKING, List, Optional
from sqlalchemy import BigInteger, Boolean, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from bot.database.base import Base, TimestampMixin

if TYPE_CHECKING:
    from bot.database.models.order import Order


class User(Base, TimestampMixin):
    """
    Модель пользователя Telegram.
    """
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    username: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    first_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    last_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    is_banned: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    orders: Mapped[List["Order"]] = relationship(
        "Order",
        back_populates="user",
        cascade="all, delete-orphan",
        order_by="desc(Order.id)",
    )

    def __repr__(self) -> str:
        return f"<User(id={self.id}, username='{self.username}', is_banned={self.is_banned})>"
