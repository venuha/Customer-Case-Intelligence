"""Package only secret-scanned, allowlisted source, synthetic PDFs and reports."""

from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
from scan_publication import publication_files, scan

ROOT = Path(__file__).resolve().parents[1]


def main():
    if not scan():
        raise SystemExit("Publication scan failed; nothing packaged.")
    output = ROOT / "outputs"
    output.mkdir(exist_ok=True)
    archive = output / "customer-case-intelligence.zip"
    with ZipFile(archive, "w", ZIP_DEFLATED) as z:
        for path in publication_files():
            z.write(path, path.relative_to(ROOT))
    print(f"Packaged {len(publication_files())} files: {archive.name}")


if __name__ == "__main__":
    main()
