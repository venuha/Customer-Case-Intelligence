"""Check allowlisted publication files, including PDF text; never prints matched values."""

import json, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
TOP = {
    "README.md",
    "requirements.txt",
    "requirements.lock",
    "requirements-dev.txt",
    "Dockerfile",
    "render.yaml",
    "start.command",
    ".env.example",
    ".gitignore",
    ".dockerignore",
    "pyproject.toml",
    ".gitattributes",
}


def publication_files():
    files = [ROOT / name for name in TOP if (ROOT / name).is_file()]
    for directory in ("app", "data", "docs", "scripts", "tests", ".github"):
        files.extend(
            p
            for p in (ROOT / directory).rglob("*")
            if p.is_file()
            and p.name != ".DS_Store"
            and "__pycache__" not in p.parts
            and not p.is_relative_to(ROOT / "data/index")
            and p.suffix not in (".pyc", ".png")
        )
    return files


def scan():
    from dotenv import dotenv_values
    import pymupdf

    secrets = [
        v
        for k, v in dotenv_values(ROOT / ".env").items()
        if v
        and any(w in k.upper() for w in ("KEY", "SECRET", "TOKEN", "PASSWORD"))
        and len(v) >= 10
    ]
    patterns = [
        re.compile(r"sk-(?:proj-)?[A-Za-z0-9_-]{24,}"),
        re.compile(r"gh[pousr]_[A-Za-z0-9]{25,}"),
        re.compile(r"AKIA[0-9A-Z]{16}"),
        re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    ]
    bad = []
    files = publication_files()
    for p in files:
        if p.suffix == ".pdf":
            with pymupdf.open(p) as pdf:
                text = "\n".join(page.get_text() for page in pdf)
        else:
            try:
                text = p.read_text()
            except UnicodeDecodeError:
                continue
        compact = "".join(text.split())
        if any(value in text or value in compact for value in secrets) or any(
            pattern.search(text) for pattern in patterns
        ):
            bad.append(str(p.relative_to(ROOT)))
    print(json.dumps({"files_checked": len(files), "findings": bad, "passed": not bad}))
    return not bad


if __name__ == "__main__":
    sys.exit(0 if scan() else 1)
