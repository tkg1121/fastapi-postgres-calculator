"""Validate registration data and the public representation of a user."""

from datetime import datetime, timezone
from types import SimpleNamespace

from pydantic import ValidationError
import pytest

from app.schemas import UserCreate, UserRead


pytestmark = pytest.mark.unit
VALID_USER = {
    "username": "trent_123",
    "email": "trent@example.com",
    "password": "A long test password!",
}


def test_registration_normalizes_identifiers_but_preserves_password():
    raw_password = " leading and trailing spaces "
    user = UserCreate(
        username="  Trent_123  ",
        email="  Trent@EXAMPLE.COM  ",
        password=raw_password,
    )

    assert user.username == "trent_123"
    assert str(user.email) == "trent@example.com"
    assert user.password.get_secret_value() == raw_password
    assert raw_password not in repr(user)
    assert raw_password not in user.model_dump_json()


@pytest.mark.parametrize("username", ["abc", "user_123", "x" * 50])
def test_username_valid_boundaries(username):
    assert UserCreate(**{**VALID_USER, "username": username}).username == username


@pytest.mark.parametrize("username", [
    "", "ab", "x" * 51, "space inside", "user-name", "user.name", "\u00e9clair", None, 123,
])
def test_invalid_usernames(username):
    with pytest.raises(ValidationError):
        UserCreate(**{**VALID_USER, "username": username})


@pytest.mark.parametrize("email", [
    "", "missing-at-symbol", "name@", "@example.com", "name@localhost",
    "two@@example.com", None, 123,
])
def test_invalid_emails(email):
    with pytest.raises(ValidationError):
        UserCreate(**{**VALID_USER, "email": email})


@pytest.mark.parametrize("length", [12, 128])
def test_password_valid_length_boundaries(length):
    password = "x" * length
    assert UserCreate(**{**VALID_USER, "password": password}).password.get_secret_value() == password


@pytest.mark.parametrize("password", ["", "x" * 11, "x" * 129, None, 123])
def test_invalid_passwords(password):
    with pytest.raises(ValidationError):
        UserCreate(**{**VALID_USER, "password": password})


@pytest.mark.parametrize("field", ["username", "email", "password"])
def test_registration_requires_all_fields(field):
    payload = dict(VALID_USER)
    payload.pop(field)

    with pytest.raises(ValidationError):
        UserCreate(**payload)


@pytest.mark.parametrize("field,value", [
    ("password_hash", "caller-controlled-hash"), ("id", 42), ("created_at", "2026-01-01T00:00:00Z"),
])
def test_registration_does_not_accept_server_managed_fields(field, value):
    with pytest.raises(ValidationError):
        UserCreate(**{**VALID_USER, field: value})


def test_validation_error_text_hides_rejected_password():
    rejected_password = "secret" * 30
    with pytest.raises(ValidationError) as failure:
        UserCreate(**{**VALID_USER, "password": rejected_password})
    assert rejected_password not in str(failure.value)


def test_public_schema_reads_model_attributes_and_omits_credentials():
    created_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    stored_user = SimpleNamespace(
        id=17,
        username="trent_123",
        email="trent@example.com",
        created_at=created_at,
        password_hash="$argon2id$private-stored-hash",
        password="A long test password!",
    )

    response = UserRead.model_validate(stored_user)

    assert response.model_dump() == {
        "id": 17, "username": "trent_123", "email": "trent@example.com", "created_at": created_at,
    }
    assert "password" not in response.model_dump_json()
    assert "private-stored-hash" not in response.model_dump_json()
