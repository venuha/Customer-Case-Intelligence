"""Live case/role checks on the synthetic corpus and a controlled fallback probe."""

import json
import hashlib
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv

load_dotenv(ROOT / ".env")
from app.rag.retrieval import HybridIndex
from app.rag.pinecone_store import connect
from app.security.policy import ROLES, minimum_role, role_allows


def main():
    try:
        index = HybridIndex(strategy="fixed", backend="pinecone-strict")
        checks = []
        for cid in sorted(
            {d.metadata["case_id"] for d in index.docs if d.metadata["case_id"]}
        ):
            for role in ROLES:
                hits = index.search(
                    "return refund bank status", cid, rerank=False, role=role
                )
                assert hits and all(h["retrieval_backend"] == "pinecone" for h in hits)
                assert all(
                    h["case_id"] in (cid, None)
                    and role_allows(role, minimum_role(h["kind"]))
                    for h in hits
                )
                checks.append({"case_id": cid, "role": role, "passed": True})
        index.backend = "pinecone"
        original = index.cloud

        def outage(*args):
            raise RuntimeError("Controlled provider-failure simulation")

        index.cloud = SimpleNamespace(ranking=outage)
        fallback = index.search(
            "refund", "CASE-1001", rerank=False, role="customer_service"
        )
        assert fallback and all(
            h["retrieval_backend"] == "local-fallback" for h in fallback
        )
        assert all(
            h["case_id"] in ("CASE-1001", None)
            and role_allows("customer_service", minimum_role(h["kind"]))
            for h in fallback
        )
        index.cloud = original
        stats = connect().describe_index_stats(timeout=5)
        report = {
            "date_utc": datetime.now(timezone.utc).isoformat(),
            "corpus_sha256": hashlib.sha256(
                (ROOT / "data/corpus/manifest.json").read_bytes()
            ).hexdigest(),
            "dimension": 384,
            "metric": "cosine",
            "namespaces": {
                name: info.vector_count for name, info in stats.namespaces.items()
            },
            "case_role_checks": checks,
            "controlled_failure_fallback_passed": True,
            "private_uploads": "Not synchronized; owner-local policy tested separately",
            "passed": True,
        }
        (ROOT / "docs/pinecone-validation.json").write_text(
            json.dumps(report, indent=2)
        )
        print(
            f"Live Pinecone validation passed: {len(checks)} case/role queries; controlled local fallback passed."
        )
    except Exception:
        raise SystemExit(
            "Pinecone validation failed; provider details suppressed."
        ) from None


if __name__ == "__main__":
    main()
