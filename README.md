# FastAPI Calculator with PostgreSQL

This IS601 database assignment runs a FastAPI calculator, PostgreSQL, and pgAdmin
with Docker Compose. The SQL exercises create related tables, insert sample
records, query them, and update and delete individual calculations.

## Submission

- [Repository](https://github.com/tkg1121/fastapi-postgres-calculator)
- [Successful tests and Compose verification](https://github.com/tkg1121/fastapi-postgres-calculator/actions/runs/41763079480)
- [CI verification screenshot](docs/database/CI%20verification.jpg)
- [Database assignment PDF with screenshots](docs/Database%20Assignment%20Submission.pdf)
- [Reflection](docs/Reflection.pdf)

The submission includes a separate pgAdmin screenshot for each of the nine
required SQL commands, the final two calculation records, and successful
Compose service output from GitHub Actions. The SQL screenshots were captured
from the local pgAdmin instance at `localhost:5050`.

## Start the environment

Install Docker Desktop and start its Linux container engine. Clone this repository:

```bash
git clone https://github.com/tkg1121/fastapi-postgres-calculator.git
cd fastapi-postgres-calculator
```

Create the local environment file in PowerShell:

```powershell
Copy-Item .env.example .env
```

Or in Bash:

```bash
cp .env.example .env
```

The example passwords are public local-demo values, not real account secrets.
The `.env` file is ignored by Git. Set different values before using this setup
in another environment. PostgreSQL reads its initialization password when the
database volume is first created; changing `.env` afterward does not change an
existing database user's password.

Build and start the services:

```bash
docker compose up -d --build --wait
docker compose ps
```

| Service | Address | Purpose |
| --- | --- | --- |
| FastAPI | [http://localhost:8000](http://localhost:8000) | Browser calculator |
| Database check | [http://localhost:8000/health/db](http://localhost:8000/health/db) | Actual PostgreSQL connection and database name |
| pgAdmin | [http://localhost:5050](http://localhost:5050) | Query Tool for the SQL exercises |
| PostgreSQL | `db:5432` inside Compose | Database server; no host port published |

FastAPI and pgAdmin listen only on the local machine's loopback interface.
pgAdmin uses desktop mode, so it opens without a separate pgAdmin login. The
`PGADMIN_DEFAULT_PASSWORD` value is still provided for container initialization;
it is not the PostgreSQL connection password.

The `/health/db` endpoint returns `{"status":"ok","database":"fastapi_db"}`
when the database responds, or HTTP 503 with a generic error when it is
unavailable. It checks connectivity only. The four calculator endpoints retain
their existing behavior; they do not save calculations or provide a database
CRUD API. Database records in this assignment are managed with SQL.

## Run the SQL in pgAdmin

1. Open pgAdmin and expand **Servers > FastAPI PostgreSQL**. This server is
   registered by `pgadmin/servers.json`.
2. Connect using host `db`, port `5432`, database `fastapi_db`, and user
   `postgres`. When prompted for a password, enter `POSTGRES_PASSWORD` from
   `.env`.
3. Expand **Databases**, select **fastapi_db**, and open **Query Tool**.
4. On a fresh database, copy each numbered script below into the editor and
   execute it separately, in order. Capture the query and its **Messages** or
   **Data Output** after each execution.

| Script | Action | Expected result |
| --- | --- | --- |
| `sql/01_create_users.sql` | Create users table | Table created |
| `sql/02_create_calculations.sql` | Create calculations table | Table created |
| `sql/03_insert_users.sql` | Insert Alice and Bob | 2 rows inserted |
| `sql/04_insert_calculations.sql` | Insert three calculations | 3 rows inserted |
| `sql/05_select_users.sql` | Retrieve users | Alice id 1 and Bob id 2 |
| `sql/06_select_calculations.sql` | Retrieve calculations | 3 rows |
| `sql/07_join.sql` | Join calculations to users | Alice owns add/divide; Bob owns multiply |
| `sql/08_update.sql` | Set calculation 1 result to 6 | 1 row updated |
| `sql/09_delete.sql` | Delete calculation 2 | 1 row deleted |

These scripts intentionally follow the assignment's SQL. They are not repeatable
migrations: rerunning CREATE or INSERT statements against the same populated
database will cause duplicate-table or uniqueness errors. The inserts assume a
fresh database where Alice and Bob receive ids 1 and 2. No tables or records are
created automatically when the containers start.

The update changes the stored result for `2 + 3` to `6` to demonstrate SQL UPDATE.
It does not recalculate the arithmetic or assert that 6 is the correct sum.

## Relationships and verification

One user can own many calculations. Each calculation has one required `user_id`
referencing `users.id`. The foreign key rejects nonexistent users, and
`ON DELETE CASCADE` removes a user's calculations when that user is deleted.
Unique constraints prevent duplicate usernames and email addresses.

After scripts 01-09, run `sql/10_final_state.sql`. It should show two calculations:
Alice's add row (id 1, result 6) and Bob's multiply row (id 3, result 20).

The optional `sql/11_verify_relationships.sql` checks that final state, rejects
unknown users and duplicate usernames/emails, and checks cascade deletion. It
rolls back its row changes so the assignment records remain intact. PostgreSQL
sequence counters can still advance during failed inserts even after rollback;
gaps in later ids are expected.

## Tests and continuous integration

The existing unit, API integration, and Playwright tests remain in the project.
The database endpoint also has mocked tests for a successful connection,
connection failure, query failure, resource cleanup, and generic error messages.

For local tests, create and activate a Python 3.12 virtual environment, then run:

```bash
python -m pip install -r requirements.txt
python -m playwright install chromium
python -m pytest -v
```

On Linux, use `python -m playwright install --with-deps chromium` to install the
browser's system dependencies too. Browser tests start their own local FastAPI
server and do not require a manually started server.

GitHub Actions runs all three test layers on pushes and pull requests. A separate
Compose job builds the stack, waits for healthy services, executes SQL scripts
01-11 against a fresh database, and checks `/health/db`. SQL errors fail the job.

The linked verification run passed all 130 application tests and the complete
Compose/SQL job for commit `275cf0d`.

The same stack was also built and run locally. All three services reported
healthy, `/health/db` returned `fastapi_db`, and the relationship checks passed
after the SQL commands were executed in pgAdmin.

## Stop and restart

```bash
docker compose logs
docker compose down
docker compose up -d --wait
```

The `postgres_data` and `pgadmin_data` named volumes preserve database records
and pgAdmin settings across normal shutdowns. `docker compose down` does not
delete these volumes. Avoid adding `--volumes` when you want to keep your work.

## Source

This project builds on my [Module 8 calculator](https://github.com/tkg1121/fastapi-calculator),
which started from the instructor's
[Module 8 source](https://github.com/kaw393939/module8_is601/tree/1c2198fab4c0920797a01c9013358e920433e78b).
The original MIT license and Keith Williams copyright notice are included.
