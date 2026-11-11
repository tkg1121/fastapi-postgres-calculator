from pathlib import Path
import os
import socket
import subprocess
import sys
import time
from uuid import uuid4

from fastapi.testclient import TestClient
import httpx
import pytest

from main import app


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(scope="session")
def postgres_engine():
    """Require the migrated PostgreSQL database for tests marked database."""
    from sqlalchemy import create_engine, inspect, text
    from app.database import get_database_url

    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        if os.environ.get("REQUIRE_DATABASE_TESTS") == "1":
            pytest.fail("DATABASE_URL is required for the PostgreSQL integration tests.")
        pytest.skip("Set DATABASE_URL to run the PostgreSQL integration tests.")
    url = get_database_url()
    if url.get_backend_name() != "postgresql":
        pytest.fail("Database integration tests require PostgreSQL, not SQLite.")
    engine = create_engine(url, hide_parameters=True)
    try:
        with engine.connect() as connection:
            assert "PostgreSQL" in connection.scalar(text("SELECT version()"))
        assert inspect(engine).has_table("users", schema="calculator"), (
            "Run python -m alembic upgrade head before database tests."
        )
        yield engine
    finally:
        engine.dispose()


@pytest.fixture
def db_session(postgres_engine):
    """Let routes commit while rolling back every test's changes afterward."""
    from sqlalchemy.orm import Session

    with postgres_engine.connect() as connection:
        transaction = connection.begin()
        with Session(
            bind=connection,
            join_transaction_mode="create_savepoint",
            expire_on_commit=False,
        ) as session:
            try:
                yield session
            finally:
                session.close()
                transaction.rollback()


@pytest.fixture
def user_client(db_session):
    from app.database import get_db

    def override_session():
        yield db_session

    previous_override = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = override_session
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        if previous_override is None:
            app.dependency_overrides.pop(get_db, None)
        else:
            app.dependency_overrides[get_db] = previous_override


@pytest.fixture
def user_payload():
    identifier = uuid4().hex[:20]
    return {
        "username": f"user_{identifier}",
        "email": f"user_{identifier}@example.com",
        "password": "A long test password!",
    }


@pytest.fixture(scope="session")
def fastapi_server(tmp_path_factory):
    """Start a separate server on an available loopback port for browser tests."""
    root = Path(__file__).resolve().parents[1]
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    url = f"http://127.0.0.1:{port}"
    log_path = tmp_path_factory.mktemp("server") / "uvicorn.log"
    with log_path.open("w", encoding="utf-8") as log:
        process = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", str(port)],
            cwd=root, stdout=log, stderr=subprocess.STDOUT,
        )
        try:
            deadline = time.monotonic() + 30
            with httpx.Client(timeout=1, trust_env=False) as connection:
                while time.monotonic() < deadline:
                    if process.poll() is not None:
                        raise RuntimeError(log_path.read_text(encoding="utf-8"))
                    try:
                        if connection.get(url).status_code == 200:
                            break
                    except httpx.TransportError:
                        time.sleep(0.1)
                else:
                    raise RuntimeError("FastAPI server did not start within 30 seconds.")
            yield url
        finally:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
