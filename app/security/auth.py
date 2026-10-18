"""Opaque, server-revocable sessions; scrypt password hashes; no default passwords."""

import hashlib
import hmac
import json
import secrets
import time
from threading import BoundedSemaphore

from fastapi import HTTPException, Request

from app.storage.database import (
    connect,
    duplicate_error,
    initialize_schema,
    private_local_file,
)

from ..config import runtime_dir
from .policy import ROLES, Principal

SESSION_COOKIE = "cci_session"
SESSION_TTL = 8 * 60 * 60
_HASH_SLOT = BoundedSemaphore(1)


def database():
    return runtime_dir() / "identity.sqlite"


def initialize():
    initialize_schema()
    with connect(database()) as db:
        db.executescript("""CREATE TABLE IF NOT EXISTS users(username TEXT PRIMARY KEY,role TEXT NOT NULL,case_ids TEXT NOT NULL,salt TEXT NOT NULL,password_hash TEXT NOT NULL,active INTEGER NOT NULL DEFAULT 1);
  CREATE TABLE IF NOT EXISTS sessions(token_hash TEXT PRIMARY KEY,username TEXT NOT NULL,expires REAL NOT NULL);
  CREATE INDEX IF NOT EXISTS sessions_user ON sessions(username);""")
    private_local_file(database())


def password_hash(password, salt):
    with _HASH_SLOT:
        return hashlib.scrypt(
            password.encode(),
            salt=bytes.fromhex(salt),
            n=16384,
            r=8,
            p=1,
            dklen=32,
            maxmem=64 * 1024 * 1024,
        ).hex()


def create_user(username, password, role, case_ids, *, active=True):
    if role not in ROLES:
        raise ValueError("Unknown role")
    if (
        not username
        or len(username) > 80
        or not username.replace("_", "").replace("-", "").replace(".", "").isalnum()
    ):
        raise ValueError("Use a simple username")
    if len(password) < 12 or len(password) > 512:
        raise ValueError("Password must have at least 12 characters")
    initialize()
    salt = secrets.token_hex(16)
    with connect(database()) as db:
        db.execute(
            "INSERT INTO users(username,role,case_ids,salt,password_hash,active) VALUES(?,?,?,?,?,?)",
            (
                username,
                role,
                json.dumps(sorted(set(case_ids))),
                salt,
                password_hash(password, salt),
                int(active),
            ),
        )


def authenticate(username, password):
    with connect(database()) as db:
        row = db.execute(
            "SELECT role,case_ids,salt,password_hash,active FROM users WHERE username=?",
            (username,),
        ).fetchone()
    salt = row[2] if row else "0" * 32
    candidate = password_hash(password, salt)
    if not row or not row[4] or not hmac.compare_digest(candidate, row[3]):
        return None
    return Principal(username, row[0], tuple(json.loads(row[1])))


def new_session(principal):
    token = secrets.token_urlsafe(32)
    with connect(database()) as db:
        db.execute("DELETE FROM sessions WHERE expires<?", (time.time(),))
        db.execute(
            "INSERT INTO sessions VALUES(?,?,?)",
            (
                hashlib.sha256(token.encode()).hexdigest(),
                principal.username,
                time.time() + SESSION_TTL,
            ),
        )
    return token


def require_user(request: Request):
    token = request.cookies.get(SESSION_COOKIE, "")
    if not token:
        raise HTTPException(401, "Sign in to access customer cases.")
    with connect(database()) as db:
        row = db.execute(
            "SELECT u.username,u.role,u.case_ids FROM sessions s JOIN users u ON s.username=u.username WHERE s.token_hash=? AND s.expires>? AND u.active=1",
            (hashlib.sha256(token.encode()).hexdigest(), time.time()),
        ).fetchone()
    if not row:
        raise HTTPException(401, "Your session has expired. Sign in again.")
    return Principal(row[0], row[1], tuple(json.loads(row[2])))


def revoke(token):
    with connect(database()) as db:
        db.execute(
            "DELETE FROM sessions WHERE token_hash=?",
            (hashlib.sha256(token.encode()).hexdigest(),),
        )


def request_account(username, password):
    """Public registration never grants case access or creates a session."""
    try:
        create_user(username, password, "customer_service", [], active=False)
    except Exception as error:
        if not duplicate_error(error):
            raise
        # Same response for existing accounts; never replace their password.


def approve_user(username, role, case_ids):
    if role not in ROLES or not case_ids:
        raise ValueError("Select a valid role and at least one case.")
    initialize()
    with connect(database()) as db:
        result = db.execute(
            "UPDATE users SET role=?,case_ids=?,active=1 WHERE username=? AND active=0",
            (role, json.dumps(sorted(set(case_ids))), username),
        )
        if result.rowcount != 1:
            raise ValueError("Pending account not found.")


def pending_users():
    initialize()
    with connect(database()) as db:
        return [
            r[0]
            for r in db.execute(
                "SELECT username FROM users WHERE active=0 ORDER BY username"
            )
        ]
