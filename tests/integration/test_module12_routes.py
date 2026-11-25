"""Exercise user login and calculation BREAD endpoints against PostgreSQL."""

import logging

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import OperationalError

from app.models import Calculation, User
from app.security import verify_password


pytestmark = [pytest.mark.integration, pytest.mark.database]
CALCULATION_FIELDS = {"id", "a", "b", "type", "result", "created_at"}


@pytest.fixture
def registered_user(user_client, user_payload):
    response = user_client.post("/users/register", json=user_payload)
    assert response.status_code == 201
    return response.json()


@pytest.fixture
def saved_calculation(user_client):
    response = user_client.post("/calculations", json={"type": "add", "a": 2, "b": 3})
    assert response.status_code == 201
    return response.json()


def test_register_endpoint_stores_hash_and_preserves_existing_lookup(
    user_client, db_session, user_payload, caplog,
):
    with caplog.at_level(logging.INFO):
        response = user_client.post("/users/register", json=user_payload)

    assert response.status_code == 201
    public = response.json()
    assert set(public) == {"id", "username", "email", "created_at"}
    stored = db_session.get(User, public["id"])
    assert verify_password(user_payload["password"], stored.password_hash)
    assert stored.password_hash.startswith("$argon2id$")
    assert user_client.get(f"/users/{public['id']}").json() == public
    for secret in [user_payload["password"], stored.password_hash]:
        assert secret not in response.text
        assert secret not in caplog.text


@pytest.mark.parametrize("field", ["username", "email"])
def test_register_alias_enforces_normalized_unique_identity(
    user_client, registered_user, user_payload, field,
):
    duplicate = {
        **user_payload,
        "username": user_payload["username"] + "_new",
        "email": "new_" + user_payload["email"],
        field: " " + user_payload[field].upper() + " ",
    }

    response = user_client.post("/users/register", json=duplicate)

    assert response.status_code == 409
    assert response.json() == {"error": "Username or email already registered."}


@pytest.mark.parametrize("identity", ["username", "email"])
def test_login_accepts_normalized_identity_and_returns_public_user(
    user_client, registered_user, user_payload, db_session, identity, caplog,
):
    with caplog.at_level(logging.INFO):
        response = user_client.post("/users/login", json={
            identity: " " + user_payload[identity].upper() + " ",
            "password": user_payload["password"],
        })

    assert response.status_code == 200
    assert response.json() == registered_user
    assert "access_token" not in response.json()
    assert user_payload["password"] not in caplog.text
    assert db_session.get(User, registered_user["id"]).password_hash not in response.text


@pytest.mark.parametrize("identity", ["username", "email"])
def test_login_does_not_distinguish_wrong_password_from_unknown_account(
    user_client, registered_user, user_payload, identity, caplog,
):
    wrong_password = "Definitely the wrong password!"
    wrong = user_client.post("/users/login", json={
        identity: user_payload[identity], "password": wrong_password,
    })
    unknown_identity = "unknown_" + user_payload[identity]
    unknown = user_client.post("/users/login", json={
        identity: unknown_identity, "password": wrong_password,
    })

    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json() == {"error": "Invalid credentials."}
    assert wrong_password not in caplog.text
    assert unknown_identity not in caplog.text


@pytest.mark.parametrize("payload", [
    {},
    {"username": "valid_user"},
    {"password": "A valid password!"},
    {"username": "valid_user", "email": "valid@example.com", "password": "A valid password!"},
    {"email": "not-an-email", "password": "A valid password!"},
    {"username": "bad user", "password": "A valid password!"},
    {"username": "valid_user", "password": ""},
    {"username": "valid_user", "password": "x" * 129},
    {"username": "valid_user", "password": True},
    {"username": "valid_user", "password": "A valid password!", "password_hash": "injected-secret"},
])
def test_login_invalid_input_is_generic_and_private(user_client, payload, caplog):
    response = user_client.post("/users/login", json=payload)

    assert response.status_code == 422
    assert response.json() == {"error": "Invalid user data."}
    for value in [payload.get("password"), payload.get("password_hash")]:
        if isinstance(value, str) and value:
            assert value not in response.text
            assert value not in caplog.text


@pytest.mark.parametrize("path", ["/users/register", "/users/login"])
def test_malformed_user_json_does_not_echo_credentials(user_client, path, caplog):
    secret = "Private malformed-body password!"
    response = user_client.post(
        path, content='{"password": "' + secret + '",',
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 422
    assert secret not in response.text
    assert secret not in caplog.text


def test_login_rejects_corrupt_stored_hash(user_client, registered_user, user_payload, db_session, caplog):
    stored = db_session.get(User, registered_user["id"])
    stored.password_hash = "invalid-private-stored-hash"
    db_session.commit()

    response = user_client.post("/users/login", json={
        "username": user_payload["username"], "password": user_payload["password"],
    })

    assert response.status_code == 401
    assert response.json() == {"error": "Invalid credentials."}
    assert stored.password_hash not in response.text
    assert stored.password_hash not in caplog.text


@pytest.mark.parametrize("operation,a,b,result", [
    ("add", 2, 3, 5), ("Sub", 10, 4, 6),
    ("multiply", -4, 5, -20), ("divide", 9, 2, 4.5),
])
def test_create_calculation_endpoint_persists_computed_result(
    user_client, db_session, operation, a, b, result,
):
    response = user_client.post("/calculations", json={"type": operation, "a": a, "b": b})

    assert response.status_code == 201
    body = response.json()
    assert set(body) == CALCULATION_FIELDS
    assert body["result"] == pytest.approx(result)
    assert body["type"] == ("subtract" if operation == "Sub" else operation)
    stored = db_session.get(Calculation, body["id"])
    assert stored.result == pytest.approx(result)
    assert stored.created_at.tzinfo is not None


def test_calculation_bread_round_trip(user_client, saved_calculation, db_session):
    path = f"/calculations/{saved_calculation['id']}"
    assert user_client.get(path).json() == saved_calculation
    browse = user_client.get("/calculations")
    assert browse.status_code == 200
    assert saved_calculation in browse.json()

    edited = user_client.put(path, json={"type": "multiply", "a": 4, "b": 5})
    assert edited.status_code == 200
    assert edited.json() == {
        **saved_calculation, "type": "multiply", "a": 4.0, "b": 5.0, "result": 20.0,
    }
    assert user_client.get(path).json() == edited.json()
    assert db_session.get(Calculation, saved_calculation["id"]).result == 20

    deleted = user_client.delete(path)
    assert deleted.status_code == 204
    assert deleted.content == b""
    assert user_client.get(path).status_code == 404
    assert db_session.get(Calculation, saved_calculation["id"]) is None


def test_browse_orders_calculations_by_ascending_id(user_client):
    created_ids = []
    for number in [7, 2, 9]:
        response = user_client.post("/calculations", json={"type": "add", "a": number, "b": 1})
        assert response.status_code == 201
        created_ids.append(response.json()["id"])

    response = user_client.get("/calculations")

    assert response.status_code == 200
    ids = [row["id"] for row in response.json()]
    assert ids == sorted(ids)
    assert [identifier for identifier in ids if identifier in created_ids] == created_ids
    assert all(set(row) == CALCULATION_FIELDS for row in response.json())


@pytest.mark.parametrize("method", ["get", "put", "delete"])
def test_unknown_calculation_returns_not_found(user_client, method):
    options = {"json": {"type": "add", "a": 1, "b": 2}} if method == "put" else {}
    response = getattr(user_client, method)("/calculations/2147483647", **options)

    assert response.status_code == 404
    assert response.json() == {"error": "Calculation not found."}


@pytest.mark.parametrize("method", ["post", "put"])
@pytest.mark.parametrize("payload", [
    {"type": "power", "a": 2, "b": 3},
    {"type": "divide", "a": 2, "b": 0},
    {"type": "add", "a": True, "b": 2},
    {"type": "add", "a": 1, "b": "2"},
    {"type": "add", "a": 1},
    {"type": "add", "a": 1, "b": 2, "result": 999},
])
def test_invalid_calculation_write_does_not_change_database(
    user_client, db_session, saved_calculation, method, payload,
):
    before = db_session.scalar(select(func.count()).select_from(Calculation))
    path = "/calculations" if method == "post" else f"/calculations/{saved_calculation['id']}"

    response = getattr(user_client, method)(path, json=payload)

    assert response.status_code == 422
    assert db_session.scalar(select(func.count()).select_from(Calculation)) == before
    assert user_client.get(f"/calculations/{saved_calculation['id']}").json() == saved_calculation


@pytest.mark.parametrize("literal", ["NaN", "Infinity", "-Infinity"])
@pytest.mark.parametrize("method", ["post", "put"])
def test_calculation_write_rejects_nonfinite_json(user_client, saved_calculation, literal, method):
    path = "/calculations" if method == "post" else f"/calculations/{saved_calculation['id']}"
    response = getattr(user_client, method)(
        path, content='{"type":"add","a":' + literal + ',"b":2}',
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 422


@pytest.mark.parametrize("method", ["post", "put"])
def test_overflow_is_rejected_without_modifying_existing_calculation(
    user_client, db_session, saved_calculation, method,
):
    before = db_session.scalar(select(func.count()).select_from(Calculation))
    path = "/calculations" if method == "post" else f"/calculations/{saved_calculation['id']}"
    response = getattr(user_client, method)(path, json={"type": "multiply", "a": 1e308, "b": 2})

    assert response.status_code == 400
    assert "finite" in response.json()["error"]
    assert db_session.scalar(select(func.count()).select_from(Calculation)) == before
    assert user_client.get(f"/calculations/{saved_calculation['id']}").json() == saved_calculation


@pytest.mark.parametrize("method", ["get", "put", "delete"])
@pytest.mark.parametrize("identifier", ["0", "-1", "not-an-integer"])
def test_calculation_ids_must_be_positive_integers(user_client, method, identifier):
    options = {"json": {"type": "add", "a": 1, "b": 2}} if method == "put" else {}
    response = getattr(user_client, method)(f"/calculations/{identifier}", **options)
    assert response.status_code == 422


@pytest.mark.parametrize("method", ["post", "put", "delete"])
def test_failed_commit_rolls_back_calculation_write(
    user_client, db_session, saved_calculation, monkeypatch, caplog, method,
):
    before = db_session.scalar(select(func.count()).select_from(Calculation))
    path = "/calculations" if method == "post" else f"/calculations/{saved_calculation['id']}"

    def fail_commit():
        raise OperationalError("private SQL statement", {}, RuntimeError("private database credentials"))

    with monkeypatch.context() as patch:
        patch.setattr(db_session, "commit", fail_commit)
        options = {"json": {"type": "multiply", "a": 4, "b": 5}} if method != "delete" else {}
        response = getattr(user_client, method)(path, **options)

    assert response.status_code == 503
    assert response.json() == {"error": "Database unavailable."}
    assert "private SQL statement" not in response.text + caplog.text
    assert "private database credentials" not in response.text + caplog.text
    assert db_session.scalar(select(func.count()).select_from(Calculation)) == before
    assert user_client.get(f"/calculations/{saved_calculation['id']}").json() == saved_calculation


def test_openapi_documents_registration_login_and_bread(user_client):
    specification = user_client.get("/openapi.json").json()
    expected = {
        "/users/register": {"post"},
        "/users/login": {"post"},
        "/calculations": {"get", "post"},
        "/calculations/{calculation_id}": {"get", "put", "delete"},
    }
    for path, methods in expected.items():
        assert methods <= set(specification["paths"][path])
    assert "password_hash" not in specification["components"]["schemas"]["UserRead"]["properties"]
