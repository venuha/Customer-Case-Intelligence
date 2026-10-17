"""Read searchable content from PDFs, preserving tables and page provenance."""

import hashlib, json
import pymupdf as fitz
from langchain_core.documents import Document
from ..config import ROOT, data_dir


def pdf_pages(record):
    path = ROOT / record["pdf"]
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != record["sha256"]:
        raise ValueError("Source PDF hash mismatch: " + record["id"])
    cache = data_dir() / "index" / "extracted"
    cache.mkdir(parents=True, exist_ok=True)
    cached = cache / (digest + ".json")
    if cached.exists():
        return json.loads(cached.read_text())
    pages = []
    with fitz.open(path) as pdf:
        for page in pdf:
            tables = page.find_tables().tables
            items = []
            for table in tables:
                rows = table.extract()
                rows = [
                    [" ".join((cell or "").split()) for cell in row] for row in rows
                ]
                if rows:
                    text = (
                        "| "
                        + " | ".join(rows[0])
                        + " |\n| "
                        + " | ".join(["---"] * len(rows[0]))
                        + " |\n"
                        + "\n".join("| " + " | ".join(row) + " |" for row in rows[1:])
                    )
                    items.append((table.bbox[1], text))
            for block in page.get_text("blocks"):
                if block[1] < 45 or block[3] > 750:
                    continue
                rect = fitz.Rect(block[:4])
                if any(
                    (rect & fitz.Rect(t.bbox)).get_area() > rect.get_area() * 0.4
                    for t in tables
                ):
                    continue
                text = " ".join(block[4].split())
                if text and "Customer Case Intelligence | Fictional" not in text:
                    items.append((block[1], text))
            pages.append(
                "\n\n".join(text for _, text in sorted(items, key=lambda x: x[0]))
            )
    cached.write_text(json.dumps(pages))
    return pages


def load_pdf_documents():
    manifest = json.loads((data_dir() / "corpus/manifest.json").read_text())
    documents = []
    for record in manifest:
        for page, text in enumerate(pdf_pages(record), 1):
            if text.strip():
                documents.append(
                    Document(page_content=text, metadata={**record, "page": page})
                )
    return documents
