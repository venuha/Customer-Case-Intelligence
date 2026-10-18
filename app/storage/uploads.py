"""Durable owner/case metadata in private Postgres; PDFs in a private bucket."""

import hashlib
import json

from . import objects
from .database import connect


def initialize():
    with connect(None) as db:
        db.execute("""CREATE TABLE IF NOT EXISTS uploads (
            id TEXT PRIMARY KEY, owner TEXT NOT NULL, case_id TEXT NOT NULL,
            object_path TEXT NOT NULL UNIQUE, payload TEXT NOT NULL)""")
        db.execute(
            "CREATE INDEX IF NOT EXISTS uploads_owner_case ON uploads(owner,case_id)"
        )
    objects.verify_private_bucket()


def records(user, cid):
    with connect(None) as db:
        rows = db.execute(
            "SELECT payload FROM uploads WHERE owner=? AND case_id=? ORDER BY id",
            (user.username, cid),
        ).fetchall()
    return [json.loads(row[0]) for row in rows]


def save(user, cid, record, content):
    path = (
        hashlib.sha256(user.username.encode()).hexdigest()
        + "/"
        + cid
        + "/"
        + record["id"]
        + ".pdf"
    )
    uploaded = False
    try:
        with connect(None) as db:
            # Bounded free-tier usage; serialize all uploads across processes.
            db.execute("SELECT pg_advisory_xact_lock(73314521)")
            if db.execute("SELECT COUNT(*) FROM uploads").fetchone()[0] >= 50:
                raise ValueError(
                    "The demo document capacity is full. Remove a document first."
                )
            if (
                db.execute(
                    "SELECT COUNT(*) FROM uploads WHERE owner=? AND case_id=?",
                    (user.username, cid),
                ).fetchone()[0]
                >= 10
            ):
                raise ValueError("This case already has ten private uploads.")
            objects.upload(path, content)
            uploaded = True
            db.execute(
                "INSERT INTO uploads VALUES (?,?,?,?,?)",
                (record["id"], user.username, cid, path, json.dumps(record)),
            )
    except Exception:
        if uploaded:
            try:
                objects.delete(path)
            except Exception:
                pass  # A provider outage may leave an orphan; no public access is granted.
        raise


def object_path(user, cid, did):
    with connect(None) as db:
        row = db.execute(
            "SELECT object_path FROM uploads WHERE owner=? AND case_id=? AND id=?",
            (user.username, cid, did),
        ).fetchone()
    if not row:
        raise ValueError("Document not found.")
    return row[0]


def read_pdf(user, cid, did):
    return objects.download(object_path(user, cid, did))


def remove(user, cid, did):
    path = object_path(user, cid, did)
    objects.delete(path)
    with connect(None) as db:
        db.execute(
            "DELETE FROM uploads WHERE owner=? AND case_id=? AND id=?",
            (user.username, cid, did),
        )
