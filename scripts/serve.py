"""Single-process container entrypoint; persistent state, private first administrator."""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.config import index_dir, runtime_dir
from app.security.bootstrap import bootstrap_admin


def main():
    os.umask(0o077)
    try:
        port = int(os.getenv("PORT", "8000"))
        if not 1 <= port <= 65535:
            raise ValueError("PORT must be between 1 and 65535.")
        if os.getenv("REQUIRE_DURABLE_STORAGE") == "true":
            required = ("DATABASE_URL", "SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY")
            if not all(os.getenv(key) for key in required):
                raise ValueError(
                    "Configure the private database and document storage before hosted startup."
                )
        # Child directories avoid changing ownership/permissions of the disk mount itself.
        runtime_dir()
        index_dir()
        bootstrap_admin()
    except Exception as error:
        # Our validation errors contain no values from private configuration.
        message = (
            str(error)
            if isinstance(error, ValueError)
            else "Persistent storage could not be initialized. Check private server configuration."
        )
        raise SystemExit("Startup configuration error: " + message) from None
    os.execvp(
        "uvicorn",
        [
            "uvicorn",
            "app.main:app",
            "--host",
            "0.0.0.0",
            "--port",
            str(port),
            "--workers",
            "1",
            "--proxy-headers",
            "--forwarded-allow-ips",
            os.getenv("FORWARDED_ALLOW_IPS", "127.0.0.1"),
        ],
    )


if __name__ == "__main__":
    main()
