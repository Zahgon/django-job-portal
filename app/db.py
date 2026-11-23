"""Database engine and session handling.

The engine is built from ``DATABASE_URL`` and can be rebound at run time with
:func:`set_database_url`, which is how a test run points the application at a
throwaway database without importing it again.
"""
from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings


class Base(DeclarativeBase):
    """The declarative base every model inherits from."""


def _build_engine(url: str) -> Engine:
    kwargs: dict = {"future": True}
    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
    return create_engine(url, **kwargs)


engine: Engine = _build_engine(settings.database_url)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False,
                            future=True)


@event.listens_for(Engine, "connect")
def _enable_sqlite_foreign_keys(dbapi_connection, _record):
    """SQLite checks foreign keys only when asked to, and the schema relies on it."""
    if dbapi_connection.__class__.__module__.startswith("sqlite3"):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


def set_database_url(url: str) -> Engine:
    """Point the application at another database and return the new engine."""
    global engine
    settings.database_url = url
    previous, engine = engine, _build_engine(url)
    SessionLocal.configure(bind=engine)
    if previous is not None:
        previous.dispose()
    return engine


def get_session() -> Iterator[Session]:
    """Request-scoped session.

    The route handler owns the transaction; a request that fails has whatever it
    had started rolled back rather than left open for the next one.
    """
    session = SessionLocal()
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@contextmanager
def session_scope() -> Iterator[Session]:
    """A session for code outside a request, committed on a clean exit."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
