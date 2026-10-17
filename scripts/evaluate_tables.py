"""Supplementary table retrieval probe; does not replace the original 32 queries."""

import json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.rag.retrieval import CorpusLoader, LocalEmbeddings, HybridIndex

ROOT = Path(__file__).resolve().parents[1]


def main():
    cases = json.loads((ROOT / "data/cases.json").read_text())
    docs = CorpusLoader().load()
    emb = LocalEmbeddings()
    results = {}
    for strategy in ("fixed", "structure"):
        index = HybridIndex(docs, emb, strategy)
        for rerank in (False, True):
            rows = []
            for case in cases:
                amount = case["amount_cents"]
                tax = amount * 7 // 107
                question = f"For order {case['order_id']}, what tax allocation and control total are listed in the order confirmation financial allocation table?"
                source = case["id"] + "-order"
                anchors = [
                    f"Tax allocation | {tax / 100:.2f}",
                    f"Total for this record | {amount / 100:.2f}",
                ]
                hits = index.search(question, case["id"], k=6, rerank=rerank)
                found = sum(
                    any(h["id"] == source and a in h["text"] for h in hits)
                    for a in anchors
                )
                rows.append(
                    {
                        "case_id": case["id"],
                        "question": question,
                        "source_id": source,
                        "anchors": anchors,
                        "recall": found / 2,
                        "retrieved": [h["chunk_id"] for h in hits],
                    }
                )
            results[strategy + ("_cross_encoder" if rerank else "")] = {
                "table_evidence_recall_at_6": sum(r["recall"] for r in rows)
                / len(rows),
                "questions": rows,
            }
    report = {
        "dataset": "Eight supplemental financial allocation table questions; not included in the primary 32-query result",
        "results": results,
    }
    (ROOT / "docs/table-evaluation.json").write_text(json.dumps(report, indent=2))
    (ROOT / "docs/table-evaluation.md").write_text(
        "# Supplemental financial table evaluation\n\n"
        + report["dataset"]
        + ". Requires both the tax amount and the control total from the designated order document.\n\n| Configuration | Evidence recall@6 |\n|---|---:|\n"
        + "\n".join(
            f"| {k} | {v['table_evidence_recall_at_6']:.3f} |"
            for k, v in results.items()
        )
        + "\n\nThis conservative source-specific probe can expose confusion between similarly worded allocation tables in order, payment, approval, and refund documents. It measures evidence retrieval, not generated arithmetic accuracy.\n"
    )
    print(
        json.dumps(
            {k: v["table_evidence_recall_at_6"] for k, v in results.items()}, indent=2
        )
    )


if __name__ == "__main__":
    main()
