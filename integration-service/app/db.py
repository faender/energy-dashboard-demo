"""Datenbank-Setup (SQLAlchemy, SQLite-Datei) für die Integrationsschicht."""
from __future__ import annotations

import os

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import DATABASE_URL

if DATABASE_URL.startswith("sqlite:///./"):
    db_path = DATABASE_URL.replace("sqlite:///./", "")
    os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)

# Großzügiger, aber begrenzter Pool: die Default-Größe (5 + 10 Overflow) ist bei
# mehreren gleichzeitig pollenden Dashboards zu knapp ("QueuePool limit
# reached"), ein unbegrenzter Pool (NullPool) lässt sich dagegen unter Last zu
# vielen SQLite-Verbindungen gleichzeitig öffnen und verschärft die
# WAL-Reader-Konkurrenz eher, statt sie zu entschärfen.
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
    pool_size=10,
    max_overflow=10,
)

if DATABASE_URL.startswith("sqlite"):
    # WAL erlaubt nebenläufige Reader neben einem Writer (statt sich mit dem
    # Live-Poller über "database is locked" zu blockieren); busy_timeout
    # lässt verbleibende Lock-Konflikte kurz retryen statt sofort zu failen.
    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=10000")
        cursor.close()

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def get_session() -> Session:
    return SessionLocal()
