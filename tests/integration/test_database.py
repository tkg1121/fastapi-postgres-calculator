from unittest.mock import MagicMock

import psycopg
import pytest

from app import database


pytestmark = pytest.mark.integration


@pytest.fixture
def database_connection(monkeypatch):
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
