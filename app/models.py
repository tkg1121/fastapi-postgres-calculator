"""SQLAlchemy models for the calculator application's own database schema."""

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Float, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("username", name="uq_calculator_users_username"),
        UniqueConstraint("email", name="uq_calculator_users_email"),
        {"schema": "calculator"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(50), nullable=False)
    email: Mapped[str] = mapped_column(String(254), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class Calculation(Base):
    __tablename__ = "calculations"
    __table_args__ = (
        CheckConstraint(
            "type IN ('add', 'subtract', 'multiply', 'divide')",
            name="ck_calculations_type",
        ),
        CheckConstraint(
            "a > '-Infinity'::double precision AND a < 'Infinity'::double precision",
            name="ck_calculations_a_finite",
        ),
        CheckConstraint(
            "b > '-Infinity'::double precision AND b < 'Infinity'::double precision",
            name="ck_calculations_b_finite",
        ),
        CheckConstraint(
            "result > '-Infinity'::double precision AND result < 'Infinity'::double precision",
            name="ck_calculations_result_finite",
        ),
        CheckConstraint("type <> 'divide' OR b <> 0", name="ck_calculations_divisor"),
        {"schema": "calculator"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    a: Mapped[float] = mapped_column(Float, nullable=False)
    b: Mapped[float] = mapped_column(Float, nullable=False)
    type: Mapped[str] = mapped_column(String(10), nullable=False)
    result: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
