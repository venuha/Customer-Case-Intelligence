# Chunking comparison and cross-encoder impact

PDF corpus: same 32 primary queries; frozen source-ID evidence spans, whitespace normalized for PDF reflow.

## Controlled protocol

Explicit cl100k_base tokenizer. 350-token recursive baseline (40 overlap); semantic 70th-percentile adjacent embedding distance, same 350-token cap; BGE embeddings + BM25 RRF top-20 shortlist in every condition; return six chunks; no parent-document promotion during evaluation.

Trained reranker: `Xenova/ms-marco-MiniLM-L-6-v2` (FastEmbed ONNX). Scores below are measured.

| Configuration | Chunks | Evidence recall@6 | Evidence precision@6 | Evidence MRR@6 | Document recall@6 | Median ms |
|---|---:|---:|---:|---:|---:|---:|
| fixed | 274 | 0.875 | 0.172 | 0.683 | 0.938 | 204.9 |
| fixed_cross_encoder | 274 | 0.891 | 0.172 | 0.743 | 0.938 | 2041.2 |
| semantic | 989 | 0.828 | 0.151 | 0.593 | 0.922 | 202.4 |
| semantic_cross_encoder | 989 | 0.859 | 0.161 | 0.610 | 0.922 | 1285.2 |
| structure_cross_encoder | 342 | 0.844 | 0.161 | 0.716 | 0.938 | 2947.3 |

## Paired reranking impact

- fixed: evidence recall +1.56 percentage points; precision +0.00 points; MRR +0.060; median latency +1836.3 ms.
- semantic: evidence recall +3.12 percentage points; precision +1.04 points; MRR +0.017; median latency +1082.8 ms.

## Failure analysis

### fixed: 5 incomplete-evidence questions
- CASE-1008: Is the dispute credit provisional or a merchant refund? (evidence recall 0.00)
- CASE-1002: Was the money sent and is receipt visible to the customer? (evidence recall 0.00)
- CASE-1003: Connect the uninspected second device with the partial credit. (evidence recall 0.00)
- CASE-1004: Connect the outgoing refund and the incoming credit. (evidence recall 0.50)
- CASE-1008: Distinguish the merchant payment record from the temporary dispute adjustment. (evidence recall 0.50)
### fixed_cross_encoder: 6 incomplete-evidence questions
- CASE-1002: Was the money sent and is receipt visible to the customer? (evidence recall 0.00)
- CASE-1003: Connect the uninspected second device with the partial credit. (evidence recall 0.50)
- CASE-1004: Connect the outgoing refund and the incoming credit. (evidence recall 0.50)
- CASE-1006: Compare the purchased device identifier with the scanned return. (evidence recall 0.50)
- CASE-1007: Does internal approval mean the customer received a credit? (evidence recall 0.50)
- CASE-1008: Distinguish the merchant payment record from the temporary dispute adjustment. (evidence recall 0.50)
### semantic: 6 incomplete-evidence questions
- CASE-1002: Was the money sent and is receipt visible to the customer? (evidence recall 0.00)
- CASE-1003: Connect the uninspected second device with the partial credit. (evidence recall 0.00)
- CASE-1004: Connect the outgoing refund and the incoming credit. (evidence recall 0.00)
- CASE-1005: Does generating return paperwork establish that the carrier took possession? (evidence recall 0.00)
- CASE-1007: Does internal approval mean the customer received a credit? (evidence recall 0.50)
- CASE-1008: Distinguish the merchant payment record from the temporary dispute adjustment. (evidence recall 0.00)
### semantic_cross_encoder: 7 incomplete-evidence questions
- CASE-1002: Was the money sent and is receipt visible to the customer? (evidence recall 0.00)
- CASE-1003: Connect the uninspected second device with the partial credit. (evidence recall 0.50)
- CASE-1004: Connect the outgoing refund and the incoming credit. (evidence recall 0.00)
- CASE-1005: Does generating return paperwork establish that the carrier took possession? (evidence recall 0.50)
- CASE-1006: Compare the purchased device identifier with the scanned return. (evidence recall 0.50)
- CASE-1007: Does internal approval mean the customer received a credit? (evidence recall 0.50)
- CASE-1008: Distinguish the merchant payment record from the temporary dispute adjustment. (evidence recall 0.50)
### structure_cross_encoder: 6 incomplete-evidence questions
- CASE-1008: Is the dispute credit provisional or a merchant refund? (evidence recall 0.00)
- CASE-1002: Was the money sent and is receipt visible to the customer? (evidence recall 0.00)
- CASE-1003: Connect the uninspected second device with the partial credit. (evidence recall 0.50)
- CASE-1004: Connect the outgoing refund and the incoming credit. (evidence recall 0.00)
- CASE-1006: Compare the purchased device identifier with the scanned return. (evidence recall 0.50)
- CASE-1008: Distinguish the merchant payment record from the temporary dispute adjustment. (evidence recall 0.00)

## Limits

- Eight fictional cases; template-assisted synthetic text is not representative of real institutional data.
- The 32 questions are a development benchmark, not an independently held-out test.
- Evidence annotations identify selected sufficient passages; unannotated supporting paraphrases can be scored as irrelevant.
- This report uses passage-level top-six metrics; the prior short-corpus report used unique-document metrics and is not directly comparable.
- Cold model downloads, index building, and OpenAI generation are excluded from warm retrieval timings.

Faithfulness: Not measured without live generation and a judge. Exact evidence-span recall and quote existence are not faithfulness.

Per-query ranks, source IDs, chunk IDs, model scores, and corpus/query hashes are recorded in evaluation.json. No query or gold annotation is loaded by the application retriever.
