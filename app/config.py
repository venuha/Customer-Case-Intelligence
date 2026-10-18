"""Process settings. Secrets remain in the environment or ignored runtime files."""

import os
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
APP_NAME = "Customer Case Intelligence"
SUBTITLE = "Return & Refund Intelligence"
TAGLINE = "One case. Every connection."


def data_dir():
    return ROOT / os.getenv("DATA_DIR", "data")


def runtime_dir():
    path = Path(os.getenv("CCI_RUNTIME_DIR", str(ROOT / "work")))
    path.mkdir(parents=True, exist_ok=True)
    path.chmod(0o700)
    return path


def index_dir():
    path = Path(os.getenv("CCI_INDEX_DIR", str(data_dir() / "index")))
    path.mkdir(parents=True, exist_ok=True)
    return path
