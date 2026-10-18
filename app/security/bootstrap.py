"""One-time hosted administrator creation; never resets an existing account."""

import json
import os
import sqlite3

from ..config import data_dir
from .auth import create_user, database, initialize


def bootstrap_admin():
    initialize()
    with sqlite3.connect(database()) as db:
        if db.execute(
            "SELECT 1 FROM users WHERE role='head' AND active=1 LIMIT 1"
        ).fetchone():
            return False
    username = os.getenv("CCI_BOOTSTRAP_USERNAME", "owner")
    password = os.getenv("CCI_BOOTSTRAP_PASSWORD", "")
    if len(password) < 12 or len(password) > 512:
        raise ValueError(
            "Set a private CCI_BOOTSTRAP_PASSWORD of 12 to 512 characters for first launch."
        )
    cases = [case["id"] for case in json.loads((data_dir() / "cases.json").read_text())]
    try:
        create_user(username, password, "head", cases)
    except sqlite3.IntegrityError:
        raise ValueError(
            "Bootstrap username already exists; choose another username or use local account administration."
        ) from None
    return True
