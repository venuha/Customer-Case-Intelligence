"""Reproducible document-level retrieval experiment; no invented judge scores."""

import argparse, json, os, statistics, time, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.rag.retrieval import (
    HybridIndex,
    LocalEmbeddings,
    CorpusLoader,
    get_reranker,
    RERANK_MODEL,
)

ROOT = Path(__file__).resolve().parents[1]

QUESTIONS = [
    ("CASE-1001", "Was the returned package delivered?", ["CASE-1001-shipping"]),
    (
        "CASE-1001",
        "Did support say the refund was completed?",
        ["CASE-1001-conversation"],
    ),
    ("CASE-1001", "What is the requested return amount?", ["CASE-1001-return"]),
    (
        "CASE-1002",
        "What is the processor refund trace reference?",
        ["CASE-1002-refund"],
    ),
    (
        "CASE-1002",
        "Does the statement show a posted merchant refund credit?",
        ["CASE-1002-statement"],
    ),
    ("CASE-1002", "What amount was approved?", ["CASE-1002-approval"]),
    ("CASE-1003", "Which device inspection is missing?", ["CASE-1003-inspection"]),
    ("CASE-1003", "How much merchant refund credit posted?", ["CASE-1003-statement"]),
    ("CASE-1003", "How much refund was submitted?", ["CASE-1003-refund"]),
    ("CASE-1004", "Is the merchant refund posted?", ["CASE-1004-statement"]),
    ("CASE-1004", "What is the refund processor reference?", ["CASE-1004-refund"]),
    ("CASE-1004", "Was device inspection accepted?", ["CASE-1004-inspection"]),
    ("CASE-1005", "Does tracking prove carrier acceptance?", ["CASE-1005-shipping"]),
    ("CASE-1005", "What return label was created?", ["CASE-1005-return"]),
    ("CASE-1005", "Which device was ordered?", ["CASE-1005-order"]),
    (
        "CASE-1006",
        "Does the scanned device match the expected device?",
        ["CASE-1006-inspection"],
    ),
    ("CASE-1006", "What is the order device identifier?", ["CASE-1006-order"]),
    ("CASE-1006", "Was the package delivered?", ["CASE-1006-shipping"]),
    ("CASE-1007", "What amount was approved for refund?", ["CASE-1007-approval"]),
    (
        "CASE-1007",
        "Is a matching refund posted in the statement?",
        ["CASE-1007-statement"],
    ),
    (
        "CASE-1007",
        "Was the device accepted after inspection?",
        ["CASE-1007-inspection"],
    ),
    (
        "CASE-1008",
        "Is the dispute credit provisional or a merchant refund?",
        ["CASE-1008-statement"],
    ),
    (
        "CASE-1008",
        "What trace reference accompanies the submitted refund?",
        ["CASE-1008-refund"],
    ),
    ("CASE-1008", "What payment was captured?", ["CASE-1008-payment"]),
    (
        "CASE-1001",
        "Compare the agent completion claim with the customer-provided statement.",
        ["CASE-1001-conversation", "CASE-1001-statement"],
    ),
    (
        "CASE-1002",
        "Was the money sent and is receipt visible to the customer?",
        ["CASE-1002-refund", "CASE-1002-statement"],
    ),
    (
        "CASE-1003",
        "Connect the uninspected second device with the partial credit.",
        ["CASE-1003-inspection", "CASE-1003-statement"],
    ),
    (
        "CASE-1004",
        "Connect the outgoing refund and the incoming credit.",
        ["CASE-1004-refund", "CASE-1004-statement"],
    ),
    (
        "CASE-1005",
        "Does generating return paperwork establish that the carrier took possession?",
        ["CASE-1005-return", "CASE-1005-shipping"],
    ),
    (
        "CASE-1006",
        "Compare the purchased device identifier with the scanned return.",
        ["CASE-1006-order", "CASE-1006-inspection"],
    ),
    (
        "CASE-1007",
        "Does internal approval mean the customer received a credit?",
        ["CASE-1007-approval", "CASE-1007-statement"],
    ),
    (
        "CASE-1008",
        "Distinguish the merchant payment record from the temporary dispute adjustment.",
        ["CASE-1008-refund", "CASE-1008-statement"],
    ),
]


def main():
    import hashlib

    parser = argparse.ArgumentParser()
    parser.add_argument("--judge", action="store_true")
    parser.add_argument("--output-prefix", default="evaluation-expanded")
    parser.add_argument("--backend", choices=("local", "pinecone"), default="local")
    args = parser.parse_args()
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
    emb = LocalEmbeddings()
    docs = CorpusLoader().load()
    results = {}
    annotations = json.loads((ROOT / "data/eval/evidence.json").read_text())
    get_reranker().rerank
    list(get_reranker().rerank("refund", ["A merchant credit posted."]))
    indexes = {}
    for name, strategy, rerank in [
        ("fixed", "fixed", False),
        ("fixed_cross_encoder", "fixed", True),
        ("semantic", "semantic", False),
        ("semantic_cross_encoder", "semantic", True),
        ("structure_cross_encoder", "structure", True),
    ]:
        print("Evaluating " + name, flush=True)
        if strategy not in indexes:
            indexes[strategy] = HybridIndex(
                docs,
                emb,
                strategy,
                backend="pinecone-strict" if args.backend == "pinecone" else "local",
            )
        index = indexes[strategy]
        rows = []
        for n, (cid, q, gold) in enumerate(QUESTIONS):
            start = time.perf_counter()
            hits = index.search(q, cid, k=6, rerank=rerank)
            latency = (time.perf_counter() - start) * 1000
            targets = annotations[n]["evidence"]
            relevant = [
                any(
                    h["id"] == t["source_id"]
                    and " ".join(t["anchor"].split()) in " ".join(h["text"].split())
                    for t in targets
                )
                for h in hits
            ]
            found = sum(
                any(
                    h["id"] == t["source_id"]
                    and " ".join(t["anchor"].split()) in " ".join(h["text"].split())
                    for h in hits
                )
                for t in targets
            )
            ids = [h["id"] for h in hits]
            rows.append(
                {
                    "case_id": cid,
                    "question": q,
                    "gold": gold,
                    "evidence_targets": targets,
                    "retrieved": [
                        {
                            k: h[k]
                            for k in (
                                "id",
                                "chunk_id",
                                "score",
                                "fusion_score",
                                "reranker",
                                "retrieval_backend",
                            )
                        }
                        for h in hits
                    ],
                    "recall": found / len(targets),
                    "precision": sum(relevant) / 6,
                    "document_recall": len(set(ids) & set(gold)) / len(gold),
                    "reciprocal_rank": next(
                        (1 / (j + 1) for j, v in enumerate(relevant) if v), 0
                    ),
                    "latency_ms": round(latency, 1),
                }
            )
        results[name] = {
            "chunks": len(index.docs),
            "recall_at_6": statistics.mean(r["recall"] for r in rows),
            "precision_at_6": statistics.mean(r["precision"] for r in rows),
            "document_recall_at_6": statistics.mean(r["document_recall"] for r in rows),
            "mrr_at_6": statistics.mean(r["reciprocal_rank"] for r in rows),
            "median_ms": statistics.median(r["latency_ms"] for r in rows),
            "p95_ms": sorted(r["latency_ms"] for r in rows)[30],
            "questions": rows,
        }
    report = {
        "date": "2026-10-17",
        "dataset": "PDF corpus: same 32 primary queries; frozen source-ID evidence spans, whitespace normalized for PDF reflow",
        "corpus_sha256": hashlib.sha256(
            (ROOT / "data/corpus/manifest.json").read_bytes()
        ).hexdigest(),
        "queries_sha256": hashlib.sha256(json.dumps(QUESTIONS).encode()).hexdigest(),
        "annotations_sha256": hashlib.sha256(
            json.dumps(annotations, sort_keys=True).encode()
        ).hexdigest(),
        "backend": args.backend,
        "reranker": RERANK_MODEL,
        "reranker_input": "Document title + source label + case scope + passage text; same source context in all reranked conditions",
        "protocol": "Explicit cl100k_base tokenizer. 350-token recursive baseline (40 overlap); semantic 70th-percentile adjacent embedding distance, same 350-token cap; BGE embeddings + BM25 RRF top-20 shortlist in every condition; return six chunks; no parent-document promotion during evaluation.",
        "results": results,
        "faithfulness": "Not measured without live generation and a judge. Exact evidence-span recall and quote existence are not faithfulness.",
        "limitations": [
            "Eight fictional cases; template-assisted synthetic text is not representative of real institutional data.",
            "The 32 questions are a development benchmark, not an independently held-out test.",
            "Evidence annotations identify selected sufficient passages; unannotated supporting paraphrases can be scored as irrelevant.",
            "This report uses passage-level top-six metrics; the prior short-corpus report used unique-document metrics and is not directly comparable.",
            "Cold model downloads, index building, and OpenAI generation are excluded from warm retrieval timings.",
        ],
    }
    for prefix in ("fixed", "semantic"):
        a = results[prefix]
        b = results[prefix + "_cross_encoder"]
        report[prefix + "_reranking_delta"] = {
            m: b[m] - a[m]
            for m in ("recall_at_6", "precision_at_6", "mrr_at_6", "median_ms")
        }
    if args.judge:
        from dotenv import load_dotenv

        load_dotenv(ROOT / ".env")
        if not os.getenv("OPENAI_API_KEY"):
            raise SystemExit(
                "Set OPENAI_API_KEY in .env before requesting generation/judge evaluation."
            )
        from app.rag.graph import build_graph
        from app.security.provider_keys import bind_key, reset_key
        from langchain_openai import ChatOpenAI
        from pydantic import BaseModel, Field

        class Grade(BaseModel):
            supported_claims: int = Field(ge=0)
            total_claims: int = Field(ge=0)
            explanation: str

        raw = json.loads((ROOT / "data/documents.json").read_text())
        cases = {c["id"]: c for c in json.loads((ROOT / "data/cases.json").read_text())}
        graph = build_graph(HybridIndex(docs, emb), cases, raw)
        judge = ChatOpenAI(
            model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
            temperature=0,
            timeout=30,
            max_retries=1,
        ).with_structured_output(Grade)
        grades = []
        for cid, q, _ in QUESTIONS:
            # Offline evaluation is an explicit administrator operation, never a web request.
            credential = bind_key(os.environ["OPENAI_API_KEY"])
            try:
                answer = graph.invoke({"case_id": cid, "question": q})
            finally:
                reset_key(credential)
            if answer.get("mode") != "openai":
                grades.append(
                    {
                        "question": q,
                        "error": "Generation did not complete in OpenAI mode",
                    }
                )
                continue
            grade = judge.invoke(
                "Evaluate only whether each answer claim is supported by the supplied evidence. Do not use outside knowledge. Count claims and supported claims. Evidence: "
                + json.dumps(answer["evidence"])
                + " Answer: "
                + json.dumps(answer["answer"])
            )
            grades.append({"question": q, **grade.model_dump()})
        report["generation_judge"] = grades
    (ROOT / "docs" / f"{args.output_prefix}.json").write_text(
        json.dumps(report, indent=2)
    )
    lines = [
        "# Chunking comparison and cross-encoder impact",
        "",
        report["dataset"] + ".",
        "",
        "## Controlled protocol",
        "",
        report["protocol"],
        "",
        "Trained reranker: `"
        + RERANK_MODEL
        + "` (FastEmbed ONNX). Scores below are measured.",
        "",
        "| Configuration | Chunks | Evidence recall@6 | Evidence precision@6 | Evidence MRR@6 | Document recall@6 | Median ms |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for name, r in results.items():
        lines.append(
            f"| {name} | {r['chunks']} | {r['recall_at_6']:.3f} | {r['precision_at_6']:.3f} | {r['mrr_at_6']:.3f} | {r['document_recall_at_6']:.3f} | {r['median_ms']:.1f} |"
        )
    lines += ["", "## Paired reranking impact", ""]
    for prefix in ("fixed", "semantic"):
        delta = report[prefix + "_reranking_delta"]
        lines.append(
            f"- {prefix}: evidence recall {delta['recall_at_6'] * 100:+.2f} percentage points; precision {delta['precision_at_6'] * 100:+.2f} points; MRR {delta['mrr_at_6']:+.3f}; median latency {delta['median_ms']:+.1f} ms."
        )
    lines += ["", "## Failure analysis", ""]
    for name, r in results.items():
        failures = [q for q in r["questions"] if q["recall"] < 1]
        lines.append(f"### {name}: {len(failures)} incomplete-evidence questions")
        lines += [
            "- "
            + q["case_id"]
            + ": "
            + q["question"]
            + f" (evidence recall {q['recall']:.2f})"
            for q in failures
        ]
    lines += (
        ["", "## Limits", ""]
        + ["- " + x for x in report["limitations"]]
        + [
            "",
            "Faithfulness: " + report["faithfulness"],
            "",
            "Per-query ranks, source IDs, chunk IDs, model scores, and corpus/query hashes are recorded in evaluation.json. No query or gold annotation is loaded by the application retriever.",
        ]
    )
    (ROOT / "docs" / f"{args.output_prefix}.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines[:25]), flush=True)


if __name__ == "__main__":
    main()
