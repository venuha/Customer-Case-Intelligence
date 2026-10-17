"""Opaque, server-revocable sessions; scrypt password hashes; no default passwords."""

import hashlib, hmac, json, os, secrets, sqlite3, time
from fastapi import HTTPException, Request
from .policy import Principal, ROLES
from ..config import runtime_dir

SESSION_COOKIE = "cci_session"
SESSION_TTL = 8 * 60 * 60


def database():
    return runtime_dir() / "identity.sqlite"


def initialize():
    with sqlite3.connect(database()) as db:
        db.executescript("""CREATE TABLE IF NOT EXISTS users(username TEXT PRIMARY KEY,role TEXT NOT NULL,case_ids TEXT NOT NULL,salt TEXT NOT NULL,password_hash TEXT NOT NULL,active INTEGER NOT NULL DEFAULT 1);
  CREATE TABLE IF NOT EXISTS sessions(token_hash TEXT PRIMARY KEY,username TEXT NOT NULL,expires REAL NOT NULL);
  CREATE INDEX IF NOT EXISTS sessions_user ON sessions(username);""")
    os.chmod(database(), 0o600)


def password_hash(password, salt):
    return hashlib.scrypt(
        password.encode(),
        salt=bytes.fromhex(salt),
        n=16384,
        r=8,
        p=1,
        dklen=32,
        maxmem=64 * 1024 * 1024,
    ).hex()


def create_user(username, password, role, case_ids):
    if role not in ROLES:
        raise ValueError("Unknown role")
    if (
        not username
        or len(username) > 80
        or not username.replace("_", "").replace("-", "").replace(".", "").isalnum()
    ):
        raise ValueError("Use a simple username")
    if len(password) < 12:
        raise ValueError("Password must have at least 12 characters")
    initialize()
    salt = secrets.token_hex(16)
    with sqlite3.connect(database()) as db:
        db.execute(
            "INSERT INTO users(username,role,case_ids,salt,password_hash) VALUES(?,?,?,?,?)",
            (
                username,
                role,
                json.dumps(sorted(set(case_ids))),
                salt,
                password_hash(password, salt),
            ),
        )


def authenticate(username, password):
    with sqlite3.connect(database()) as db:
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
    with sqlite3.connect(database()) as db:
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
    with sqlite3.connect(database()) as db:
        row = db.execute(
            "SELECT u.username,u.role,u.case_ids FROM sessions s JOIN users u ON s.username=u.username WHERE s.token_hash=? AND s.expires>? AND u.active=1",
            (hashlib.sha256(token.encode()).hexdigest(), time.time()),
        ).fetchone()
    if not row:
        raise HTTPException(401, "Your session has expired. Sign in again.")
    return Principal(row[0], row[1], tuple(json.loads(row[2])))


def revoke(token):
    with sqlite3.connect(database()) as db:
        db.execute(
            "DELETE FROM sessions WHERE token_hash=?",
            (hashlib.sha256(token.encode()).hexdigest(),),
        )
