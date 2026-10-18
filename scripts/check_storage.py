"""Verify private durable providers without printing credentials or provider errors."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.security.auth import initialize
from app.storage.database import connect, remote
from app.storage.uploads import initialize as initialize_uploads


def main():
    if not remote():
        raise SystemExit(
            "Storage is not configured. Run the private setup helper first."
        )
    try:
        initialize()
        initialize_uploads()
        with connect(None) as db:
            assert db.execute("SELECT 1").fetchone()[0] == 1
    except Exception:
        raise SystemExit(
            "Storage check failed. Check the saved password, server key, and private bucket settings; no credential values were printed."
        ) from None
    print(
        "Postgres connection: OK. Private PDF bucket: OK. Credentials were not printed."
    )


if __name__ == "__main__":
    main()
