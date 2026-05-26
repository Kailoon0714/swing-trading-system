from __future__ import annotations

from app.utils.logger import get_logger

logger = get_logger(__name__)


class MoomooExecutor:
    """Placeholder boundary for FutuOpenD integration.

    Live broker wiring should stay isolated here so ETL and model code never imports broker SDKs.
    """

    def place_order(self, ticker: str, side: str, quantity: int) -> str:
        logger.info("Paper order: {} {} {}", side, quantity, ticker)
        return f"PAPER-{ticker}-{side}-{quantity}"
