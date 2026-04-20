from __future__ import annotations

from pathlib import Path

from sqlalchemy.engine import Engine
from sqlmodel import SQLModel, create_engine

DEFAULT_DATABASE_URL = "sqlite:///data/budgetwings.db"


def get_database_engine(database_url: str = DEFAULT_DATABASE_URL) -> Engine:
    if database_url.startswith("sqlite:///"):
        db_path = database_url.removeprefix("sqlite:///")
        if db_path and db_path != ":memory:":
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    return create_engine(database_url, connect_args=connect_args)


def create_db_and_tables(engine: Engine | None = None) -> None:
    resolved_engine = engine or get_database_engine()
    SQLModel.metadata.create_all(resolved_engine)
