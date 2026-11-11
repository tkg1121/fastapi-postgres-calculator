from unittest.mock import MagicMock

import psycopg
import pytest

from app import database


pytestmark = pytest.mark.integration


@pytest.fixture
def database_connection(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    connect = MagicMock()
    connection = connect.return_value.__enter__.return_value
    cursor = connection.cursor.return_value.__enter__.return_value
    cursor.fetchone.return_value = ("fastapi_db",)
    monkeypatch.setattr(database.psycopg, "connect", connect)
    return connect, connection, cursor


def test_database_health_and_connection_cleanup(client, database_connection):
    connect, connection, cursor = database_connection

    response = client.get("/health/db")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "fastapi_db"}
    connect.assert_called_once_with(connect_timeout=3)
    cursor.execute.assert_called_once_with("SELECT current_database()")
    connection.cursor.return_value.__exit__.assert_called_once()
    connect.return_value.__exit__.assert_called_once()


@pytest.mark.parametrize("driver", ["postgresql+psycopg", "postgresql", "postgres"])
def test_database_health_honors_database_url(client, database_connection, monkeypatch, driver, caplog):
    connect, _, cursor = database_connection
    monkeypatch.setenv(
        "DATABASE_URL",
        f"{driver}://url_user:p%40ss%25word@url-db:5544/url_database?sslmode=require",
    )
    monkeypatch.setenv("PGHOST", "different-db")
    monkeypatch.setenv("PGDATABASE", "different_database")
    cursor.fetchone.return_value = ("url_database",)

    response = client.get("/health/db")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "url_database"}
    assert connect.call_args.kwargs == {"connect_timeout": 3}
    assert psycopg.conninfo.conninfo_to_dict(connect.call_args.args[0]) == {
        "user": "url_user", "password": "p@ss%word", "host": "url-db",
        "port": "5544", "dbname": "url_database", "sslmode": "require",
    }
    assert "p@ss%word" not in response.text
    assert "p@ss%word" not in caplog.text


def test_invalid_database_url_is_generic(client, database_connection, monkeypatch, caplog):
    connect, _, _ = database_connection
    monkeypatch.setenv("DATABASE_URL", "invalid-private-connection-value")

    response = client.get("/health/db")

    assert response.status_code == 503
    assert response.json() == {"error": "Database unavailable."}
    assert "invalid-private-connection-value" not in response.text
    assert "invalid-private-connection-value" not in caplog.text
    connect.assert_not_called()


@pytest.mark.parametrize("failure_stage", ["connection", "query"])
def test_database_failure_is_generic(client, database_connection, failure_stage, caplog):
    connect, connection, cursor = database_connection
    error = psycopg.OperationalError("private connection credentials")
    if failure_stage == "connection":
        connect.side_effect = error
    else:
        cursor.execute.side_effect = error

    response = client.get("/health/db")

    assert response.status_code == 503
    assert response.json() == {"error": "Database unavailable."}
    assert "private connection credentials" not in response.text
    assert "private connection credentials" not in caplog.text
    assert "Database health check failed" in caplog.text
    if failure_stage == "query":
        connection.cursor.return_value.__exit__.assert_called_once()
        connect.return_value.__exit__.assert_called_once()
