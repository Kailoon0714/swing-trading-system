from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.utils.config import settings


def get_engine() -> Engine:
    if not settings.database_url:
        raise RuntimeError("DATABASE_URL is required for database operations")
    return create_engine(settings.database_url, pool_pre_ping=True, future=True)


def get_session_factory() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), autoflush=False, autocommit=False, future=True)
