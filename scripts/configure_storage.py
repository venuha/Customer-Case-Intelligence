"""Prompt privately for durable storage credentials; never echo or publish them."""

import argparse
import getpass
from pathlib import Path
from urllib.parse import quote

from dotenv import set_key

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True)
    parser.add_argument("--pooler-host", required=True)
    args = parser.parse_args()
    if not args.project.isalnum() or not args.pooler_host.endswith(
        ".pooler.supabase.com"
    ):
        parser.error(
            "Use the project reference and transaction-pooler host from Supabase."
        )
    password = getpass.getpass("Supabase database password (hidden): ")
    key = getpass.getpass("Supabase legacy service_role key (hidden): ")
    if not password or not key:
        raise SystemExit("Nothing saved: both private values are required.")
    path = ROOT / ".env"
    path.touch(mode=0o600, exist_ok=True)
    path.chmod(0o600)
    values = {
        "DATABASE_URL": f"postgresql://postgres.{args.project}:{quote(password, safe='')}@{args.pooler_host}:6543/postgres",
        "SUPABASE_URL": f"https://{args.project}.supabase.co",
        "SUPABASE_SERVICE_ROLE_KEY": key,
        "SUPABASE_STORAGE_BUCKET": "cci-private-documents",
    }
    for name, value in values.items():
        set_key(path, name, value)
    path.chmod(0o600)
    print(
        "Private storage configuration saved in ignored .env. No values were printed."
    )


if __name__ == "__main__":
    main()
