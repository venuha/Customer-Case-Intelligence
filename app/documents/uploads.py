"""Private, owner-scoped supplemental PDFs; never alter verified financial facts."""

import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pymupdf
from langchain_core.documents import Document

from ..config import runtime_dir
from ..storage import uploads as durable_uploads
from ..storage.database import remote

MAX_BYTES = 10 * 1024 * 1024


def folder(user, cid):
    path = (
        runtime_dir()
        / "uploads"
        / hashlib.sha256(user.username.encode()).hexdigest()
        / cid
    )
    path.mkdir(parents=True, exist_ok=True)
    return path


def records(user, cid):
    if remote():
        return durable_uploads.records(user, cid)
    return [
        json.loads(path.read_text())
        for path in sorted(folder(user, cid).glob("*.json"))
    ]


def store_pdf(user, cid, name, content):
    if not content.startswith(b"%PDF-") or len(content) > MAX_BYTES:
        raise ValueError("Upload a PDF no larger than 10 MB.")
    existing = records(user, cid)
    if len(existing) >= 10:
        raise ValueError(
            "This case already has ten private uploads. Remove one before adding another."
        )
    try:
        with pymupdf.open(stream=content, filetype="pdf") as pdf:
            if pdf.needs_pass or len(pdf) > 50:
                raise ValueError("Use an unlocked PDF with at most 50 pages.")
            pages = [extract_page(page) for page in pdf]
    except ValueError:
        raise
    except Exception:
        raise ValueError("The PDF could not be read.") from None
    if not any(pages):
        raise ValueError("No readable text found. Scanned PDFs need OCR before upload.")
    if sum(map(len, pages)) > 200000:
        raise ValueError("Use a smaller document (up to 200,000 extracted characters).")
    did = "UPLOAD-" + uuid4().hex
    name = Path(name).name[:120] or "Uploaded document.pdf"
    record = {
        "id": did,
        "case_id": cid,
        "kind": "user_upload",
        "title": name,
        "source": "Your private PDF upload",
        "date": datetime.now(UTC).date().isoformat(),
        "synthetic": False,
        "facts": {},
        "owner": user.username,
        "sha256": hashlib.sha256(content).hexdigest(),
        "pages": pages,
        "text": "\n\n".join(pages),
    }
    if remote():
        durable_uploads.save(user, cid, record, content)
        return record
    path = folder(user, cid) / did
    path.with_suffix(".pdf").write_bytes(content)
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(record))
    os.chmod(temporary, 0o600)
    temporary.replace(path.with_suffix(".json"))
    os.chmod(path.with_suffix(".pdf"), 0o600)
    os.chmod(path.with_suffix(".json"), 0o600)
    return record


def get_record(user, cid, did):
    return next((r for r in records(user, cid) if r["id"] == did), None)


def documents(record):
    meta = {k: v for k, v in record.items() if k not in ("pages", "text", "facts")}
    return [
        Document(page_content=text, metadata={**meta, "page": n})
        for n, text in enumerate(record["pages"], 1)
        if text
    ]


def extract_page(page):
    tables = page.find_tables().tables
    items = []
    for table in tables:
        rows = [
            [" ".join((cell or "").split()) for cell in row] for row in table.extract()
        ]
        if not rows:
            continue
        items.append(
            (
                table.bbox[1],
                "| "
                + " | ".join(rows[0])
                + " |\n| "
                + " | ".join(["---"] * len(rows[0]))
                + " |\n"
                + "\n".join("| " + " | ".join(row) + " |" for row in rows[1:]),
            )
        )
    for block in page.get_text("blocks"):
        rect = pymupdf.Rect(block[:4])
        if any(
            (rect & pymupdf.Rect(table.bbox)).get_area() > rect.get_area() * 0.4
            for table in tables
        ):
            continue
        text = " ".join(block[4].split())
        if text:
            items.append((block[1], text))
    return "\n\n".join(text for _, text in sorted(items, key=lambda item: item[0]))


def remove_cached_indexes(did):
    from ..config import index_dir

    for path in index_dir().glob("*.chunks.json"):
        try:
            chunks = json.loads(path.read_text())
        except (ValueError, OSError):
            continue
        if not any(c.get("metadata", {}).get("id") == did for c in chunks):
            continue
        payload = json.dumps(
            [(c["text"], c["metadata"]) for c in chunks], sort_keys=True
        )
        fingerprint = hashlib.sha256(
            ("bge-small-en-v1.5-v1" + payload).encode()
        ).hexdigest()[:20]
        (path.parent / (fingerprint + ".npy")).unlink(missing_ok=True)
        path.unlink(missing_ok=True)


def remove(user, cid, did):
    if remote():
        durable_uploads.remove(user, cid, did)
    else:
        for extension in (".json", ".pdf"):
            (folder(user, cid) / (did + extension)).unlink(missing_ok=True)
