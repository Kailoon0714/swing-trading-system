from __future__ import annotations

from app.utils.logger import get_logger

logger = get_logger(__name__)


def poll_pending_signals() -> None:
    logger.info("Signal polling is not wired yet. Implement after Supabase live schema is deployed.")
