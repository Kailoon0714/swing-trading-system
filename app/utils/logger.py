from __future__ import annotations

import sys

from loguru import logger

from app.utils.config import settings


def configure_logging() -> None:
    logger.remove()
    logger.add(
        sys.stderr,
        level=settings.log_level.upper(),
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level}</level> | {name}:{line} | {message}",
    )


def get_logger(name: str):
    configure_logging()
    return logger.bind(module=name)
