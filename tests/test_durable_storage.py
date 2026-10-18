"""Storage contracts: owner scope, private bucket, restart safety and fail-closed startup."""

import secrets
import sqlite3
from contextlib import contextmanager

import httpx
import pytest

from app.documents import uploads
from app.security import auth
from app.security.policy import Principal
from app.storage import database, objects
from app.storage import uploads as durable
from app.storage.errors import StorageUnavailable
from scripts import serve


def test_postgres_queries_use_bound_parameters_and_precise_timestamps():
    calls = []

    class Connection:
        def execute(self, statement, parameters):
            calls.append((statement, parameters))

    wrapper = database.PostgresConnection(Connection())
    wrapper.execute("SELECT username FROM users WHERE username=?", ("O'Reilly",))
    wrapper.execute("CREATE TABLE t (expires REAL)")
    assert calls[0] == ("SELECT username FROM users WHERE username=%s", ("O'Reilly",))
    assert "DOUBLE PRECISION" in calls[1][0]


def test_database_pooler_uses_tls_transaction_scope_and_no_prepared_statements(
    monkeypatch,
):
    import psycopg

    calls = []

    class Connection:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def execute(self, *args):
            calls.append(args)

    def fake_connect(dsn, **kwargs):
        assert dsn == "private-connection"
        assert kwargs["sslmode"] == "require" and kwargs["prepare_threshold"] is None
        return Connection()

    monkeypatch.setenv("DATABASE_URL", "private-connection")
    monkeypatch.setattr(psycopg, "connect", fake_connect)
    with database.connect(None) as db:
        db.execute("SELECT ?", (123,))
    assert calls == [("SET LOCAL search_path TO cci_private",), ("SELECT %s", (123,))]


def test_public_bucket_is_rejected(monkeypatch):
    monkeypatch.setattr(
        objects, "request", lambda *a, **k: httpx.Response(200, json={"public": True})
    )
    with pytest.raises(StorageUnavailable, match="must be private"):
        objects.verify_private_bucket()


def test_storage_errors_do_not_expose_service_key(monkeypatch):
    secret = secrets.token_urlsafe(24)
    monkeypatch.setenv("SUPABASE_URL", "https://test-project.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", secret)

    def fail(*args, **kwargs):
        assert kwargs["headers"]["apikey"] == secret
        raise httpx.ConnectError(secret)

    monkeypatch.setattr(httpx, "request", fail)
    with pytest.raises(StorageUnavailable) as error:
        objects.download("private.pdf")
    assert secret not in str(error.value)


def test_accounts_and_private_documents_survive_runtime_directory_replacement(
    tmp_path, monkeypatch
):
    # Disk-backed stand-in exercises the remote repository contract without live credentials.
    backing = tmp_path / "durable.sqlite"

    @contextmanager
    def persistent_connect(_):
        with sqlite3.connect(backing) as connection:

            class Adapter:
                def execute(self, sql, params=()):
                    if "pg_advisory_xact_lock" in sql:
                        return None
                    return connection.execute(sql, params)

                def executescript(self, sql):
                    return connection.executescript(sql)

            yield Adapter()

    monkeypatch.setattr(auth, "connect", persistent_connect)
    monkeypatch.setattr(auth, "initialize_schema", lambda: None)
    monkeypatch.setattr(auth, "private_local_file", lambda p: None)
    monkeypatch.setattr(durable, "connect", persistent_connect)
    monkeypatch.setattr(uploads, "remote", lambda: True)
    blobs = {}
    monkeypatch.setattr(objects, "verify_private_bucket", lambda: None)
    monkeypatch.setattr(objects, "upload", lambda p, c: blobs.__setitem__(p, c))
    monkeypatch.setattr(objects, "download", lambda p: blobs[p])
    monkeypatch.setattr(objects, "delete", lambda p: blobs.pop(p, None))
    monkeypatch.setenv("CCI_RUNTIME_DIR", str(tmp_path / "first-container"))
    password = secrets.token_urlsafe(24)
    auth.create_user("alice", password, "customer_service", ["CASE-1001"])
    user = auth.authenticate("alice", password)
    durable.initialize()
    record = {
        "id": "UPLOAD-fixture",
        "owner": "alice",
        "case_id": "CASE-1001",
        "pages": ["refund evidence"],
    }
    durable.save(user, "CASE-1001", record, b"%PDF-fixture")
    monkeypatch.setenv("CCI_RUNTIME_DIR", str(tmp_path / "replacement-container"))
    assert auth.authenticate("alice", password).username == "alice"
    assert uploads.records(user, "CASE-1001") == [record]
    assert durable.read_pdf(user, "CASE-1001", record["id"]) == b"%PDF-fixture"
    other = Principal("bob", "head", ("CASE-1001",))
    assert durable.records(other, "CASE-1001") == []
    assert durable.records(user, "CASE-1002") == []
    with pytest.raises(ValueError):
        durable.read_pdf(other, "CASE-1001", record["id"])
    durable.remove(user, "CASE-1001", record["id"])
    assert not blobs and not durable.records(user, "CASE-1001")


def test_hosted_startup_refuses_temporary_storage(monkeypatch):
    monkeypatch.setenv("REQUIRE_DURABLE_STORAGE", "true")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    old_mask = serve.os.umask(0o077)
    try:
        with pytest.raises(SystemExit, match="private database"):
            serve.main()
    finally:
        serve.os.umask(old_mask)
