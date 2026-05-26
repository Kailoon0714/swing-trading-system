from __future__ import annotations

from dataclasses import dataclass

from app.utils.config import settings


@dataclass(frozen=True)
class PositionDecision:
    allowed: bool
    quantity: int
    reason: str


def size_position(cash_usd: float, price: float, open_positions: int) -> PositionDecision:
    if open_positions >= settings.max_open_positions:
        return PositionDecision(False, 0, "max_open_positions_reached")
    if price <= 0:
        return PositionDecision(False, 0, "invalid_price")

    max_notional = cash_usd * settings.max_position_fraction
    quantity = int(max_notional // price)
    if quantity < 1:
        return PositionDecision(False, 0, "insufficient_cash_for_one_share")

    return PositionDecision(True, quantity, "allowed")
