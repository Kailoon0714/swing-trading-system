from __future__ import annotations

from decimal import Decimal

from app.db.models import SizingDecision
from app.etl.fetch_prices import calculate_fee_inclusive_quantity
from app.utils.config import settings


def volatility_scaled_fraction(
    asset_volatility: Decimal | float,
    universe_inverse_volatility_sum: Decimal | float,
    max_position_fraction: Decimal | float | None = None,
) -> Decimal:
    vol = Decimal(str(asset_volatility))
    inv_sum = Decimal(str(universe_inverse_volatility_sum))
    max_fraction = Decimal(str(max_position_fraction if max_position_fraction is not None else settings.max_position_fraction))
    if vol <= 0 or inv_sum <= 0:
        return Decimal("0")
    return max_fraction * ((Decimal("1") / vol) / inv_sum)


def size_position(
    cash_usd: Decimal | float | str,
    price: Decimal | float | str,
    side: str = "BUY",
    scaled_position_fraction: Decimal | float | str | None = None,
) -> SizingDecision:
    return calculate_fee_inclusive_quantity(
        current_cash=cash_usd,
        price=price,
        side=side,
        max_position_fraction=scaled_position_fraction,
    )
