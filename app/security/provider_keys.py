"""Process-local, session-bound provider credentials. Never serialize these values."""

import hashlib
import threading
import time
from contextvars import ContextVar

from app.storage.database import connect

from .auth import SESSION_TTL, database

_current = ContextVar("provider_key", default=None)
_keys = {}
_guard = threading.Lock()


def _id(token):
    return hashlib.sha256(token.encode()).hexdigest()


def set_key(token, key):
    if not token or not key or len(key) > 512 or any(c.isspace() for c in key):
        raise ValueError("Enter a valid API key without whitespace.")
    with connect(database()) as db:
        session = db.execute(
            "SELECT expires FROM sessions WHERE token_hash=?", (_id(token),)
        ).fetchone()
    if not session or session[0] <= time.time():
        raise ValueError("Sign in again before connecting a key.")
    with _guard:
        now = time.time()
        for k in list(_keys):
            if _keys[k][1] <= now:
                _keys.pop(k, None)
        if len(_keys) >= 1000 and _id(token) not in _keys:
            raise ValueError("Session key capacity reached. Try again later.")
        _keys[_id(token)] = (key, min(session[0], now + SESSION_TTL))


def personal_key(token):
    with _guard:
        value = _keys.get(_id(token))
        if value and value[1] > time.time():
            return value[0]
        _keys.pop(_id(token), None)
    return None


def forget_key(token):
    with _guard:
        _keys.pop(_id(token), None)


def effective_key():
    # Public application requests may only use the requesting session credential.
    return _current.get()


def bind_key(key):
    return _current.set(key)


def reset_key(token):
    _current.reset(token)


def _expire_keys():
    while True:
        time.sleep(30)
        with _guard:
            now = time.time()
            for session in list(_keys):
                if _keys[session][1] <= now:
                    _keys.pop(session, None)


threading.Thread(target=_expire_keys, daemon=True, name="session-key-expiry").start()
