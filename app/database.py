"""PostgreSQL connections for health checks, migrations, and user requests."""

from functools import lru_cache
import os

import psycopg
from sqlalchemy import URL, create_engine
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.exc import ArgumentError
from sqlalchemy.orm import Session


def get_database_url() -> URL:
    """Build a PostgreSQL URL without interpolating passwords into a string."""
    configured_url = os.getenv("DATABASE_URL")
    if configured_url:
        try:
            url = make_url(configured_url)
        except (ArgumentError, ValueError, TypeError):
            raise ValueError("Invalid database configuration.") from None
        if url.drivername in {"postgres", "postgresql", "postgres+psycopg"}:
            url = url.set(drivername="postgresql+psycopg")
        if url.drivername != "postgresql+psycopg":
            raise ValueError("DATABASE_URL must use PostgreSQL with psycopg.")
        return url

    try:
        port = int(os.getenv("PGPORT", "5432"))
    except ValueError as error:
        raise ValueError("Invalid database port.") from error
    return URL.create(
        "postgresql+psycopg",
        username=os.getenv("PGUSER", "postgres"),
        password=os.getenv("PGPASSWORD"),
        host=os.getenv("PGHOST", "localhost"),
        port=port,
        database=os.getenv("PGDATABASE", "fastapi_db"),
    )


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    """Create the pool lazily, without opening a connection at import time."""
    return create_engine(
        get_database_url(),
        pool_pre_ping=True,
        hide_parameters=True,
        connect_args={"connect_timeout": 3},
    )


def get_db():
    """Give each request its own session and close it when the request ends."""
    with Session(get_engine(), expire_on_commit=False) as session:
        yield session


def get_database_name() -> str:
    """Check the same DATABASE_URL or PG environment used by user sessions."""
    connection_args = ()
    if os.getenv("DATABASE_URL"):
        url = get_database_url().set(drivername="postgresql")
        connection_args = (url.render_as_string(hide_password=False),)
    with psycopg.connect(*connection_args, connect_timeout=3) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT current_database()")
            return cursor.fetchone()[0]
