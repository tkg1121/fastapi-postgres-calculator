# FastAPI Calculator: User and Calculation API

This IS601 Module 12 assignment continues my calculator from Modules 8-11. It
adds registration and login endpoints and a complete Browse, Read, Edit, Add,
Delete (BREAD) API for persisted calculations. SQLAlchemy stores the records in
PostgreSQL, Pydantic validates requests and responses, and the existing factory
computes results. Real database integration tests and GitHub Actions verify the
routes before a Docker image is published.

Login verifies a password and returns public user details. This module does not
issue tokens or restrict calculation routes; sessions and route authorization are
optional extensions. The earlier arithmetic endpoints and browser calculator
remain available and do not save calculation records.

- [GitHub repository](https://github.com/tkg1121/fastapi-postgres-calculator)
- [Docker Hub image](https://hub.docker.com/r/tkg1121/fastapi-postgres-calculator)
- [GitHub Actions](https://github.com/tkg1121/fastapi-postgres-calculator/actions)
- [Module 9 SQL exercise and screenshots](docs/Module9-README.md)

## Module 12 submission

- [Submission PDF with links, browser screenshots, deployment evidence, and reflection](docs/Module12.pdf)
- [Separate reflection PDF](docs/Module12%20Reflection.pdf)
- [Successful source workflow](https://github.com/tkg1121/fastapi-postgres-calculator/actions/runs/45599526638) for commit [`37b86bf`](https://github.com/tkg1121/fastapi-postgres-calculator/commit/37b86bf7d44e70c308da2ffc868c653d72be16b5)
- [OpenAPI application screenshot](docs/module12/openapi.png)
- [Registration](docs/module12/register.png) and [login](docs/module12/login.png) screenshots
- Calculation screenshots: [browse](docs/module12/calculation-browse.png), [read](docs/module12/calculation-read.png), [edit](docs/module12/calculation-edit.png), [add](docs/module12/calculation-create.png), and [delete](docs/module12/calculation-delete.png)
- [Successful GitHub Actions screenshot](docs/module12/github-actions.png) and [Docker Hub tag screenshot](docs/module12/dockerhub.png)

The source workflow passed its unit, PostgreSQL integration, browser, Compose,
image scan, push, and published-image pull checks. The browser screenshots show
actual `/docs` requests against the local Docker Compose application.

## Previous Module 11 submission

- [Submission PDF with repository links, screenshots, and reflection](docs/Module11.pdf)
- [Separate reflection PDF](docs/Module11%20Reflection.pdf)
- [Successful tests, scan, and Docker Hub deployment](https://github.com/tkg1121/fastapi-postgres-calculator/actions/runs/44196064737)
- [GitHub Actions screenshot](docs/module11/github-actions.png)
- [Docker Hub screenshot](docs/module11/dockerhub.png)

The verified application source revision is
`ef58262c55adfeca45d4e5bcbd614d15d9a110a8`. All 294 tests passed:
132 unit, 146 integration (including 52 real PostgreSQL tests), and 16 browser
tests. The Compose checks passed, the image passed the HIGH/CRITICAL security
scan, and the workflow pushed, pulled, and checked the published image. The
screenshots document that completed deployment; later documentation commits do
not change the application source.

## Run with Docker Compose

Install Docker Desktop and start its Linux engine, then clone the project:

```bash
git clone https://github.com/tkg1121/fastapi-postgres-calculator.git
cd fastapi-postgres-calculator
```

Create the local environment file. In PowerShell:

```powershell
Copy-Item .env.example .env
```

In Bash:

```bash
cp .env.example .env
```

Build and start the application, PostgreSQL, and pgAdmin:

```bash
docker compose up -d --build --wait
docker compose ps
```

| Service | Address |
| --- | --- |
| Calculator | [http://localhost:8000](http://localhost:8000) |
| Interactive API documentation | [http://localhost:8000/docs](http://localhost:8000/docs) |
| Database connection check | [http://localhost:8000/health/db](http://localhost:8000/health/db) |
| pgAdmin | [http://localhost:5050](http://localhost:5050) |
| PostgreSQL within Compose | `db:5432`, database `fastapi_db` |

If port 8000 is occupied or reserved by Windows, change `WEB_PORT=8000` to
`WEB_PORT=18000` in `.env`
and use `http://localhost:18000` for the calculator and API. Browser services are
bound to loopback; PostgreSQL has no published host port. pgAdmin uses local
desktop mode. Its preconfigured server connects as `postgres`, with the
`POSTGRES_PASSWORD` value from `.env`.

The example passwords are public development values. `.env` is ignored by Git
and excluded from the image. PostgreSQL initializes its password only when the
data volume is first created; editing `.env` does not change an existing database
account's password.

The container applies `alembic upgrade head` before starting Uvicorn. The
application tables are `calculator.users` and `calculator.calculations`, separate
from the earlier `public.users` and `public.calculations` SQL exercises. The
migrations preserve those existing assignment tables and records.

## Calculation model, schemas, and factory

The SQLAlchemy `Calculation` model maps to `calculator.calculations`:

| Field | Purpose |
| --- | --- |
| `id` | Database-generated integer primary key |
| `a`, `b` | Required finite floating-point operands |
| `type` | `add`, `subtract`, `multiply`, or `divide` |
| `result` | Required finite result computed by the factory |
| `created_at` | Timezone-aware timestamp generated by PostgreSQL |

`CalculationCreate` accepts only `a`, `b`, and `type`. Operands must be numbers;
numeric strings, booleans, `NaN`, and infinities are rejected. Operation names are
trimmed and converted to lowercase; `Sub` and `Subtract` both normalize to
`subtract`. Unsupported operations and a zero divisor are rejected before
calculation. Callers cannot supply an `id`, `result`, or
timestamp. `CalculationRead` serializes all six stored fields from an ORM object.

`CalculationFactory.create(type, a, b)` validates the input, selects an existing
arithmetic function, and constructs an unsaved `Calculation` with its result.
This reuses the arithmetic implementation instead of duplicating formulas in
the model. A finite-input calculation can still overflow, so the factory also
checks that its computed result is finite.

```python
from app.calculations import CalculationFactory

calculation = CalculationFactory.create("Add", 2, 3)
assert calculation.type == "add"
assert calculation.result == 5
```

For persistence, `create_calculation(session, CalculationCreate(...))` adds the
record and flushes the SQLAlchemy session. The caller owns the transaction and
chooses when to commit or roll back. PostgreSQL constraints independently enforce
required fields, supported operation names, finite values, and a nonzero divisor
for division, including writes that bypass Pydantic.

Migration `0002_create_calculations` adds this table after the existing user
migration. Module 12 exposes it through the calculation API without changing the
database schema or adding a user relationship.

## Calculation BREAD API

| Request | Successful result | Common errors |
| --- | --- | --- |
| `GET /calculations` | `200`, records ordered by ascending ID | `503` database unavailable |
| `GET /calculations/{id}` | `200`, one record | `404` missing; `422` invalid ID; `503` database unavailable |
| `POST /calculations` | `201`, new record and computed result | `422` invalid input; `400` non-finite result; `503` database unavailable |
| `PUT /calculations/{id}` | `200`, replaced inputs and recomputed result | `404` missing; `422` invalid input; `400` non-finite result; `503` database unavailable |
| `DELETE /calculations/{id}` | `204`, empty response | `404` missing; `422` invalid ID; `503` database unavailable |

`POST` and `PUT` accept a full `CalculationCreate` body with `a`, `b`, and `type`.
The response uses `CalculationRead`: `id`, `a`, `b`, `type`, `result`, and
`created_at`. Editing preserves the record ID and creation time. The service
recomputes the result from the supplied operands and operation rather than
trusting a caller-supplied result. Deleting removes the record. Request validation
returns a generic error without copying submitted values into logs or responses.

## User model and API

The SQLAlchemy `User` model contains `id`, unique `username`, unique `email`,
`password_hash`, and `created_at`. Database constraints enforce uniqueness even
when competing requests reach the database together.

`UserCreate` validates incoming data:

- Username: 3-50 ASCII letters, digits, or underscores.
- Email: a valid email address, at most 254 characters.
- Username and email are trimmed and converted to lowercase.
- Password: 12-128 characters, represented as Pydantic `SecretStr`. Password
  whitespace is preserved.
- Extra fields, including a caller-supplied hash, are rejected.

Passwords are hashed with salted Argon2id through `pwdlib`. The hash and verify
helpers are in `app/security.py`. The database stores the hash rather than the
original password. `UserRead` exposes only `id`, `username`, `email`, and
`created_at`; neither passwords nor hashes appear in user responses.

| Request | Successful result | Error responses |
| --- | --- | --- |
| `POST /users/register` | `201`, newly created public user fields | `409` duplicate username/email; `422` invalid input; `503` database unavailable |
| `POST /users/login` | `200`, public user fields after password verification | `401` invalid credentials; `422` invalid input; `503` database unavailable |
| `GET /users/{user_id}` | `200`, public user fields | `404` missing user; `422` invalid ID; `503` database unavailable |
| `GET /health/db` | `200`, connection status and database name | `503` database unavailable |

The earlier `POST /users` remains available as a registration alias.

Open `/docs`, expand `POST /users/register`, select **Try it out**, and submit:

```json
{
  "username": "example_user",
  "email": "example@example.com",
  "password": "Example password phrase 2026!"
}
```

Use the returned `id` with `GET /users/{user_id}`. Repeating the same registration
returns `409`. Then expand `POST /users/login` and submit either a username or
email with the same password:

```json
{
  "username": "example_user",
  "password": "Example password phrase 2026!"
}
```

Login returns the same public fields as registration. It requires exactly one
username or email; a wrong password or unknown identity returns the same `401`
message. Responses and application logs omit plaintext passwords, stored hashes,
and connection credentials. No session or token is created.

To check calculation BREAD manually in `/docs`, first run
`POST /calculations` with this body:

```json
{
  "a": 10,
  "b": 2,
  "type": "divide"
}
```

The `201` response has `result: 5` and a generated `id`. Use that ID with
`GET /calculations/{id}` and confirm the record also appears in
`GET /calculations`. Next, `PUT /calculations/{id}` with `a: 10`, `b: 4`, and
`type: "subtract"`; the result becomes `6` while the ID and creation time stay
the same. Finally, `DELETE /calculations/{id}` returns `204`, and a subsequent
read returns `404`. Try division with `b: 0` to see input validation return `422`.
The older `/add`, `/subtract`, `/multiply`, and `/divide` endpoints and browser
calculator remain available.

## Database configuration

The application and Alembic accept `DATABASE_URL`, for example:

```text
postgresql+psycopg://postgres:test-password@127.0.0.1:55432/fastapi_test
```

`DATABASE_URL` takes precedence. Without it, the application builds its connection
from `PGHOST`, `PGPORT`, `PGDATABASE`, `PGUSER`, and `PGPASSWORD`. Compose supplies
these variables from its configuration. For native Python commands, set the
environment variables in the shell; Compose's `.env` is not automatically loaded
by Python.

## Run the tests locally

Use Python 3.12. Create a virtual environment:

```bash
python -m venv .venv
```

Activate it in PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

Or in Bash:

```bash
source .venv/bin/activate
```

Install the application, test dependencies, and Chromium:

```bash
python -m pip install -r requirements.txt
python -m playwright install chromium
```

On Linux, use `python -m playwright install --with-deps chromium` for browser
system dependencies.

Unit tests do not require a database. Run all unit tests, or just the calculation
schema and factory tests:

```bash
python -m pytest tests/unit -v
python -m pytest tests/unit/test_calculations.py -v
```

Start a separate, disposable PostgreSQL container for tests. This command works
in PowerShell and Bash:

```bash
docker run --rm -d --name calculator-test-db -p 127.0.0.1:55432:5432 -e POSTGRES_USER=postgres -e POSTGRES_PASSWORD=test-password -e POSTGRES_DB=fastapi_test postgres:17-bookworm
```

Wait until this command reports that PostgreSQL is accepting connections:

```bash
docker exec calculator-test-db pg_isready -U postgres -d fastapi_test
```

Set the test connection in PowerShell:

```powershell
$env:DATABASE_URL = 'postgresql+psycopg://postgres:test-password@127.0.0.1:55432/fastapi_test'
$env:PGHOST = '127.0.0.1'
$env:PGPORT = '55432'
$env:PGDATABASE = 'fastapi_test'
$env:PGUSER = 'postgres'
$env:PGPASSWORD = 'test-password'
$env:REQUIRE_DATABASE_TESTS = '1'
```

Or in Bash:

```bash
export DATABASE_URL='postgresql+psycopg://postgres:test-password@127.0.0.1:55432/fastapi_test'
export PGHOST=127.0.0.1 PGPORT=55432 PGDATABASE=fastapi_test PGUSER=postgres PGPASSWORD=test-password
export REQUIRE_DATABASE_TESTS=1
```

Apply migrations and run all test layers:

```bash
python -m alembic upgrade head
python -m alembic check
python -m pytest -v
```

The suite covers arithmetic, schemas, password hashing, user registration and
login, calculation BREAD routes, database constraints, and browser calculations.
The route integration tests exercise real PostgreSQL, including creation,
retrieval, editing, deletion, invalid inputs, duplicate identities, and rollback.

Database tests use actual PostgreSQL connections and transactions with savepoints
to isolate changes. `REQUIRE_DATABASE_TESTS=1` makes a missing test connection fail
rather than silently skipping database tests. Browser tests start and stop their
own Uvicorn server on an available port.

After applying migrations and setting the connection variables above, run the
new Module 12 route integration tests with:

```bash
python -m pytest tests/integration/test_module12_routes.py -v
```

The earlier Module 11 schema, factory, and PostgreSQL tests can be run with:

```bash
python -m pytest tests/unit/test_calculations.py tests/integration/test_calculation_database.py -v
```

To run one layer, use `python -m pytest tests/unit -v`,
`python -m pytest tests/integration -v`, or
`python -m pytest tests/e2e -v --browser chromium`.

When finished, remove the disposable test container:

```bash
docker stop calculator-test-db
```

Its `--rm` option removes the test container on shutdown. The application's
Compose volumes are separate and remain intact.

## CI and Docker Hub publishing

`.github/workflows/ci.yml` runs on pushes and pull requests and can also be
started manually. The workflow:

1. Starts an isolated PostgreSQL service, applies and checks migrations, then
   runs all user and calculation unit and integration tests, plus the existing
   Playwright tests.
2. Runs a separate Compose job with the earlier SQL regression exercises and
   application smoke checks.
3. After both jobs succeed, builds the application image once and loads it into
   Docker. Trivy scans its operating-system and library packages; HIGH or
   CRITICAL vulnerabilities fail the job. The scan report is retained as a
   workflow artifact.
4. Starts the scanned image against PostgreSQL and checks registration, login,
   calculation BREAD, and the earlier calculator routes.
5. For `main` branch runs outside pull requests, signs in to Docker Hub and
   publishes that same image as `latest` and `sha-<commit>`.
6. Removes the local image tags, pulls the published image, and runs it by its
   registry digest for another API smoke check.

Publishing uses the repository secrets `DOCKERHUB_USERNAME` and `DOCKERHUB_TOKEN`.
Credentials are provided only to the registry login step after the checks pass.
The workflow pins its actions to commit SHAs and keeps repository permissions
read-only.

To run the published image instead of building locally, first create `.env` as
shown above, then run:

```bash
docker compose pull web
docker compose up -d --no-build --wait
```

Image: `tkg1121/fastapi-postgres-calculator:latest`.
Commit-specific tags identify the source version; the workflow summary records
the verified registry digest.

## Stop and restart

```bash
docker compose logs
docker compose down
docker compose up -d --wait
```

Normal `docker compose down` preserves the named PostgreSQL and pgAdmin volumes.
Do not add `--volumes` if you want to keep those records and settings.

## Project layout

```text
app/models.py                 SQLAlchemy User and Calculation models
app/schemas.py                User login and creation/response schemas; calculation schemas
app/calculations.py           Calculation factory and persistence helper
app/calculation_routes.py     Calculation BREAD API routes
app/security.py               Argon2id hash and verify helpers
app/users.py                  Registration, login, and lookup routes
app/database.py               Database configuration and sessions
migrations/                   Alembic user and calculation migrations
scripts/verify_deployment.py   Container/API smoke checks
tests/unit/                   Arithmetic, schema, factory, and password tests
tests/integration/            User and calculation API and real PostgreSQL tests
tests/e2e/                    Playwright calculator tests
.github/workflows/ci.yml       Tests, image scan, and Docker Hub publishing
```

## Source

The calculator builds on my [Module 8 project](https://github.com/tkg1121/fastapi-calculator),
which began with the instructor's
[Module 8 source](https://github.com/kaw393939/module8_is601/tree/1c2198fab4c0920797a01c9013358e920433e78b).
The original MIT license and Keith Williams copyright notice are retained.
The user model, password handling, and deployment workflow extended that project
for Module 10. The calculation model, schemas, factory, migration, and associated
tests extended it for Module 11. Registration, login, and calculation BREAD routes
extend the same project for Module 12.

Further reading: [FastAPI's password-hashing example](https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/)
and [Docker's test-before-push workflow](https://docs.docker.com/build/ci/github-actions/test-before-push/).

## Previous Module 10 submission

- [Submission PDF with repository links and screenshots](docs/Module10.pdf)
- [Reflection](docs/Module10%20Reflection.pdf)
- [Successful Module 10 tests, scan, and Docker Hub deployment](https://github.com/tkg1121/fastapi-postgres-calculator/actions/runs/42955563012)
- [GitHub Actions screenshot](docs/module10/github-actions.jpg)
- [Docker Hub screenshot](docs/module10/dockerhub.jpg)

These archived screenshots document source revision
`d6eef8339601790f4ab57d5e2d2cbba67b20c783`, which passed 206 tests and the
HIGH/CRITICAL image scan before publishing and checking the pulled image. They
record the earlier Module 10 submission, not the Module 12 test run.
