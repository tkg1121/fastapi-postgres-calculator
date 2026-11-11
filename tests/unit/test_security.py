"""Password verification must work without ever storing the original password."""

import pytest

from app.security import hash_password, verify_password


pytestmark = pytest.mark.unit


@pytest.mark.parametrize("password", [
    "A long test password!",
    "spaces are preserved ",
    "p\u00e4ssword-\u03bb-\u65e5\u672c\u8a9e-123",
])
def test_argon2_hash_verifies_only_the_original_password(password):
    stored_hash = hash_password(password)

    assert stored_hash.startswith("$argon2id$")
    assert password not in stored_hash
    assert verify_password(password, stored_hash)
    assert not verify_password(password + "wrong", stored_hash)


def test_identical_passwords_receive_distinct_salts():
    password = "A shared password phrase"
    first_hash = hash_password(password)
    second_hash = hash_password(password)

    assert first_hash != second_hash
    assert verify_password(password, first_hash)
    assert verify_password(password, second_hash)


@pytest.mark.parametrize("stored_hash", [
    "", "not-a-password-hash", "$argon2id$broken", "5f4dcc3b5aa765d61d8327deb882cf99",
])
def test_malformed_hashes_are_rejected_without_raising(stored_hash):
    assert verify_password("A long test password!", stored_hash) is False


def test_password_whitespace_is_significant():
    stored_hash = hash_password(" leading and trailing spaces ")

    assert verify_password(" leading and trailing spaces ", stored_hash)
    assert not verify_password("leading and trailing spaces", stored_hash)
