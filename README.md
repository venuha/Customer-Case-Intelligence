# Customer Case Intelligence
**Return & Refund Intelligence · One case. Every connection.**

A LangChain + LangGraph financial RAG application that connects a fictional customer's order, device return, merchant refund and bank review. FastAPI serves a custom web interface, scoped evidence search, source PDFs and draft investigation handoffs.

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
