from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import BigInteger, Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Asset(Base):
    __tablename__ = "assets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ticker: Mapped[str] = mapped_column(String(10), unique=True, nullable=False)
    company_name: Mapped[str | None] = mapped_column(Text)
    sector: Mapped[str | None] = mapped_column(Text)
    industry: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    prices: Mapped[list["DailyPrice"]] = relationship(back_populates="asset")


class DailyPrice(Base):
    __tablename__ = "daily_prices"
    __table_args__ = (UniqueConstraint("asset_id", "trading_date"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id"))
    trading_date: Mapped[date] = mapped_column(Date, nullable=False)
    open: Mapped[Decimal | None] = mapped_column(Numeric)
    high: Mapped[Decimal | None] = mapped_column(Numeric)
    low: Mapped[Decimal | None] = mapped_column(Numeric)
    close: Mapped[Decimal | None] = mapped_column(Numeric)
    adjusted_close: Mapped[Decimal | None] = mapped_column(Numeric)
    volume: Mapped[int | None] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    asset: Mapped[Asset] = relationship(back_populates="prices")


class ModelFeature(Base):
    __tablename__ = "model_features"
    __table_args__ = (UniqueConstraint("asset_id", "trading_date"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id"))
    trading_date: Mapped[date] = mapped_column(Date, nullable=False)
    log_return: Mapped[Decimal | None] = mapped_column(Numeric)
    rolling_volatility_14d: Mapped[Decimal | None] = mapped_column(Numeric)
    momentum_score: Mapped[Decimal | None] = mapped_column(Numeric)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class ModelSignal(Base):
    __tablename__ = "model_signals"
    __table_args__ = (UniqueConstraint("asset_id", "trading_date", "model_name"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id"))
    trading_date: Mapped[date] = mapped_column(Date, nullable=False)
    signal: Mapped[str] = mapped_column(String(10), nullable=False)
    confidence: Mapped[Decimal | None] = mapped_column(Numeric)
    model_name: Mapped[str] = mapped_column(Text, nullable=False)
    execution_status: Mapped[str] = mapped_column(String(20), default="PENDING")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Trade(Base):
    __tablename__ = "trades"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    signal_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("model_signals.id"))
    ticker: Mapped[str | None] = mapped_column(String(10))
    side: Mapped[str | None] = mapped_column(String(10))
    quantity: Mapped[int | None] = mapped_column(Integer)
    execution_price: Mapped[Decimal | None] = mapped_column(Numeric)
    execution_time: Mapped[datetime | None] = mapped_column(DateTime)
    broker_order_id: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str | None] = mapped_column(Text)
