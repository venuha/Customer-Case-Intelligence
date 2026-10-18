# RAGAS chunking and reranking comparison

**Status: complete.**

Four configurations use the same 32 development questions and independently authored reference answers. This experiment isolates retrieved context: top-six chunks, the same evidence-only LangChain prompt, the same OpenAI generation/judge models, and no deterministic case-reconciliation facts in the generation context. It does not benchmark the full application workflow or private uploads.

Faithfulness measures whether generated statements are supported by retrieved context; the evaluated response includes claims, unknowns and the suggested next step. Context precision is reference-guided, rank-weighted usefulness; context recall measures whether reference-answer claims are attributable to retrieved context. These are judge-based metrics, not exact-span retrieval scores.

| Configuration | Completed rows / expected | Faithfulness | Context precision | Context recall |
|---|---:|---:|---:|---:|
| fixed | 32 / 32 | 0.784 (n=32) | 0.849 (n=32) | 0.984 (n=32) |
| fixed_cross_encoder | 32 / 32 | 0.735 (n=32) | 0.884 (n=32) | 0.984 (n=32) |
| semantic | 32 / 32 | 0.676 (n=32) | 0.863 (n=32) | 0.953 (n=32) |
| semantic_cross_encoder | 32 / 32 | 0.592 (n=32) | 0.838 (n=32) | 0.969 (n=32) |

## Paired reranking impact

- fixed, faithfulness: -0.049 (n=32).
- fixed, context_precision: +0.034 (n=32).
- fixed, context_recall: +0.000 (n=32).
- semantic, faithfulness: -0.084 (n=32).
- semantic, context_precision: -0.026 (n=32).
- semantic, context_recall: +0.016 (n=32).

## Execution and limits

- Backend requested: pinecone. Pinecone runs refuse silent local fallback.
- No live-provider scores are asserted until successful generation and judging finish. Missing or invalid metric outputs are null, never zero.
- References are manually authored from synthetic records; the 32 questions are a development set, not a held-out or real-customer benchmark.
- RAGAS context metrics are LLM judgments and differ from exact-span recall/precision in evaluation-pdf.md.
- RAGAS 0.3.9; Faithfulness, LLMContextPrecisionWithReference and LLMContextRecall. No embedding-based judge metric is used.
- Same model is used across all configurations; generation and judging are separate calls. Shared model bias and small sample size limit conclusions.
- Tracing and RAGAS telemetry are disabled for this command. Only synthetic corpus passages are sent to OpenAI.
- See per-query results and provenance hashes in the JSON companion.
