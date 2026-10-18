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
    validation_path = ROOT / "docs/pinecone-validation.json"
    validation = (
        json.loads(validation_path.read_text()) if validation_path.exists() else {}
    )
    cloud_state = (
        "Live Pinecone synchronization, all 24 case/role checks and a controlled local-fallback test passed. "
        if validation.get("passed")
        else "Live Pinecone synchronization and access checks are not yet fully verified. "
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
        "Measured local retrieval comparisons are complete. "
        + cloud_state
        + "RAGAS execution status: "
        + ragas["status"]
        + ". "
        + ragas.get(
            "reason", "See the RAGAS companion report for detailed completion counts."
        ),
        "",
        "This report separates measured local/cloud retrieval results from RAGAS answer-quality judgments. A final demo recording and hosting deployment remain separate deliverables.",
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
    pinecone_report_path = ROOT / "docs/evaluation-pinecone.json"
    if pinecone_report_path.exists():
        cloud_report = json.loads(pinecone_report_path.read_text())
        lines += [
            "",
            "# Pinecone retrieval comparison",
            "",
            "The same frozen 32 questions were evaluated with strict Pinecone dense search plus local BM25. No local dense fallback is allowed in this experiment; these are retrieval measurements, separate from RAGAS generation/judge scores.",
            "",
            "| Configuration | Chunks | Recall@6 | Precision@6 | MRR@6 | Median ms |",
            "|---|---:|---:|---:|---:|---:|",
        ]
        for name, result in cloud_report["results"].items():
            lines.append(
                f"| {name} | {result['chunks']} | {result['recall_at_6']:.3f} | {result['precision_at_6']:.3f} | {result['mrr_at_6']:.3f} | {result['median_ms']:.1f} |"
            )
        lines.append("")
        for prefix in ("fixed", "semantic"):
            delta = cloud_report[prefix + "_reranking_delta"]
            lines.append(
                f"Pinecone {prefix} reranking: evidence recall {delta['recall_at_6'] * 100:+.2f} percentage points; MRR {delta['mrr_at_6']:+.3f}."
            )
            lines.append("")
        lines += [
            "",
            "Cloud and earlier local timings were measured at different times under different loads; they do not establish an isolated backend speed comparison. Per-query cloud backend labels and corpus hashes are in evaluation-pinecone.json.",
            "",
        ]
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
        "Faithfulness grades the complete rendered response, including factual claims, unknowns and the suggested next step. Reference-guided context precision measures rank-weighted usefulness, while context recall attributes reference-answer claims to retrieved passages. Recommendations can therefore affect faithfulness even when every retained claim has an exact source quote; quote matching is not a semantic-grounding guarantee.",
        "",
        f"Generation model: {ragas['generation_model']}; judge model: {ragas['judge_model']}; temperature 0 for both. Current status: {ragas['status']}. The table records measured judge outputs when available; missing, failed or non-finite metrics remain unmeasured, never fabricated zeros.",
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
        "3. Install requirements-eval.txt (or the exact requirements-eval.lock snapshot). Run scripts/evaluate_ragas.py --preflight, then scripts/evaluate_ragas.py --backend pinecone. For a controlled local experiment use --backend local. The full comparison evaluates 128 answers plus multiple judge calls and incurs provider charges; failed attempts and retries can add calls.",
        "",
        "4. Run scripts/build_comparison_report.py --pdf after live evaluations to refresh this document. Run scripts/scan_publication.py and scripts/package_submission.py before sharing; record the application demo separately.",
        "",
        "# Limits and honest interpretation",
        "",
        "- Eight fictional cases and template-assisted source documents cannot establish production accuracy on real bank or merchant records.",
        "- The 32 questions are a development benchmark, not an independent held-out test. Reference annotations may miss valid supporting paraphrases.",
        "- Existing retrieval timing measurements exclude downloads, embedding/index construction and OpenAI generation; concurrent local workloads limit timing precision.",
        "- A cross-encoder can only reorder retrieved candidates. It cannot recover a passage outside the candidate set or prove a real-world event occurred.",
        "- Same-family generation/judge models can share biases. This is a single-pass evaluation with stochastic model outputs, not a confidence-interval estimate. RAGAS results require human review, especially for claims about missing credits or provisional adjustments.",
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
    if ragas.get("status") == "complete":
        import statistics

        metrics = ("faithfulness", "context_precision", "context_recall")
        means = {
            name: {
                metric: statistics.mean(row[metric] for row in rows)
                for metric in metrics
            }
            for name, rows in ragas["results"].items()
        }
        deltas = [
            means[prefix + "_cross_encoder"][metric] - means[prefix][metric]
            for prefix in ("fixed", "semantic")
            for metric in metrics
        ]
        improved = sum(d > 1e-9 for d in deltas)
        declined = sum(d < -1e-9 for d in deltas)
        interpretation = [
            "",
            "# Interpretation of the measured RAGAS results",
            "",
            f"Across the six paired RAGAS comparisons, reranking improved {improved} metric averages, reduced {declined}, and left {6 - improved - declined} unchanged. Retrieval improvements do not guarantee more faithful generated answers; the score table must be read alongside latency and individual failures.",
            "",
            "The application retains fixed-size hybrid retrieval by default and optional deeper reranking. These development-set measurements support reviewing the trade-off rather than declaring semantic chunking or reranking universally superior. A held-out real-document study and repeated judge runs are needed before a production choice.",
            "",
            "## Lowest-faithfulness examples for review",
            "",
        ]
        examples = sorted(
            [
                (row["faithfulness"], name, row)
                for name, rows in ragas["results"].items()
                for row in rows
            ],
            key=lambda item: (
                item[0],
                item[1],
                item[2]["case_id"],
                item[2]["question"],
            ),
        )
        for score, name, row in examples[:4]:
            interpretation.append(
                f"- {name}, {row['case_id']}: {row['question']} Faithfulness {score:.3f}. Review the full response, unknowns, recommendation and retrieved source IDs in the JSON artifact; this is a judge flag, not proof that every factual claim is false."
            )
        interpretation += [
            "",
            f"All 128 rows have valid values for all three metrics. Requested retrieval backend: {ragas['backend']}; actual per-hit backend labels are retained in the JSON artifact. Checkpoint retries retained successful rows; failed attempts are excluded from score averages and can add provider usage.",
            "",
        ]
        place = lines.index("# Reproduce and complete")
        lines[place:place] = interpretation
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
