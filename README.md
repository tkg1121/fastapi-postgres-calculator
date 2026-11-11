# FastAPI Calculator: Users and Deployment

This IS601 Module 10 assignment continues my Module 8 calculator and Module 9
PostgreSQL project. It adds a SQLAlchemy user model, validated request and response
schemas, Argon2id password hashing, PostgreSQL integration tests, and a Docker Hub
publishing workflow.

- [GitHub repository](https://github.com/tkg1121/fastapi-postgres-calculator)
- [Docker Hub image](https://hub.docker.com/r/tkg1121/fastapi-postgres-calculator)
- [GitHub Actions](https://github.com/tkg1121/fastapi-postgres-calculator/actions)
- [Module 9 SQL exercise and screenshots](docs/Module9-README.md)

## Module 10 submission

- [Submission PDF with repository links and screenshots](docs/Module10.pdf)
- [Reflection](docs/Module10%20Reflection.pdf)
- [Successful tests, scan, and Docker Hub deployment](https://github.com/tkg1121/fastapi-postgres-calculator/actions/runs/42955563012)
- [GitHub Actions screenshot](docs/module10/github-actions.jpg)
- [Docker Hub screenshot](docs/module10/dockerhub.jpg)

The verified source revision is `d6eef8339601790f4ab57d5e2d2cbba67b20c783`.
All 206 tests passed: 69 unit, 121 integration (including 27 real PostgreSQL
tests), and 16 browser tests. The image passed the strict HIGH/CRITICAL security
scan and was pushed, pulled, and exercised through the API. The screenshots show
this completed deployment; later documentation-only commits retain that evidence.

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

The container applies `alembic upgrade head` before starting Uvicorn. The user
table is `calculator.users`, separate from the earlier `public.users` and
`public.calculations` SQL exercises. The migration preserves those existing
assignment tables and records.

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
| `POST /users` | `201`, newly created public user fields | `409` duplicate username/email; `422` invalid input; `503` database unavailable |
| `GET /users/{user_id}` | `200`, public user fields | `404` missing user; `422` invalid ID; `503` database unavailable |
| `GET /health/db` | `200`, connection status and database name | `503` database unavailable |

Open `/docs`, expand `POST /users`, select **Try it out**, and submit:

```json
{
  "username": "example_user",
  "email": "example@example.com",
  "password": "Example password phrase 2026!"
}
```

Use the returned `id` with `GET /users/{user_id}`. Repeating the same registration
returns `409`. Validation and database errors use generic messages without
including submitted passwords, stored hashes, or connection credentials.

This assignment implements registration and lookup. It does not provide login,
access tokens, or authenticated access control. The existing `/add`, `/subtract`,
`/multiply`, and `/divide` endpoints and browser calculator remain available.

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

The tests cover arithmetic, request validation, password hashing and verification,
response-field filtering, real PostgreSQL persistence and constraints, error
handling, and browser calculations. Database tests use transactions and savepoints
to isolate changes. `REQUIRE_DATABASE_TESTS=1` makes a missing test connection fail
rather than silently skipping database tests. Browser tests start and stop their
own Uvicorn server on an available port.

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
   runs unit, integration, and Playwright tests.
2. Runs a separate Compose job with the earlier SQL regression exercises and
   application smoke checks.
3. After both jobs succeed, builds the application image once and loads it into
   Docker. Trivy scans its operating-system and library packages; HIGH or
   CRITICAL vulnerabilities fail the job. The scan report is retained as a
   workflow artifact.
4. Starts the scanned image against PostgreSQL and checks the calculator,
   registration, and user lookup.
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
app/models.py                 SQLAlchemy User model
app/schemas.py                UserCreate and UserRead
app/security.py               Argon2id hash and verify helpers
app/users.py                  Registration and lookup routes
app/database.py               Database configuration and sessions
migrations/                   Alembic schema migration
scripts/verify_deployment.py   Container/API smoke checks
tests/unit/                   Arithmetic, schema, and password tests
tests/integration/            API and real PostgreSQL tests
tests/e2e/                    Playwright calculator tests
.github/workflows/ci.yml       Tests, image scan, and Docker Hub publishing
```

## Source

The calculator builds on my [Module 8 project](https://github.com/tkg1121/fastapi-calculator),
which began with the instructor's
[Module 8 source](https://github.com/kaw393939/module8_is601/tree/1c2198fab4c0920797a01c9013358e920433e78b).
The original MIT license and Keith Williams copyright notice are retained.
The user model, validation, password handling, migrations, and deployment workflow
extend that project for Module 10.

Further reading: [FastAPI's password-hashing example](https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/)
and [Docker's test-before-push workflow](https://docs.docker.com/build/ci/github-actions/test-before-push/).
