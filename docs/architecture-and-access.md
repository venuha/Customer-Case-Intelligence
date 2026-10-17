# Customer Case Intelligence
Return & Refund Intelligence. One case. Every connection.

## Scope and source of truth
A specialist asks where a device return or refund stopped, what the bank has acknowledged, and which team needs which evidence. This is a fictional case investigation application, not a live telecom or bank system.

The corpus contains 87 synthetic source records across eight cases plus four attributed public reference notes, distributed as 91 PDFs. Public PDFs are authored paraphrases with original links; they are not official bank records or copies of bank contracts. All customers, identifiers, amounts, statuses, conversations and bank acknowledgements are fictional. Source facts in data/documents.json drive deterministic case reconciliation; the searchable narrative is extracted from the PDF corpus.

## Ingestion, cleaning and freshness
The reproducible authoring records become PDFs under data/corpus; manifest.json records source identity, role, path and SHA-256. The loader verifies hashes, extracts page text, removes running headers and footers, normalizes whitespace, and reconstructs tables with headers before chunking. This demonstration is a versioned October 17, 2026 snapshot; ingestion runs on rebuild, with no scheduled refresh or live freshness SLA. Production requires provider-specific events, source timestamps, deletion handling and a negotiated freshness SLA.

## Chunking and embedding
Fixed chunking uses LangChain recursive token splitting with a 350-token limit and 40-token overlap. Semantic chunking embeds adjacent sentences/paragraphs, splits at cosine-distance boundaries above the 70th percentile, and enforces the same token cap; the table-aware application strategy groups sections and repeats table headers when splitting rows. Each chunk includes source ID, case ID, role, PDF page, source hash, strategy and chunk ID. BGE small English v1.5 produces 384-dimensional embeddings; this local English model and short chunks are a measurable project baseline, not a claim of universal optimality.

## Retrieval, reranking and storage
Authorized case and document-role filtering happens before dense or keyword ranking. BM25 and dense vectors each contribute their top 20 candidates to reciprocal rank fusion; a shared top-20 pool is optionally reranked with the trained MiniLM cross-encoder. The app defaults to fixed-size hybrid retrieval, with an explicit per-question cross-encoder option because reranking improves aggregate recall here but adds substantial latency. The app requests ten passages, groups them into at most six sources, and grounds responses on those excerpts. Cached chunk text and metadata live in ignored data/index/*.chunks.json; embedding vectors live in data/index/*.npy and are normalized in memory for cosine similarity. BM25 is built in memory over authorized candidates. PDF extraction caches live in ignored data/index/extracted/; model downloads live under ignored work/. PDFs and the provenance manifest are versioned; local indexes, identities, sessions, histories and keys are not published.

## Stateful investigation and refusal
LangGraph enforces scope, retrieval, deterministic financial reconciliation, generation and citation verification. Foreign case identifiers, unknown identifiers, absent supporting evidence, unavailable providers and invalid exact quotes have explicit refusal or fallback paths. OpenAI is optional and reads its key from the private environment; without it the app returns labeled excerpts. Citation checks validate exact quotes, not the semantic truth of every generated interpretation.

## Access control
Users are authenticated with scrypt password hashes and opaque, hashed, revocable eight-hour server sessions. Passwords are created locally with the administration script, not committed or placed in reports. Every role also needs explicit case assignments; head access is organization-scoped through those assignments.

| Role | Permitted source classes | Restricted examples |
| --- | --- | --- |
| Customer service | Order, return, shipping, conversation, approved shared bank summary | Payment, approval, processor record, private statement |
| Supervisor | Service sources plus payment, routing, inspection, approval, refund | Private statements and account history |
| Head of operations | All assigned case sources | Other unassigned cases |

APIs, retrieval, PDF downloads, handoff exports and saved runs enforce server-side access. Saved runs are isolated by username and current role. UI role labels do not grant permissions. Lower roles reconcile only their visible sources, so missing restricted evidence must not be presented as a universal negative. Customer service finance detail is explicitly restricted. Production still needs federated identity, organization tenancy, audit retention, encrypted storage, backup and security assessment.

## Connected return and bank lifecycle
The order, return authorization, shipment, warehouse inspection, refund approval, processor submission, bank acknowledgement and statement have distinct sources. Shared bank summaries connect the case/order/bank-case identifiers, state, required information and next responsible team. Merchant submission does not prove bank receipt; bank receipt does not prove posting; provisional dispute credit is separate from final merchant credit. Missing bank information remains unknown. Suggested ownership is a human-review draft, not an external assignment.

## Optional bank integration
app/integrations/banking.py provides an optional read-only Plaid sandbox transaction-sync adapter with pagination and sanitized failures. It is not wired to live customer accounts or automatically used to adjudicate refunds. It requires private sandbox credentials and access tokens. No refunds, disputes, bank transfers, customer messages or external tickets are executed. Transaction feeds alone do not prove universal bank acceptance; explicit provider references, account authorization and review are required. A documentation MCP can assist developers but cannot bypass bank consent or account access.

Official integration references: https://plaid.com/docs/api/products/transactions/ and https://plaid.com/docs/api/sandbox/ . TrueLayer's refund-return documentation illustrates that provider events may change and need verified signatures: https://docs.truelayer.com/docs/payout-and-refund-returns and https://docs.truelayer.com/docs/payments-api-webhook-reference .

## Evaluation results for the PDF corpus
The final comparison uses the same 32 development questions on 91 PDFs (202 extracted pages), with frozen source-ID evidence spans and whitespace normalization for PDF reflow. The tokenizer is explicitly cl100k_base in every configuration. Fixed-size hybrid retrieval achieved 87.5% evidence recall@6, increasing to 89.1% with cross-encoder reranking; semantic retrieval achieved 82.8%, increasing to 85.9%. Fixed reranking improved recall by 1.5625 percentage points and MRR by 0.060; semantic reranking improved recall by 3.125 points and MRR by 0.017. The table-aware configuration with reranking scored 84.4% on the primary benchmark. All eight supplemental financial-table questions achieved full evidence recall in all four tested table configurations.

Chunk counts were 274 fixed, 989 semantic and 342 table-aware. Warm median retrieval latency was approximately 35-37 ms without reranking, 7.86 seconds for fixed reranking, 2.52 seconds for semantic reranking and 5.14 seconds for table-aware reranking. These timings include concurrent local workload and are not isolated production benchmarks. The app defaults to the fast fixed-size baseline and lets users request deeper reranking per question; that choice exchanges latency for the measured aggregate recall improvement.

Every condition used the same questions, BGE embeddings, top-20 fusion pool and six returned passages. The report records per-query ranks, source IDs and corpus/query hashes. Earlier evaluation-expanded reports are historical pre-PDF results; preliminary PDF measurements before tokenizer correction are superseded. OpenAI generation faithfulness remains unmeasured without credentials. Synthetic templates and a small development question set limit generalization.
