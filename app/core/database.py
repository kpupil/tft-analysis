"""Database bootstrap for the collector state store."""
import os

from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import settings


class Base(DeclarativeBase):
    pass


def _normalized_url(url: str) -> str:
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


def _ensure_sqlite_parent(url: str) -> None:
    parsed = make_url(url)
    if not parsed.drivername.startswith("sqlite"):
        return
    if not parsed.database or parsed.database == ":memory:":
        return
    parent = os.path.dirname(parsed.database)
    if parent:
        os.makedirs(parent, exist_ok=True)


DATABASE_URL = _normalized_url(settings.database_url)
_ensure_sqlite_parent(DATABASE_URL)

engine = create_engine(DATABASE_URL, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)


def init_db() -> None:
    # Import models so SQLAlchemy registers all table metadata before create_all.
    from app.core import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
