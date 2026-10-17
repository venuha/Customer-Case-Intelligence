# Customer Case Intelligence — Return & Refund Intelligence

*One case. Every connection.*

## Assignment framework

My RAG app helps support and escalation specialists determine where a device return or refund stalled, using case documents and public reference guidance in an investigation workspace, with a target of 95% claim faithfulness and a warm-query latency target below 10 seconds. Targets are goals, not measured results.

| Field | Decision |
|---|---|
| Use case | Support and escalation specialists ask where a device return/refund stalled, what evidence supports the finding, and what is needed next, in a web investigation workspace. |
| Corpus | The English corpus contains 87 synthetic order, shipping, inspection, payment, statement, support and shared bank records across eight fictional cases, plus four attributed reference notes, stored as 91 PDFs. Source-of-truth ownership remains with each originating system; public guidance never proves an individual case event. |
| Ingestion + cleaning | Reproducibly authored PDFs are hash-verified and read page by page; running headers/footers and excess whitespace are removed while tables, identifiers, amounts, and dates are retained. Every chunk carries case, source, document ID, source type, and revision metadata. |
| Ingestion + freshness | Initial ingestion occurs at startup from the versioned local snapshot; changed files require a service restart and index rebuild. This demo has no live institutional integrations or live freshness SLA; public references are dated and must be reviewed before real operational use. |
| Chunking + embedding | The main path preserves document sections and table headers, targeting 350 tokens with a tokenizer-enforced cap for ordinary prose and table blocks, using local BAAI/bge-small-en-v1.5 embeddings; a fixed-size baseline uses the same corpus and embedding model. Embedding-distance semantic segmentation is compared separately in evaluation rather than treating section boundaries as semantic chunking. |
| Retrieve | A local persisted NumPy vector matrix plus BM25 forms a hybrid index; reciprocal rank fusion combines the top 20 candidates from each retriever, then a trained MiniLM cross-encoder reranks the fused top-20 shortlist and returns six passages. Case filtering is applied before ranking, and missing case evidence triggers abstention rather than borrowing another customer's records. |

## Scope and integrity
- All customer records, amounts, device IDs, timelines, and teams are fictional; no institution connection is implied.
- Refund approval, processor submission, bank posting, and provisional dispute credit remain distinct.
- No payments, external tickets, customer messages, or dispute decisions are executed.
- Escalation packets are downloadable drafts for human review.
- OpenAI answers require a server-side key. The no-key mode is evidence search/extraction, explicitly labeled.
- Server-enforced role and case permissions are implemented. Production still needs SSO, organization tenancy, audit retention, approved connectors and institution-specific policy review.
