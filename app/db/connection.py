from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.utils.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)


@lru_cache
def get_engine() -> Engine:
    if not settings.database_url:
        raise RuntimeError("DATABASE_URL is required for database operations")

    logger.debug("Creating SQLAlchemy engine")
    return create_engine(
        settings.database_url,
        pool_pre_ping=True,
        pool_recycle=1800,
        pool_size=5,
        max_overflow=5,
        future=True,
    )


@lru_cache
def get_session_factory() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), autoflush=False, autocommit=False, expire_on_commit=False, future=True)


@contextmanager
def session_scope() -> Iterator[Session]:
    session = get_session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        logger.exception("Database transaction rolled back")
        raise
    finally:
        session.close()


def fetch_active_universe() -> list[str]:
    query = text(
        """
        SELECT ticker
        FROM assets
        WHERE is_active = TRUE
        ORDER BY ticker;
        """
    )
    with get_engine().connect() as connection:
        tickers = [row[0] for row in connection.execute(query)]

    logger.info("Loaded {} active tickers from database universe", len(tickers))
    return tickers


def stream_query(sql: str, params: dict[str, object] | None = None, chunksize: int = 50_000) -> Iterator[object]:
    connection = get_engine().connect().execution_options(stream_results=True)
    try:
        result = connection.execution_options(yield_per=chunksize).execute(text(sql), params or {})
        while True:
            rows = result.fetchmany(chunksize)
            if not rows:
                break
            yield rows
    finally:
        connection.close()
