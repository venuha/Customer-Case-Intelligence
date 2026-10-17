"""Reproducible, fictional PDF corpus. Never reads credentials or runtime databases."""

import hashlib, json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.security.policy import minimum_role
from app.documents.rendering import render

ROOT = Path(__file__).resolve().parents[1]


def main():
    records = json.loads((ROOT / "data/documents.json").read_text()) + json.loads(
        (ROOT / "data/public/references.json").read_text()
    )
    manifest = []
    for r in records:
        path = ROOT / "data/corpus" / f"{r['id']}.pdf"
        render(r["text"], path, r["title"], r["id"])
        manifest.append(
            {
                **{k: v for k, v in r.items() if k not in ("text", "facts")},
                "min_role": minimum_role(r.get("kind", "public_guidance")),
                "pdf": str(path.relative_to(ROOT)),
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
        )
    (ROOT / "data/corpus/manifest.json").write_text(json.dumps(manifest, indent=2))
    print(f"Generated {len(manifest)} source PDFs and provenance manifest.")


if __name__ == "__main__":
    main()
