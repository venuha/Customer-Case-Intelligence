"""Build the PDF companion from versioned, original project documentation."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.documents.rendering import render

ROOT = Path(__file__).resolve().parents[1]


def main():
    names = [
        "architecture-and-access.md",
        "framework.md",
        "evaluation-pdf.md",
        "table-evaluation.md",
        "implementation-provenance.md",
        "validation.md",
    ]
    text = "\n\n".join((ROOT / "docs" / name).read_text() for name in names)
    target = ROOT / "docs/pdf/architecture-and-access.pdf"
    render(text, target, "Customer Case Intelligence - Project Report")
    print("Built project PDF companion.")


if __name__ == "__main__":
    main()
