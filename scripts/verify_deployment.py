"""Check a running image through its public API without exposing credentials."""

import json
import sys
import time
import urllib.error
import urllib.request
import uuid


def request(base_url, path, data=None, method=None):
    body = None if data is None else json.dumps(data).encode()
    message = urllib.request.Request(
        base_url + path, data=body, method=method,
        headers={"Content-Type": "application/json"},
    )
    try:
        response = urllib.request.urlopen(message, timeout=5)
    except urllib.error.HTTPError as error:
        response = error
    with response:
        content = response.read()
        return response.status, json.loads(content) if content else None


def main(base_url):
    deadline = time.monotonic() + 90
    while True:
        try:
            status, body = request(base_url, "/health/db")
            if status == 200 and body["status"] == "ok":
                break
        except (urllib.error.URLError, TimeoutError):
            pass
        if time.monotonic() >= deadline:
            raise RuntimeError("The deployed image did not become healthy.")
        time.sleep(1)

    identity = "smoke_" + uuid.uuid4().hex[:12]
    payload = {
        "username": identity,
        "email": identity + "@example.com",
        "password": "Container verification password!",
    }
    status, user = request(base_url, "/users/register", payload)
    assert status == 201, f"Registration returned {status}"
    assert set(user) == {"id", "username", "email", "created_at"}
    assert user["username"] == identity
    assert request(base_url, f"/users/{user['id']}") == (200, user)
    for field in ("username", "email"):
        assert request(base_url, "/users/login", {
            field: payload[field], "password": payload["password"],
        }) == (200, user)
    assert request(base_url, "/users/login", {
        "username": identity, "password": "Incorrect verification password!",
    }) == (401, {"error": "Invalid credentials."})
    assert request(base_url, "/users", payload)[0] == 409
    assert request(base_url, "/users/register", {**payload, "email": "invalid"})[0] == 422
    assert request(base_url, "/add", {"a": 2, "b": 3}) == (200, {"result": 5.0})

    calculations = []
    for operation, a, b, expected in [
        ("add", 2, 3, 5), ("subtract", 8, 2, 6),
        ("multiply", 4, 5, 20), ("divide", 9, 2, 4.5),
    ]:
        status, calculation = request(base_url, "/calculations", {"type": operation, "a": a, "b": b})
        assert status == 201, f"Calculation creation returned {status}"
        assert set(calculation) == {"id", "a", "b", "type", "result", "created_at"}
        assert calculation["result"] == expected
        assert request(base_url, f"/calculations/{calculation['id']}") == (200, calculation)
        calculations.append(calculation)

    status, history = request(base_url, "/calculations")
    assert status == 200
    assert all(calculation in history for calculation in calculations)
    assert [row["id"] for row in history] == sorted(row["id"] for row in history)
    first = calculations[0]
    status, updated = request(
        base_url, f"/calculations/{first['id']}", {"type": "Sub", "a": 9, "b": 4}, method="PUT",
    )
    assert status == 200
    assert updated == {**first, "type": "subtract", "a": 9.0, "b": 4.0, "result": 5.0}
    assert request(base_url, "/calculations", {"type": "power", "a": 2, "b": 3})[0] == 422
    assert request(base_url, "/calculations", {"type": "divide", "a": 2, "b": 0})[0] == 422
    assert request(base_url, "/calculations", {"type": "multiply", "a": 1e308, "b": 2})[0] == 400
    for calculation in calculations:
        path = f"/calculations/{calculation['id']}"
        assert request(base_url, path, method="DELETE") == (204, None)
        assert request(base_url, path)[0] == 404
    print("Image verification passed: database, registration, login, uniqueness, validation, and calculation BREAD.")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000")
