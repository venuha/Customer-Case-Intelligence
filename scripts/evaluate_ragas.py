"""Paired RAGAS experiment on identical, frozen financial case questions.

No fallback to fabricated answers/scores. Provider errors are sanitized. Private
uploads, customer sessions and keys never enter the evaluation artifacts.
"""

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import statistics
import sys
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ["RAGAS_DO_NOT_TRACK"] = "true"
os.environ["LANGCHAIN_TRACING_V2"] = "false"
os.environ["LANGSMITH_TRACING"] = "false"
from dotenv import load_dotenv

load_dotenv(ROOT / ".env")
from app.rag.retrieval import CorpusLoader, HybridIndex, LocalEmbeddings
from app.rag.graph import Answer, PROMPT
from scripts.evaluate import QUESTIONS

CONFIGURATIONS = (
    ("fixed", "fixed", False),
    ("fixed_cross_encoder", "fixed", True),
    ("semantic", "semantic", False),
    ("semantic_cross_encoder", "semantic", True),
)
METRICS = ("faithfulness", "context_precision", "context_recall")


def read_references():
    rows = json.loads((ROOT / "data/eval/references.json").read_text())
    if [(r["case_id"], r["question"]) for r in rows] != [
        (c, q) for c, q, _ in QUESTIONS
    ]:
        raise ValueError(
            "Reference questions must exactly match frozen retrieval benchmark"
        )
    return rows


def response_text(answer):
    # Judge the actual claims and qualifications; source IDs are kept for audit separately.
    return "\n".join(
        [c.text for c in answer.claims]
        + ["Unknown: " + u for u in answer.unknowns]
        + ["Suggested next step: " + answer.suggested_next_step]
    )


def clean_score(value):
    try:
        number = float(value)
        return number if math.isfinite(number) and 0 <= number <= 1 else None
    except (ValueError, TypeError):
        return None


def save_report(report):
    (ROOT / "docs/evaluation-ragas.json").write_text(
        json.dumps(report, indent=2, allow_nan=False)
    )
    lines = [
        "# RAGAS chunking and reranking comparison",
        "",
        "**Status: " + report["status"] + ".**",
        "",
        "Four configurations use the same 32 development questions and independently authored reference answers. "
        "This experiment isolates retrieved context: top-six chunks, the same evidence-only LangChain prompt, "
        "the same OpenAI generation/judge models, and no deterministic case-reconciliation facts in the generation context. "
        "It does not benchmark the full application workflow or private uploads.",
        "",
        "| Configuration | Completed rows / expected | Faithfulness | Context precision | Context recall |",
        "|---|---:|---:|---:|---:|",
    ]
    for name, _, _ in CONFIGURATIONS:
        rows = report.get("results", {}).get(name, [])

        def average(metric):
            values = [r[metric] for r in rows if r.get(metric) is not None]
            return (
                f"{statistics.mean(values):.3f} (n={len(values)})"
                if values
                else "Not measured"
            )

        complete = sum(all(r.get(m) is not None for m in METRICS) for r in rows)
        lines.append(
            f"| {name} | {complete} / {report['question_count']} | "
            + " | ".join(average(m) for m in METRICS)
            + " |"
        )
    lines += ["", "## Paired reranking impact", ""]
    for prefix in ("fixed", "semantic"):
        a = report.get("results", {}).get(prefix, [])
        b = report.get("results", {}).get(prefix + "_cross_encoder", [])
        for metric in METRICS:
            paired = [
                (x[metric], y[metric])
                for x, y in zip(a, b)
                if x.get(metric) is not None
                and y.get(metric) is not None
                and x["question"] == y["question"]
            ]
            delta = (
                f"{statistics.mean(y - x for x, y in paired):+.3f} (n={len(paired)})"
                if paired
                else "Not measured"
            )
            lines.append(f"- {prefix}, {metric}: {delta}.")
    lines += [
        "",
        "## Execution and limits",
        "",
        "- Backend requested: "
        + report["backend"]
        + ". Pinecone runs refuse silent local fallback.",
        "- No live-provider scores are asserted until successful generation and judging finish. Missing or invalid metric outputs are null, never zero.",
        "- References are manually authored from synthetic records; the 32 questions are a development set, not a held-out or real-customer benchmark.",
        "- RAGAS context metrics are LLM judgments and differ from exact-span recall/precision in evaluation-pdf.md.",
        "- RAGAS 0.3.9; Faithfulness, LLMContextPrecisionWithReference and LLMContextRecall. No embedding-based judge metric is used.",
        "- Same model is used across all configurations; generation and judging are separate calls. Shared model bias and small sample size limit conclusions.",
        "- Tracing and RAGAS telemetry are disabled for this command. Only synthetic corpus passages are sent to OpenAI.",
        "- "
        + report.get(
            "reason",
            "See per-query results and provenance hashes in the JSON companion.",
        ),
        "",
    ]
    (ROOT / "docs/evaluation-ragas.md").write_text("\n".join(lines))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--backend", choices=("local", "pinecone"), default="local")
    parser.add_argument(
        "--preflight",
        action="store_true",
        help="Check inputs/credentials without any provider calls",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=32,
        help="1..32; smaller runs are explicitly partial",
    )
    args = parser.parse_args()
    if not 1 <= args.limit <= 32:
        parser.error("--limit must be 1..32")
    references = read_references()[: args.limit]
    report = {
        "status": "not_run",
        "question_count": args.limit,
        "full_question_count": 32,
        "backend": args.backend,
        "date_utc": datetime.now(timezone.utc).isoformat(),
        "generation_model": os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
        "judge_model": os.getenv(
            "RAGAS_JUDGE_MODEL", os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
        ),
        "corpus_sha256": hashlib.sha256(
            (ROOT / "data/corpus/manifest.json").read_bytes()
        ).hexdigest(),
        "references_sha256": hashlib.sha256(
            (ROOT / "data/eval/references.json").read_bytes()
        ).hexdigest(),
        "prompt_sha256": hashlib.sha256(str(PROMPT).encode()).hexdigest(),
        "results": {},
    }
    missing = [key for key in ("OPENAI_API_KEY",) if not os.getenv(key)]
    if args.backend == "pinecone":
        missing += [
            key
            for key in ("PINECONE_API_KEY", "PINECONE_INDEX_NAME")
            if not os.getenv(key)
        ]
    if missing or args.preflight:
        report["reason"] = (
            ("Missing private environment configuration: " + ", ".join(missing))
            if missing
            else "Preflight passed. No live API calls requested."
        )
        # Preflight must never erase a completed or partially completed experiment.
        previous = ROOT / "docs/evaluation-ragas.json"
        existing = json.loads(previous.read_text()) if previous.exists() else {}
        if not existing.get("results"):
            save_report(report)
        (ROOT / "docs/evaluation-ragas-preflight.json").write_text(
            json.dumps({k: v for k, v in report.items() if k != "results"}, indent=2)
        )
        print(report["reason"])
        return 2 if missing else 0
    from langchain_openai import ChatOpenAI
    from langsmith import tracing_context
    from ragas import EvaluationDataset, evaluate
    from ragas.llms import LangchainLLMWrapper
    from ragas.metrics import (
        Faithfulness,
        LLMContextPrecisionWithReference,
        LLMContextRecall,
    )
    from ragas.run_config import RunConfig
    import importlib.metadata

    report["ragas_version"] = importlib.metadata.version("ragas")
    model_args = dict(
        api_key=os.environ["OPENAI_API_KEY"],
        base_url="https://api.openai.com/v1",
        temperature=0,
        timeout=60,
        max_retries=1,
    )
    generator = ChatOpenAI(
        model=report["generation_model"], max_tokens=1600, **model_args
    ).with_structured_output(Answer)
    judge = LangchainLLMWrapper(ChatOpenAI(model=report["judge_model"], **model_args))
    emb = LocalEmbeddings()
    docs = CorpusLoader().load()
    indexes = {}
    report["status"] = "running"
    save_report(report)
    for name, strategy, rerank in CONFIGURATIONS:
        print("Evaluating " + name, flush=True)
        rows = report["results"][name] = []
        if strategy not in indexes:
            indexes[strategy] = HybridIndex(
                docs,
                emb,
                strategy,
                backend="pinecone-strict" if args.backend == "pinecone" else "local",
            )
        for reference in references:
            row = {
                **reference,
                "status": "failed",
                **{metric: None for metric in METRICS},
            }
            try:
                hits = indexes[strategy].search(
                    reference["question"],
                    reference["case_id"],
                    k=6,
                    rerank=rerank,
                    role="head",
                )
                contexts = [h["text"] for h in hits]
                context = "\n\n".join(
                    f"Source {h['id']} (page {h.get('page', 0)}):\n{h['text']}"
                    for h in hits
                )
                with tracing_context(enabled=False):
                    answer = (PROMPT | generator).invoke(
                        {
                            "question": reference["question"],
                            "context": context,
                            "reconciliation": "Not supplied in this controlled retrieval experiment.",
                        }
                    )
                    # Preserve the same quote-verification behavior for all variants.
                    valid = []
                    for claim in answer.claims:
                        text = "\n".join(
                            h["text"] for h in hits if h["id"] == claim.source_id
                        )
                        if claim.quote and claim.quote in text:
                            valid.append(claim)
                        else:
                            answer.unknowns.append(
                                "An unsupported generated claim was removed."
                            )
                    answer.claims = valid
                    sample = {
                        "user_input": reference["question"],
                        "reference": reference["reference"],
                        "response": response_text(answer),
                        "retrieved_contexts": contexts,
                    }
                    result = evaluate(
                        EvaluationDataset.from_list([sample]),
                        metrics=[
                            Faithfulness(llm=judge),
                            LLMContextPrecisionWithReference(
                                name="context_precision", llm=judge
                            ),
                            LLMContextRecall(llm=judge),
                        ],
                        llm=judge,
                        run_config=RunConfig(timeout=180, max_retries=1, max_workers=1),
                        raise_exceptions=True,
                        show_progress=False,
                    )
                scores = result.scores[0]
                row.update(
                    {metric: clean_score(scores.get(metric)) for metric in METRICS}
                )
                row.update(
                    response=sample["response"],
                    answer=answer.model_dump(),
                    retrieved=[
                        {k: h[k] for k in ("id", "chunk_id", "retrieval_backend")}
                        for h in hits
                    ],
                )
                row["status"] = (
                    "complete"
                    if all(row[m] is not None for m in METRICS)
                    else "invalid_metric"
                )
            except Exception:
                # Never serialize SDK exceptions, prompts with secrets or provider headers.
                row["error"] = (
                    "Generation, retrieval or RAGAS judging failed; provider details suppressed."
                )
            rows.append(row)
            save_report(report)
            print(f"{name}: {len(rows)}/{len(references)} {row['status']}", flush=True)
            if row["status"] == "failed":
                report.update(
                    status="incomplete",
                    reason="Provider execution failed; completed rows retained. Check private credentials, billing and model access. Rerun for a complete comparison.",
                )
                save_report(report)
                return 1
    complete = all(
        r["status"] == "complete" for rows in report["results"].values() for r in rows
    )
    report["status"] = (
        ("complete" if args.limit == 32 else "partial_sample")
        if complete
        else "incomplete"
    )
    save_report(report)
    return 0 if complete else 1


if __name__ == "__main__":
    raise SystemExit(main())
