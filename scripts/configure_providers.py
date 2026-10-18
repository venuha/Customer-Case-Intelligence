"""Local terminal-only credential setup. Secrets are never echoed or returned."""

from getpass import getpass
from pathlib import Path
import sys
from dotenv import set_key

ROOT = Path(__file__).resolve().parents[1]


def main():
    if not sys.stdin.isatty():
        raise SystemExit(
            "Run this setup in your own interactive terminal; redirected secret input is disabled."
        )
    path = ROOT / ".env"
    path.touch(mode=0o600, exist_ok=True)
    path.chmod(0o600)
    print("Private local setup. Blank input preserves an existing value.")
    for name in ("PINECONE_API_KEY", "OPENAI_API_KEY"):
        value = getpass(f"{name} (hidden): ").strip()
        if value:
            if any(c.isspace() for c in value) or len(value) > 512:
                raise SystemExit("Invalid key format; no value printed.")
            set_key(str(path), name, value)
    name = (
        input("Pinecone index name [customer-case-intelligence]: ").strip()
        or "customer-case-intelligence"
    )
    if not all(c.islower() or c.isdigit() or c == "-" for c in name):
        raise SystemExit(
            "Index name must contain lowercase letters, numbers and hyphens."
        )
    set_key(str(path), "PINECONE_INDEX_NAME", name)
    set_key(str(path), "VECTOR_BACKEND", "pinecone")
    path.chmod(0o600)
    print(
        "Saved privately. Create a 384-dimension cosine index in Pinecone, then run scripts/sync_pinecone.py. Restart the app after configuration changes."
    )


if __name__ == "__main__":
    main()
