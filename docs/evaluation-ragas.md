# RAGAS chunking and reranking comparison

**Status: not_run.**

Four configurations use the same 32 development questions and independently authored reference answers. This experiment isolates retrieved context: top-six chunks, the same evidence-only LangChain prompt, the same OpenAI generation/judge models, and no deterministic case-reconciliation facts in the generation context. It does not benchmark the full application workflow or private uploads.

| Configuration | Completed rows / expected | Faithfulness | Context precision | Context recall |
|---|---:|---:|---:|---:|
| fixed | 0 / 32 | Not measured | Not measured | Not measured |
| fixed_cross_encoder | 0 / 32 | Not measured | Not measured | Not measured |
| semantic | 0 / 32 | Not measured | Not measured | Not measured |
| semantic_cross_encoder | 0 / 32 | Not measured | Not measured | Not measured |

## Paired reranking impact

- fixed, faithfulness: Not measured.
- fixed, context_precision: Not measured.
- fixed, context_recall: Not measured.
- semantic, faithfulness: Not measured.
- semantic, context_precision: Not measured.
- semantic, context_recall: Not measured.

## Execution and limits

- Backend requested: pinecone. Pinecone runs refuse silent local fallback.
- No live-provider scores are asserted until successful generation and judging finish. Missing or invalid metric outputs are null, never zero.
- References are manually authored from synthetic records; the 32 questions are a development set, not a held-out or real-customer benchmark.
- RAGAS context metrics are LLM judgments and differ from exact-span recall/precision in evaluation-pdf.md.
- RAGAS 0.3.9; Faithfulness, LLMContextPrecisionWithReference and LLMContextRecall. No embedding-based judge metric is used.
- Same model is used across all configurations; generation and judging are separate calls. Shared model bias and small sample size limit conclusions.
- Tracing and RAGAS telemetry are disabled for this command. Only synthetic corpus passages are sent to OpenAI.
- Preflight passed. No live API calls requested.
