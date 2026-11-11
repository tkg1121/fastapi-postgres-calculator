"""Check a running image through its public API without exposing credentials."""

import json
import sys
import time
import urllib.error
import urllib.request
import uuid


def request(base_url, path, data=None):
    body = None if data is None else json.dumps(data).encode()
    message = urllib.request.Request(
        base_url + path, data=body, headers={"Content-Type": "application/json"}
    )
    try:
        response = urllib.request.urlopen(message, timeout=5)
    except urllib.error.HTTPError as error:
        response = error
    with response:
        return response.status, json.load(response)


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
    status, user = request(base_url, "/users", payload)
    assert status == 201, f"Registration returned {status}"
    assert set(user) == {"id", "username", "email", "created_at"}
    assert user["username"] == identity
    assert request(base_url, f"/users/{user['id']}") == (200, user)
    assert request(base_url, "/users", payload)[0] == 409
    assert request(base_url, "/users", {**payload, "email": "invalid"})[0] == 422
    assert request(base_url, "/add", {"a": 2, "b": 3}) == (200, {"result": 5.0})
    print("Image verification passed: database, registration, lookup, uniqueness, validation, calculator.")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000")
