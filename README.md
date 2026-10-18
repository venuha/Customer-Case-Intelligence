# Customer Case Intelligence
**Return & Refund Intelligence · One case. Every connection.**

A LangChain + LangGraph financial RAG application that connects a fictional customer's order, device return, merchant refund and bank review. FastAPI serves a custom web interface, scoped evidence search, source PDFs and draft investigation handoffs.

## Live application

[Open Customer Case Intelligence](https://customer-case-intelligence.onrender.com/)

The public app requires sign-in; new account requests need administrator approval and explicit case assignments. Render Free can take 50 seconds or longer to wake after inactivity. Accounts, private PDFs and saved investigations persist in Supabase across app restarts.

## Quick start
Python 3.12 recommended. Create a virtual environment, then:

```sh
pip install -r requirements.txt
cp .env.example .env
python scripts/manage_users.py demo
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Generated demo passwords are stored privately in `work/demo-access.json` (file mode 600). Open that local file to sign in; do not upload it. There are no published default passwords. The service account sees four assigned cases; supervisor and head accounts see all eight with different document permissions. For individual accounts use `python scripts/manage_users.py create --username NAME --role customer_service --cases CASE-1001` and enter a password at the prompt.

Optionally set `OPENAI_API_KEY` in the private `.env`; otherwise answers are clearly labeled retrieved excerpts. First startup downloads local embedding and reranker models and builds the PDF index. Use HTTPS and `COOKIE_SECURE=true` for hosted sessions; create users in the deployed runtime with persistent private storage. Docker and render.yaml are starting configurations, not evidence of a completed deployment.

## Repository map
- `app/api/`: authenticated HTTP routes and application lifecycle.
- `app/rag/`: LangChain loaders, hybrid retrieval, chunkers, trained cross-encoder and LangGraph workflow.
- `app/domain/`: deterministic case and integer-cent refund reconciliation.
- `app/security/`: role/case policy, password hashing and session management.
- `app/documents/`: PDF ingestion and page/table provenance.
- `app/integrations/`: optional read-only bank sandbox adapter.
- `app/data/`: reproducible synthetic record authoring.
- `app/static/`: custom web interface, styling and sign-in.
- `data/corpus/`: 91 source PDFs and hash/role manifest.
- `data/eval/`: benchmark annotations kept outside searchable evidence.
- `docs/`: experiment reports and architecture/access guide; `docs/pdf/` contains its PDF companion.
- `scripts/`: local user administration, PDF generation, evaluations, safe packaging and publication scanning.
- `tests/`: case isolation, source grounding, financial state and access-control checks.

Read [the architecture and access guide](docs/architecture-and-access.md) for chunking, exact storage locations, role permissions, integration boundaries and evaluation limitations. The PDF companion is [here](docs/pdf/architecture-and-access.pdf).

## Rebuild source PDFs
```sh
python -m app.data.seed
python scripts/build_bank_fixtures.py
python scripts/build_pdf_corpus.py
```

All case records and bank acknowledgements are synthetic. Four public notes are attributed paraphrases, not official provider documents. PDF manifest hashes are verified before indexing. Source JSON remains the reproducible structured facts layer; actual RAG narrative comes from PDF extraction. Code remains Python/JavaScript; GitHub documentation remains editable Markdown with a PDF architecture companion.

## Validation and project deliverables
```sh
pip install -r requirements-dev.txt
pytest -q
python scripts/evaluate.py
python scripts/evaluate_tables.py
python scripts/package_submission.py
```

The application defaults to fixed-size hybrid retrieval; users can opt into cross-encoder reranking per question. The current PDF-corpus results are in `docs/evaluation-pdf.md` and `.json`. Fixed recall@6 improved from 87.5% to 89.1% with reranking, and semantic recall improved from 82.8% to 85.9%. All eight financial-table probes passed in each tested configuration. Earlier `docs/evaluation-expanded.*` results are historical. The project compares fixed versus semantic chunking on identical questions and measures trained cross-encoder impact; improvements are reported honestly, including regressions. A new recording and hosting deployment are still required for final submission. No real bank connection is claimed.

## Security and publication
Never commit `.env`, `work/`, local indexes, model caches, private identities/sessions, customer data or real provider responses. Run `python scripts/scan_publication.py` before publishing. Reports contain architecture and aggregate evaluation results, never keys. No external payment, dispute, ticket or customer message is executed. This prototype requires further production security and provider integration work before real customer use.

## New account requests
Choose **New here? Request an account** on the sign-in page. Registration stores a salted password hash and creates a pending account with no cases or session; existing usernames receive the same generic acknowledgement and their passwords are never replaced.

A signed-in **head** can open **Account requests**, choose customer service or supervisor access, select permitted cases, and approve. The server prevents assigning cases outside the approver's own access. Head access can only be granted through local administration.

An administrator on the application host can also review and approve requests with explicit permissions:

```sh
python scripts/manage_users.py pending
python scripts/manage_users.py approve --username NAME --role customer_service --cases CASE-1001
```

The user can then sign in with the password they chose. Approval does not send email; this prototype uses local administrator review. Only an authenticated head or the host administrator can approve operational access. New users cannot select supervisor/head access or grant themselves cases.

## Personal AI keys and private PDFs
Open a case and select **Case assistant** or **Ask this case**. **Connect your OpenAI key** retains a personal key only in process memory, scoped to the current login session and its original expiry. Sign-out/removal clears it; restart loses it. No key is returned to the browser or included in graph state, history, indexes, reports or Git. Hosted key entry requires HTTPS. This is a single-process prototype: multiple workers need a dedicated session-secret service. The first AI request validates provider access and may incur charges; live generation evaluation status is recorded in `docs/evaluation-ragas.md`.

The **Evidence** tab accepts private text-based PDFs (10 MB, 50 pages, 200,000 extracted characters, ten files per user per case). Uploading and chunk inspection use local models and require no OpenAI key. Choose fixed, semantic or table-aware splitting in **Inspect chunks**. Private uploads are owner-scoped even when colleagues have the same case assignment. They supplement retrieval and do not change verified refund balances. With AI enabled, retrieved excerpts are sent to OpenAI under the connected key; review sensitive content before asking.

Private originals and extracted records are stored beneath ignored `work/uploads/`; derived chunks and embeddings remain in ignored `data/index/`. Removing a private upload purges indexes containing its source ID and the owner's saved answers citing it. Backups, retention policy, malware scanning, OCR for image-only PDFs, full multi-turn conversation memory, provider usage accounting and live institution integrations remain production work. Existing benchmark scores describe the fixed fictional corpus, not arbitrary user uploads.


## Pinecone with local fallback
The dense search backend can use Pinecone Serverless while BM25 remains local. Use an index with **384 dimensions, cosine metric, and external vectors** to match BGE-small; the reference kit's 768-dimensional index is incompatible with this model. Index creation is an administrator action in the Pinecone console. Runtime requests never create or delete cloud indexes.

For secure local setup, run `.venv/bin/python scripts/configure_providers.py` in your own terminal. It prompts for keys without echoing them and saves them in the ignored, permission-600 `.env`. Alternatively edit that file privately: set `PINECONE_API_KEY`, `PINECONE_INDEX_NAME`, and `VECTOR_BACKEND=pinecone`. Never enter the infrastructure key in the personal OpenAI dialog, a GitHub file, report, screenshot or chat. In hosting, use the host's server-side secret environment settings.

Run `.venv/bin/python scripts/sync_pinecone.py` to explicitly synchronize the fictional PDF corpus. Each strategy uses a separate immutable-content namespace (`cci-fixed-<fingerprint>`, `cci-semantic-<fingerprint>`, `cci-structure-<fingerprint>`). Vectors plus chunk text, source/page, case scope and role level are stored in Pinecone. Full PDFs and authoritative chunk metadata stay local. Upserts use deterministic IDs, so retrying cannot create duplicates; old corpus namespaces are retained and must be removed explicitly by an administrator when no longer needed.

Search applies case and role metadata filters in Pinecone and validates returned IDs against the local permitted set. An unavailable provider, invalid index dimensions, incomplete namespace or failed scope validation uses the local dense index. Query results record `retrieval_backend` (`pinecone`, `local-fallback`, or `local`). Private PDF workspaces always use local retrieval, including canonical evidence for that workspace; they are never synchronized by the cloud upload command. Pinecone stores only the fixed fictional/reference corpus in this implementation.

## RAGAS comparison
Install optional evaluation dependencies with `.venv/bin/pip install -r requirements-eval.txt`. An exact snapshot of the tested environment is in `requirements-eval.lock`. This is separate from the app runtime because RAGAS adds dataset/judge dependencies.

Configure `OPENAI_API_KEY` privately through the setup command above, then run:

```sh
.venv/bin/python scripts/evaluate_ragas.py --preflight
.venv/bin/python scripts/evaluate_ragas.py --backend local
# After successful cloud synchronization, compare using Pinecone instead:
.venv/bin/python scripts/evaluate_ragas.py --backend pinecone
```

The full run makes generation and judge calls for 32 questions across four paired configurations and incurs OpenAI usage charges. `--limit 2` is an explicitly partial smoke run. Pinecone evaluations fail if the cloud is unavailable; they cannot silently report local results. Reports are saved incrementally to `docs/evaluation-ragas.json` and `.md`. Back up those reports before running a different backend if retaining both comparisons. No provider scores are invented when keys are absent, calls fail, or metrics return NaN.

The controlled experiment uses retrieved context only, without the application's additional deterministic reconciliation. It evaluates Faithfulness, LLMContextPrecisionWithReference and LLMContextRecall with frozen manually authored answers in `data/eval/references.json`. These judge scores differ from exact-span retrieval metrics. Telemetry/tracing is disabled in this evaluation command. The combined submission report is `docs/comparison-report.md` with a PDF companion in `docs/pdf/comparison-report.pdf`; its status explicitly distinguishes measured retrieval results from pending live RAGAS results.


## Live Pinecone verification and evaluation checkpoints
The serverless 384-dimension cosine index has been synchronized with 274 fixed, 989 semantic and 342 table-aware vectors. `docs/pinecone-validation.json` records 24 live case/role scope checks and an explicitly simulated provider outage that exercised local fallback. Reproduce these checks with `.venv/bin/python scripts/validate_pinecone.py`. Only synthetic/reference corpus chunks were uploaded.

Retrieval-only benchmarking can target Pinecone without OpenAI generation: `.venv/bin/python scripts/evaluate.py --backend pinecone --output-prefix evaluation-pinecone`. The report records the requested backend and each hit's actual backend. RAGAS generation and judging remain separate and their completion is recorded in `docs/evaluation-ragas.md`.

The RAGAS runner supports `--workers 1..4` (default four concurrent questions, with dedicated asynchronous judge clients closed on their own event loops) and `--resume`. Resume validates corpus/reference/prompt hashes, model names, sample size, backend and RAGAS version before reusing completed rows. If OpenAI returns `insufficient_quota`, resolve API billing/project quota before resuming; repeated retries do not resolve a billing limit. Example: `.venv/bin/python scripts/evaluate_ragas.py --backend pinecone --resume`.


## Completed live RAGAS experiment
The full Pinecone-backed run completed all **128 question/configuration rows** (32 questions, four configurations) using OpenAI `gpt-4.1-mini` for separate generation and RAGAS judging calls. All three metrics are valid in every row, and every retrieved hit records Pinecone as its backend. See `docs/evaluation-ragas.md` and `.json` for the measured values, paired reranking deltas, generated responses, source/chunk IDs and provenance hashes.

The findings are mixed: reranking improved fixed-chunk context precision and semantic context recall, while answer faithfulness declined in both paired comparisons. The app keeps fixed-size hybrid retrieval as its default and exposes deeper reranking as an option. This synthetic development benchmark does not establish production accuracy; the combined PDF report explains the limits and flags low-faithfulness examples for review.

## Hosted deployment

The Render Free Blueprint uses Supabase for durable accounts and private PDFs, with a private first administrator and a public HTTPS application URL. Follow [the deployment guide](docs/deployment.md) for server-side secrets, first login, storage paths and the single-process limitation. Local accounts and private `.env` files are excluded from the Docker image. Choose only the Free plans; no payment details are required for this setup. Free services can sleep or pause.

## Shared communication timeline

Each case now includes a Shared timeline for customer contacts, promises/deadlines, progress updates, corrections and team handoffs. Author identity and recording time come from the server; source permissions control who can read an entry. A requested handoff remains pending until explicitly acknowledged. The case overview shows suggested or acknowledged ownership separately. Team labels are employee-reported internal app labels, not verified membership in external organizations.

The “Brief me on this case” action combines the permitted case milestones with up to the latest 40 shared entries. Citations open the underlying communication or PDF. Extractive milestone coverage supplements the generated summary so purchases and returns are not lost to a similarity-only top-k selection. Financial balances remain determined by verified source facts, never by a promise or support statement. Private PDF uploads cannot be attached as shared references.

History is append-only through the API; corrections retain the original entry. Three explicitly fictional dated statements from CASE-1001's supplied conversation PDF are imported idempotently, with unknown employee identity/contact time disclosed. This does not fabricate the other contacts counted in the case header. Calls, emails, external tickets and bank systems are not captured automatically; staff must record communications in the application. Shared entries are persistent Postgres records on hosting and never uploaded to Pinecone. Existing retrieval/RAGAS reports remain the original fixed-corpus benchmark; they do not measure this new dynamic briefing feature.

### Demo team directory and individual handoffs

Open **Shared timeline → Team directory** to see eight explicitly fictional contacts, including warehouse intake coordinator Alex Morgan and reconciliation lead Sam Rivera. Reserved `.example` addresses are display-only; these personas are not login accounts, verified employees, or live notification destinations.

Ask **“Who is the warehouse person to connect with?”** The assistant cites the case-scoped demo directory and offers **Review handoff**. Review the receiving team, individual and next action, then save the internal handoff. The requested individual remains pending until an authorized user records internal acknowledgement; the signed-in author is preserved separately from the demo assignee. This does not verify external employee acceptance. Existing team-only history remains readable.

Directory suggestions do not establish warehouse receipt, payment submission or refund posting. Missing-evidence answers use qualified wording (“not evidenced in the available records”), rather than claiming an event never happened. Original quoted excerpts remain unchanged. The financial state still comes only from the original source facts. This new workflow is covered by regression and hosted checks; the fixed-corpus RAGAS comparison is not a benchmark of this directory feature.

### Return-to-refund simulation lab

Open a case and select **Simulation lab → Start fictional return journey**. Each signed-in user gets an isolated, persistent training scenario with a fixed fictional $1,099 order and device; this is not the selected case’s verified financial position. Three initial events establish purchase, return authorization and carrier delivery. Step through warehouse receipt → device verification → refund approval → processor submission → bank acknowledgement → refund posted.

Optional device-mismatch and bank-information-request branches block later steps until resolved. Events keep their original history, signed-in author and timestamps. **Explain this simulation with citations** produces a deterministic, rule-based event brief; it is labeled separately from OpenAI answers. Citations open the private simulation record. Completed runs can be replayed by creating a new run, preserving previous evidence.

The simulator contains no banking credentials, external bank/warehouse calls, payment processing, email, or external tickets. All people, identifiers, trace references, and money states are fictional. Original case evidence, financial balances, shared communications, retrieval indexes, and RAGAS comparison results remain unchanged. There is no automatic execution by the case assistant. Server-side case assignment, run ownership, ordered transitions, revision checks and per-run locking protect against cross-user access, skipped steps and duplicate clicks. Limits: 20 runs per user/case, 100 events per run. Postgres stores hosted simulations; SQLite is used locally. No Plaid integration is used by this lab.
