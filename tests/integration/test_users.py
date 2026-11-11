"""Exercise registration and database constraints against real PostgreSQL."""

from datetime import datetime, timezone
import logging

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError, OperationalError

from app.models import User
from app.security import hash_password, verify_password


pytestmark = [pytest.mark.integration, pytest.mark.database]


def assert_public_user(body, payload):
    assert set(body) == {"id", "username", "email", "created_at"}
    assert isinstance(body["id"], int) and body["id"] > 0
    assert body["username"] == payload["username"].strip().lower()
    assert body["email"] == payload["email"].strip().lower()
    assert datetime.fromisoformat(body["created_at"].replace("Z", "+00:00")).utcoffset() is not None


def test_registration_stores_hash_and_returns_only_public_fields(user_client, db_session, user_payload, caplog):
    with caplog.at_level(logging.INFO):
        response = user_client.post("/users", json=user_payload)

    assert response.status_code == 201
    assert_public_user(response.json(), user_payload)
    user = db_session.get(User, response.json()["id"])
    assert user.password_hash.startswith("$argon2id$")
    assert user.password_hash != user_payload["password"]
    assert verify_password(user_payload["password"], user.password_hash)
    assert user.created_at.tzinfo is not None
    assert abs((datetime.now(timezone.utc) - user.created_at).total_seconds()) < 60
    assert user_payload["password"] not in response.text
    assert user_payload["password"] not in caplog.text
    assert user.password_hash not in response.text
    assert user.password_hash not in caplog.text


def test_get_user_round_trip_omits_credentials(user_client, db_session, user_payload):
    created = user_client.post("/users", json=user_payload)
    assert created.status_code == 201

    retrieved = user_client.get(f"/users/{created.json()['id']}")

    assert retrieved.status_code == 200
    assert retrieved.json() == created.json()
    assert_public_user(retrieved.json(), user_payload)
    assert db_session.get(User, retrieved.json()["id"]).password_hash not in retrieved.text


def test_unknown_user_returns_not_found(user_client):
    response = user_client.get("/users/2147483647")

    assert response.status_code == 404
    assert response.json() == {"error": "User not found."}


@pytest.mark.parametrize("user_id", ["0", "-1", "not-an-integer", "1.5"])
def test_user_lookup_requires_positive_integer(user_client, user_id):
    response = user_client.get(f"/users/{user_id}")

    assert response.status_code == 422


def test_invalid_user_path_is_not_copied_into_logs(user_client, caplog):
    secret = "sensitive-password-appearing-in-path"
    with caplog.at_level(logging.INFO, logger="main"):
        response = user_client.get(f"/users/{secret}")

    assert response.status_code == 422
    assert secret not in response.text
    application_logs = "\n".join(record.getMessage() for record in caplog.records if record.name == "main")
    assert secret not in application_logs


def test_registration_rejects_caller_supplied_hash(user_client, db_session, user_payload, caplog):
    injected_hash = "$argon2id$caller-controlled-private-hash"
    response = user_client.post("/users", json={**user_payload, "password_hash": injected_hash})

    assert response.status_code == 422
    assert injected_hash not in response.text
    assert injected_hash not in caplog.text
    assert db_session.scalar(select(User).where(User.username == user_payload["username"])) is None


@pytest.mark.parametrize("field", ["username", "email"])
@pytest.mark.parametrize("different_case", [False, True])
def test_duplicate_registration_is_rejected_after_normalization(
    user_client, db_session, user_payload, field, different_case,
):
    assert user_client.post("/users", json=user_payload).status_code == 201
    duplicate = {
        **user_payload,
        "username": user_payload["username"] + "_new",
        "email": "new_" + user_payload["email"],
    }
    duplicate[field] = user_payload[field].upper() if different_case else user_payload[field]

    response = user_client.post("/users", json=duplicate)

    assert response.status_code == 409
    assert response.json() == {"error": "Username or email already registered."}
    assert db_session.scalar(select(func.count()).select_from(User).where(
        getattr(User, field) == user_payload[field]
    )) == 1


def test_session_recovers_after_duplicate_registration(user_client, user_payload):
    first = user_client.post("/users", json=user_payload)
    assert first.status_code == 201
    assert user_client.post("/users", json=user_payload).status_code == 409
    another = {
        **user_payload,
        "username": user_payload["username"] + "_next",
        "email": "next_" + user_payload["email"],
    }

    second = user_client.post("/users", json=another)

    assert second.status_code == 201
    assert second.json()["id"] != first.json()["id"]
    assert user_client.get(f"/users/{first.json()['id']}").status_code == 200


@pytest.mark.parametrize("field", ["username", "email"])
def test_postgres_itself_enforces_uniqueness(db_session, user_payload, field):
    first = User(
        username=user_payload["username"],
        email=user_payload["email"],
        password_hash=hash_password(user_payload["password"]),
    )
    db_session.add(first)
    db_session.commit()
    conflicting = {
        "username": user_payload["username"] + "_other",
        "email": "other_" + user_payload["email"],
        "password_hash": first.password_hash,
    }
    conflicting[field] = user_payload[field]
    db_session.add(User(**conflicting))

    with pytest.raises(IntegrityError) as failure:
        db_session.commit()
    assert failure.value.orig.sqlstate == "23505"
    db_session.rollback()

    assert db_session.scalar(select(User.id).where(User.username == first.username)) == first.id


@pytest.mark.parametrize("field", ["username", "email", "password_hash"])
def test_postgres_rejects_missing_required_user_columns(db_session, user_payload, field):
    values = {
        "username": user_payload["username"],
        "email": user_payload["email"],
        "password_hash": hash_password(user_payload["password"]),
    }
    values[field] = None
    db_session.add(User(**values))

    with pytest.raises(IntegrityError) as failure:
        db_session.flush()
    assert failure.value.orig.sqlstate == "23502"
    db_session.rollback()


@pytest.mark.parametrize("field,value", [
    ("email", "not-an-email"), ("email", "person@"),
    ("username", "ab"), ("username", "with spaces"),
    ("password", "short"), ("password", "x" * 129),
])
def test_invalid_registration_never_reaches_database(user_client, db_session, user_payload, field, value, caplog):
    before = db_session.scalar(select(func.count()).select_from(User))
    payload = {**user_payload, field: value}

    response = user_client.post("/users", json=payload)

    assert response.status_code == 422
    assert response.json() == {"error": "Invalid user data."}
    assert db_session.scalar(select(func.count()).select_from(User)) == before
    assert payload["password"] not in response.text
    assert payload["password"] not in caplog.text


def test_malformed_registration_json_does_not_echo_password(user_client, user_payload, caplog):
    response = user_client.post(
        "/users",
        content='{"password": "' + user_payload["password"] + '",',
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 422
    assert user_payload["password"] not in response.text
    assert user_payload["password"] not in caplog.text


def test_database_errors_are_generic_and_do_not_expose_credentials(
    user_client, db_session, user_payload, monkeypatch, caplog,
):
    def fail_commit():
        raise OperationalError(
            "INSERT INTO calculator.users",
            {"password_hash": "private-password-hash"},
            RuntimeError("private-database-credentials"),
        )

    monkeypatch.setattr(db_session, "commit", fail_commit)
    response = user_client.post("/users", json=user_payload)

    assert response.status_code == 503
    assert response.json() == {"error": "Database unavailable."}
    for secret in [user_payload["password"], "private-password-hash", "private-database-credentials"]:
        assert secret not in response.text
        assert secret not in caplog.text
