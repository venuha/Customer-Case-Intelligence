"""Build an honest submission report from measured retrieval and RAGAS artifacts."""

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdf", action="store_true")
    args = parser.parse_args()
    retrieval = json.loads((ROOT / "docs/evaluation-pdf.json").read_text())
    ragas = json.loads((ROOT / "docs/evaluation-ragas.json").read_text())
    cloud_state = (
        "Live Pinecone-backed evaluation is complete. "
        if ragas.get("backend") == "pinecone" and ragas.get("status") == "complete"
        else "Live Pinecone synchronization and evaluation are not yet fully verified. "
    )
    lines = [
        "# Financial document intelligence: chunking and reranking",
        "",
        "Customer Case Intelligence | Return & Refund Intelligence",
        "",
        "One case. Every connection.",
        "",
        "# Submission status",
        "",
        "Measured local retrieval comparisons are complete. Pinecone integration is implemented and tested with mocks. "
        + cloud_state
        + "RAGAS execution status: "
        + ragas["status"]
        + ". "
        + ragas.get(
            "reason", "See the RAGAS companion report for detailed completion counts."
        ),
        "",
        "This document does not claim completed live RAGAS evaluation or measured Pinecone performance unless those companion artifacts record successful runs. A final demo recording and hosting deployment remain separate deliverables.",
        "",
        "# Required framework",
        "",
        "| Field | Decision |",
        "|---|---|",
        "| Use case | A support specialist asks where a fictional device return or refund stalled and which evidence connects merchant and bank events, through a case-scoped web assistant. |",
        "| Corpus | 91 English PDFs: synthetic orders, payments, returns, carrier scans, inspections, refund ledgers, statements, disputes and conversations, plus attributed public-guidance paraphrases. Source PDFs and their hash manifest are the narrative source of truth; structured fictional records support deterministic reconciliation. |",
        "| Ingestion and cleaning | Extract PDF text and tables with page/source provenance, normalize extraction artifacts and preserve financial table headers. Private uploads are supplemental and cannot overwrite verified case balances. |",
        "| Ingestion and freshness | The demonstration corpus is a versioned snapshot with explicit PDF rebuild and index synchronization; there is no live institution feed or production freshness SLA. New private PDFs are parsed on upload and enter only that owner's local case workspace. |",
        "| Chunking and embedding | Fixed recursive chunks target 350 cl100k_base tokens with 40 overlap; semantic splits use the 70th-percentile adjacent sentence/paragraph embedding distance and the same cap. BGE-small-en-v1.5 provides 384-dimensional local embeddings for both documents and queries. |",
        "| Retrieve | BM25 and cosine dense retrieval are fused using reciprocal ranks into the same top-20 candidate pool, returning six chunks in the controlled comparison. Dense retrieval uses optional Pinecone with local fallback; private uploads remain local. |",
        "",
        "# Controlled retrieval comparison",
        "",
        retrieval["protocol"],
        "",
        "The same 32 development questions and frozen sufficient-evidence anchors are used in every configuration. Exact source ID and whitespace-normalized passage anchors determine relevance. These are retrieval metrics, not RAGAS judge scores.",
        "",
        "| Configuration | Chunks | Recall@6 | Precision@6 | MRR@6 | Median ms |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for name, r in retrieval["results"].items():
        lines.append(
            f"| {name} | {r['chunks']} | {r['recall_at_6']:.3f} | {r['precision_at_6']:.3f} | {r['mrr_at_6']:.3f} | {r['median_ms']:.1f} |"
        )
    lines += [
        "",
        "# Reranking impact",
        "",
        "The trained cross-encoder is Xenova/ms-marco-MiniLM-L-6-v2, run locally with FastEmbed ONNX. It scores query-passage pairs jointly after hybrid retrieval. All paired conditions use the same candidate pool; source title and case metadata accompany passages in every reranked condition.",
        "",
    ]
    for prefix in ("fixed", "semantic"):
        d = retrieval[prefix + "_reranking_delta"]
        lines.append(
            f"- {prefix}: recall {d['recall_at_6'] * 100:+.2f} percentage points; precision {d['precision_at_6'] * 100:+.2f} points; MRR {d['mrr_at_6']:+.3f}; median latency {d['median_ms']:+.1f} ms."
        )
    lines += [
        "",
        "Reranking improved average recall modestly and added substantial local CPU latency. Semantic chunking did not beat the fixed baseline on this dataset. A separate eight-question financial-table probe passed all eight questions in each tested configuration; this small synthetic test is not a general table-accuracy guarantee.",
        "",
        "# Pinecone storage and fallback",
        "",
        "A serverless external-vector index must use 384 dimensions and cosine similarity. Separate content-versioned namespaces isolate fixed, semantic and table-aware chunks; deterministic vector IDs make re-uploading idempotent. Cloud records contain the vector, chunk text, source/page, case scope and required role level. Full PDFs, chunk metadata and NumPy vectors remain local for provenance and fallback.",
        "",
        "Pinecone case/role filters are applied before dense ranking. Every returned ID is checked against the local permitted set, and no remote text is trusted as authoritative. Cloud failure, incomplete synchronization or failed validation uses local retrieval. Strict Pinecone evaluation refuses fallback, preventing mislabeled cloud results. Private owner uploads are never included in the cloud synchronization command.",
        "",
        "Local storage: data/corpus/*.pdf and manifest.json hold source material; data/index/*.chunks.json holds chunk text/metadata; data/index/*.npy holds vectors. work/uploads holds private originals/extracted records. Runtime identities, keys, uploads, indexes and caches are excluded from Git and submission archives.",
        "",
        "# RAGAS evaluation",
        "",
        "Four configurations use the same 32 manually authored question/reference pairs: fixed, fixed with cross-encoder, semantic, and semantic with cross-encoder. The controlled LangChain generation chain receives only retrieved passages, with the same structured answer prompt and quote checks across conditions; additional deterministic application reconciliation is withheld to isolate retrieval effects.",
        "",
        "RAGAS 0.3.9 evaluates Faithfulness, LLMContextPrecisionWithReference and LLMContextRecall. Generation and judging use separately invoked OpenAI models recorded in the JSON artifact. RAGAS metrics are model judgments and are not interchangeable with exact-span recall/precision. Telemetry and tracing are disabled for this command.",
        "",
        "Current status: "
        + ragas["status"]
        + ". No successful judge scores are available unless recorded below and in evaluation-ragas.json. Missing, failed or non-finite metrics remain unmeasured, never fabricated zeros.",
        "",
    ]
    # Include the current metric table and paired deltas verbatim from our own runner.
    ragas_text = (ROOT / "docs/evaluation-ragas.md").read_text()
    start = ragas_text.index("| Configuration")
    end = ragas_text.index("## Execution and limits")
    lines += [
        ragas_text[start:end].replace(
            "## Paired reranking impact", "# RAGAS paired impact"
        ),
        "# Reproduce and complete",
        "",
        "1. Run scripts/configure_providers.py locally to enter Pinecone and OpenAI keys without echo. It writes only the ignored permission-600 .env file. Hosted infrastructure keys belong in server-side secret settings, never frontend code or a report.",
        "",
        "2. Create the compatible Pinecone index, then run scripts/sync_pinecone.py. Confirm every strategy namespace is fully visible. Restart the application after environment changes.",
        "",
        "3. Install requirements-eval.txt (or the exact requirements-eval.lock snapshot). Run scripts/evaluate_ragas.py --preflight, then scripts/evaluate_ragas.py --backend pinecone. For a controlled local experiment use --backend local. The full comparison uses 128 generated answers plus multiple judge calls and incurs provider charges.",
        "",
        "4. Run scripts/build_comparison_report.py --pdf after live evaluations to refresh this document. Run scripts/scan_publication.py and scripts/package_submission.py before sharing; record the application demo separately.",
        "",
        "# Limits and honest interpretation",
        "",
        "- Eight fictional cases and template-assisted source documents cannot establish production accuracy on real bank or merchant records.",
        "- The 32 questions are a development benchmark, not an independent held-out test. Reference annotations may miss valid supporting paraphrases.",
        "- Existing retrieval timing measurements exclude downloads, embedding/index construction and OpenAI generation; concurrent local workloads limit timing precision.",
        "- A cross-encoder can only reorder retrieved candidates. It cannot recover a passage outside the candidate set or prove a real-world event occurred.",
        "- Same-family generation/judge models can share biases. RAGAS results require human review, especially for claims about missing credits or provisional adjustments.",
        "- No live bank transfer, refund, dispute submission, external ticket or customer message is executed. The optional bank sandbox adapter is not a verified live institution connection.",
        "",
        "# Implementation provenance",
        "",
        "The supplied academy solution kit is architectural reference only. No Apple filings, sample scores, proprietary code or sample prompts are copied. This original implementation keeps the required fixed/semantic comparison, cross-encoder and RAGAS layers while documenting its different corpus, model sizes, chunk settings and hybrid retrieval.",
        "",
        "Primary technical references: https://sdk.pinecone.io/python/how-to/vectors/upsert-and-query.html ; https://docs.ragas.io/en/v0.3.9/getstarted/evals/ ; https://developers.openai.com/api/docs/guides/production-best-practices .",
        "",
        "Detailed provenance and per-query retrieval failures are in docs/evaluation-pdf.json and .md. Per-query RAGAS scores, completion state, model names and corpus/reference/prompt hashes are in docs/evaluation-ragas.json. No key or private customer record belongs in these artifacts.",
        "",
    ]
    text = "\n".join(lines)
    (ROOT / "docs/comparison-report.md").write_text(text)
    if args.pdf:
        import re
        from app.documents.rendering import render

        render(
            re.sub(r"(?m)^(#+ [^\n]+)\n\n(?=[^|#\n])", r"\1\n", text)
            .replace("structure_cross_encoder", "Table-aware + CE")
            .replace("semantic_cross_encoder", "Semantic + CE")
            .replace("fixed_cross_encoder", "Fixed + CE"),
            ROOT / "docs/pdf/comparison-report.pdf",
            "Financial RAG comparison report",
            "COMPARISON REPORT",
        )
    print("Comparison report refreshed; RAGAS status: " + ragas["status"])


if __name__ == "__main__":
    main()
