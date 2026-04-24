from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    telegram_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    username: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    categories: Mapped[list["Category"]] = relationship(back_populates="user")
    expenses: Mapped[list["Expense"]] = relationship(back_populates="user")


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.telegram_id"))
    name: Mapped[str] = mapped_column(String(64))
    emoji: Mapped[str | None] = mapped_column(String(8), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")

    user: Mapped["User"] = relationship(back_populates="categories")
    expenses: Mapped[list["Expense"]] = relationship(back_populates="category")


DEFAULT_CATEGORIES: list[tuple[str, str]] = [
    ("Еда", "🍎"),
    ("Транспорт", "🚗"),
    ("Развлечения", "🎉"),
    ("Здоровье", "💊"),
    ("Прочее", "📦"),
]


class Expense(Base):
    __tablename__ = "expenses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.telegram_id"))
    amount: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    category_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("categories.id"), nullable=True
    )
    transcription: Mapped[str] = mapped_column(Text)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    expense_date: Mapped[date] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    user: Mapped["User"] = relationship(back_populates="expenses")
    category: Mapped["Category | None"] = relationship(back_populates="expenses")
    shared_expenses: Mapped[list["SharedExpense"]] = relationship(
        back_populates="expense", cascade="all, delete-orphan"
    )


class SharedExpense(Base):
    __tablename__ = "shared_expenses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    expense_id: Mapped[int] = mapped_column(Integer, ForeignKey("expenses.id"))
    participant_name: Mapped[str] = mapped_column(Text)
    amount_owed: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    item_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_returned: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false"
    )

    expense: Mapped["Expense"] = relationship(back_populates="shared_expenses")
