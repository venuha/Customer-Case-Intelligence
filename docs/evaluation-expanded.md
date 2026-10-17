> Historical pre-PDF-migration record. See evaluation-pdf.md for the revised corpus experiment when available.

# Chunking comparison and cross-encoder impact

Same 32 primary queries; frozen source-ID and exact evidence-span annotations.

## Controlled protocol

350-token recursive baseline (40 overlap); semantic 70th-percentile adjacent embedding distance, same 350-token cap; BGE embeddings + BM25 RRF top-20 shortlist in every condition; return six chunks; no parent-document promotion during evaluation.

Trained reranker: `Xenova/ms-marco-MiniLM-L-6-v2` (FastEmbed ONNX). Scores below are measured.

| Configuration | Chunks | Evidence recall@6 | Evidence precision@6 | Evidence MRR@6 | Document recall@6 | Median ms |
|---|---:|---:|---:|---:|---:|---:|
| fixed | 256 | 0.906 | 0.182 | 0.774 | 0.938 | 41.8 |
| fixed_cross_encoder | 256 | 0.891 | 0.172 | 0.713 | 0.922 | 7864.7 |
| semantic | 814 | 0.844 | 0.156 | 0.695 | 0.906 | 21.0 |
| semantic_cross_encoder | 814 | 0.859 | 0.161 | 0.691 | 0.906 | 3298.9 |
| structure_cross_encoder | 307 | 0.891 | 0.172 | 0.687 | 0.938 | 4276.6 |

## Paired reranking impact

- fixed: evidence recall -1.56 percentage points; precision -1.04 points; MRR -0.061; median latency +7822.9 ms.
- semantic: evidence recall +1.56 percentage points; precision +0.52 points; MRR -0.004; median latency +3277.9 ms.

## Failure analysis

### fixed: 4 incomplete-evidence questions
- CASE-1005: Which device was ordered? (evidence recall 0.00)
- CASE-1002: Was the money sent and is receipt visible to the customer? (evidence recall 0.50)
- CASE-1003: Connect the uninspected second device with the partial credit. (evidence recall 0.00)
- CASE-1008: Distinguish the merchant payment record from the temporary dispute adjustment. (evidence recall 0.50)
### fixed_cross_encoder: 6 incomplete-evidence questions
- CASE-1002: Was the money sent and is receipt visible to the customer? (evidence recall 0.00)
- CASE-1003: Connect the uninspected second device with the partial credit. (evidence recall 0.50)
- CASE-1004: Connect the outgoing refund and the incoming credit. (evidence recall 0.50)
- CASE-1006: Compare the purchased device identifier with the scanned return. (evidence recall 0.50)
- CASE-1007: Does internal approval mean the customer received a credit? (evidence recall 0.50)
- CASE-1008: Distinguish the merchant payment record from the temporary dispute adjustment. (evidence recall 0.50)
### semantic: 7 incomplete-evidence questions
- CASE-1001: Compare the agent completion claim with the customer-provided statement. (evidence recall 0.50)
- CASE-1002: Was the money sent and is receipt visible to the customer? (evidence recall 0.00)
- CASE-1003: Connect the uninspected second device with the partial credit. (evidence recall 0.00)
- CASE-1004: Connect the outgoing refund and the incoming credit. (evidence recall 0.50)
- CASE-1005: Does generating return paperwork establish that the carrier took possession? (evidence recall 0.00)
- CASE-1007: Does internal approval mean the customer received a credit? (evidence recall 0.50)
- CASE-1008: Distinguish the merchant payment record from the temporary dispute adjustment. (evidence recall 0.50)
### semantic_cross_encoder: 7 incomplete-evidence questions
- CASE-1002: Was the money sent and is receipt visible to the customer? (evidence recall 0.00)
- CASE-1003: Connect the uninspected second device with the partial credit. (evidence recall 0.50)
- CASE-1004: Connect the outgoing refund and the incoming credit. (evidence recall 0.00)
- CASE-1005: Does generating return paperwork establish that the carrier took possession? (evidence recall 0.50)
- CASE-1006: Compare the purchased device identifier with the scanned return. (evidence recall 0.50)
- CASE-1007: Does internal approval mean the customer received a credit? (evidence recall 0.50)
- CASE-1008: Distinguish the merchant payment record from the temporary dispute adjustment. (evidence recall 0.50)
### structure_cross_encoder: 5 incomplete-evidence questions
- CASE-1002: Was the money sent and is receipt visible to the customer? (evidence recall 0.00)
- CASE-1003: Connect the uninspected second device with the partial credit. (evidence recall 0.50)
- CASE-1004: Connect the outgoing refund and the incoming credit. (evidence recall 0.00)
- CASE-1006: Compare the purchased device identifier with the scanned return. (evidence recall 0.50)
- CASE-1008: Distinguish the merchant payment record from the temporary dispute adjustment. (evidence recall 0.50)

## Limits

- Eight fictional cases; template-assisted synthetic text is not representative of real institutional data.
- The 32 questions are a development benchmark, not an independently held-out test.
- Evidence annotations identify selected sufficient passages; unannotated supporting paraphrases can be scored as irrelevant.
- This report uses passage-level top-six metrics; the prior short-corpus report used unique-document metrics and is not directly comparable.
- Cold model downloads, index building, and OpenAI generation are excluded from warm retrieval timings.

Faithfulness: Not measured without live generation and a judge. Exact evidence-span recall and quote existence are not faithfulness.

Per-query ranks, source IDs, chunk IDs, model scores, and corpus/query hashes are recorded in evaluation.json. No query or gold annotation is loaded by the application retriever.

## Interpretation

Fixed-size hybrid retrieval had the highest evidence recall in this development benchmark. The trained cross-encoder slightly improved semantic evidence recall but reduced MRR and added latency; it did not improve fixed-size retrieval. Source provenance fixed the separate table-source confusion probe. No universal winner or production-quality claim is made.

Timings were measured under concurrent local workload, including earlier jobs the environment could not terminate; they are indicative, not an isolated performance benchmark.

The source-aware table-aware cross-encoder retrieved both required rows from the designated order document on all eight supplemental probes; this is a development regression result, not held-out accuracy. See table-evaluation.md and the archived initial results under iterations/.
