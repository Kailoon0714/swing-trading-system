from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator
from sqlalchemy import BigInteger, Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Asset(Base):
    __tablename__ = "assets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ticker: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    company_name: Mapped[str | None] = mapped_column(Text)
    sector: Mapped[str | None] = mapped_column(Text, default="Unknown")
    industry: Mapped[str | None] = mapped_column(Text, default="Unknown")
    exchange: Mapped[str | None] = mapped_column(Text)
    currency: Mapped[str | None] = mapped_column(String(10), default="USD")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    min_daily_volume: Mapped[int | None] = mapped_column(BigInteger, default=100_000)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    prices: Mapped[list["DailyPrice"]] = relationship(back_populates="asset")


class DailyPrice(Base):
    __tablename__ = "daily_prices"
    __table_args__ = (UniqueConstraint("asset_id", "trading_date"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id", ondelete="CASCADE"), nullable=False)
    trading_date: Mapped[date] = mapped_column(Date, nullable=False)
    open: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    high: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    low: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    close: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    adjusted_close: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    volume: Mapped[int | None] = mapped_column(BigInteger)
    dollar_volume: Mapped[Decimal | None] = mapped_column(Numeric(24, 6))
    data_vendor: Mapped[str | None] = mapped_column(Text, default="yfinance")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    asset: Mapped[Asset] = relationship(back_populates="prices")


class ModelFeature(Base):
    __tablename__ = "model_features"
    __table_args__ = (UniqueConstraint("asset_id", "trading_date"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id", ondelete="CASCADE"), nullable=False)
    trading_date: Mapped[date] = mapped_column(Date, nullable=False)
    log_return: Mapped[Decimal | None] = mapped_column(Numeric(18, 10))
    rolling_volatility_14d: Mapped[Decimal | None] = mapped_column(Numeric(18, 10))
    momentum_score: Mapped[Decimal | None] = mapped_column(Numeric(18, 10))
    average_volume_20d: Mapped[int | None] = mapped_column(BigInteger)
    liquidity_pass: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class ModelSignal(Base):
    __tablename__ = "model_signals"
    __table_args__ = (UniqueConstraint("asset_id", "trading_date", "model_name"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id", ondelete="CASCADE"), nullable=False)
    trading_date: Mapped[date] = mapped_column(Date, nullable=False)
    signal: Mapped[str] = mapped_column(String(10), nullable=False)
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(10, 6))
    model_name: Mapped[str] = mapped_column(Text, nullable=False)
    sector: Mapped[str | None] = mapped_column(Text)
    industry: Mapped[str | None] = mapped_column(Text)
    rank_in_sector: Mapped[int | None] = mapped_column(Integer)
    execution_status: Mapped[str] = mapped_column(String(20), default="PENDING")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class Trade(Base):
    __tablename__ = "trades"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    signal_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("model_signals.id", ondelete="SET NULL"))
    ticker: Mapped[str] = mapped_column(String(20), nullable=False)
    side: Mapped[str] = mapped_column(String(10), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    execution_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    gross_notional: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    net_notional: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    commission_fee: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), default=0)
    platform_fee: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), default=0)
    settlement_fee: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), default=0)
    sec_fee: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), default=0)
    taf_fee: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), default=0)
    cat_fee: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), default=0)
    total_fees: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), default=0)
    fee_ratio: Mapped[Decimal | None] = mapped_column(Numeric(10, 6))
    execution_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    broker_order_id: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PydanticModel(BaseModel):
    model_config = ConfigDict(from_attributes=True, json_encoders={Decimal: str})


class AssetRecord(PydanticModel):
    ticker: str
    sector: str = "Unknown"
    industry: str = "Unknown"
    is_active: bool = True
    min_daily_volume: int = 100_000

    @field_validator("ticker")
    @classmethod
    def normalize_ticker(cls, value: str) -> str:
        return value.strip().upper()


class FeeBreakdown(PydanticModel):
    mode: Literal["fractional", "standard"]
    commission_fee: Decimal = Field(default=Decimal("0"), ge=0)
    platform_fee: Decimal = Field(default=Decimal("0"), ge=0)
    settlement_fee: Decimal = Field(default=Decimal("0"), ge=0)
    sec_fee: Decimal = Field(default=Decimal("0"), ge=0)
    taf_fee: Decimal = Field(default=Decimal("0"), ge=0)
    cat_fee: Decimal = Field(default=Decimal("0"), ge=0)

    @computed_field
    @property
    def total_fees(self) -> Decimal:
        return (
            self.commission_fee
            + self.platform_fee
            + self.settlement_fee
            + self.sec_fee
            + self.taf_fee
            + self.cat_fee
        )


class SizingDecision(PydanticModel):
    approved: bool
    side: Literal["BUY", "SELL"]
    mode: Literal["fractional", "standard"]
    gross_budget: Decimal = Field(ge=0)
    net_budget: Decimal = Field(ge=0)
    price: Decimal = Field(gt=0)
    quantity: Decimal = Field(ge=Decimal("0"))
    fee_breakdown: FeeBreakdown
    fee_ratio: Decimal = Field(ge=0)
    veto_reason: str | None = None


class ActivePosition(PydanticModel):
    ticker: str
    entry_date: date
    entry_price: Decimal = Field(gt=0)
    quantity: Decimal = Field(ge=Decimal("0.0001"))
    sector: str = "Unknown"
    industry: str = "Unknown"
    volatility: Decimal | None = Field(default=None, ge=0)
    signal_id: int | None = None


class ClosedTrade(PydanticModel):
    ticker: str
    side: Literal["BUY", "SELL"]
    entry_date: date
    exit_date: date
    entry_price: Decimal = Field(gt=0)
    exit_price: Decimal = Field(gt=0)
    quantity: Decimal = Field(ge=Decimal("0.0001"))
    gross_notional: Decimal = Field(ge=0)
    net_notional: Decimal = Field(ge=0)
    fees: FeeBreakdown
    pnl: Decimal
    return_pct: Decimal


class PriceBar(PydanticModel):
    ticker: str
    trading_date: date
    open: Decimal | None = None
    high: Decimal | None = None
    low: Decimal | None = None
    close: Decimal | None = None
    adjusted_close: Decimal
    volume: int = Field(ge=0)
    dollar_volume: Decimal | None = None
