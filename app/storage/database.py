"""Private Postgres schema on hosting; SQLite remains local development only."""

import os
import sqlite3
from contextlib import contextmanager

SCHEMA = "cci_private"


def remote():
    return bool(os.getenv("DATABASE_URL"))


class PostgresConnection:
    def __init__(self, connection):
        self.connection = connection

    def execute(self, statement, parameters=()):
        return self.connection.execute(
            statement.replace("?", "%s").replace(" REAL", " DOUBLE PRECISION"),
            parameters,
        )

    def executescript(self, script):
        for statement in script.split(";"):
            if statement.strip():
                self.execute(statement)


@contextmanager
def connect(local_path):
    if not remote():
        connection = sqlite3.connect(local_path)
        try:
            with connection:
                yield connection
        finally:
            connection.close()
        return
    import psycopg

    # Explicit TLS, no prepared statements: compatible with Supabase transaction pooler.
    with psycopg.connect(
        os.environ["DATABASE_URL"],
        sslmode="require",
        prepare_threshold=None,
        connect_timeout=10,
    ) as connection:
        connection.execute(f"SET LOCAL search_path TO {SCHEMA}")
        yield PostgresConnection(connection)


def initialize_schema():
    if not remote():
        return
    import psycopg

    with psycopg.connect(
        os.environ["DATABASE_URL"],
        sslmode="require",
        prepare_threshold=None,
        connect_timeout=10,
    ) as connection:
        connection.execute(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA}")
        connection.execute(
            f"REVOKE ALL ON SCHEMA {SCHEMA} FROM PUBLIC, anon, authenticated"
        )


def private_local_file(path):
    if not remote():
        path.chmod(0o600)


def duplicate_error(error):
    if isinstance(error, sqlite3.IntegrityError):
        return True
    import psycopg

    return isinstance(error, psycopg.errors.UniqueViolation)
