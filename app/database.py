"""Small PostgreSQL connectivity check using standard libpq environment variables."""

import psycopg


def get_database_name() -> str:
    """Connect using PGHOST, PGPORT, PGDATABASE, PGUSER, and PGPASSWORD."""
    with psycopg.connect(connect_timeout=3) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT current_database()")
            return cursor.fetchone()[0]
