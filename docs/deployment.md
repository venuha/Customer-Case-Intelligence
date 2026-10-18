# Deploy Customer Case Intelligence on Render

The repository includes a Docker-based Render Blueprint (`render.yaml`). It creates one paid web service and a 5 GB persistent disk, with a public HTTPS `onrender.com` address. Confirm the current price in Render before deployment; API usage is billed separately by OpenAI/Pinecone.

## Private configuration

Create a Blueprint from `venuha/Customer-Case-Intelligence`, branch `main`. Render asks for three private environment values:

- `PINECONE_API_KEY`: the replacement infrastructure key for the existing 384-dimension cosine index `customer-case-intelligence`.
- `OPENAI_API_KEY`: the replacement server-side generation key. Users can optionally supply their own temporary OpenAI key after signing in.
- `CCI_BOOTSTRAP_PASSWORD`: a new unique administrator password, 12–512 characters. Enter it directly in Render, never in GitHub, chat, screenshots, or reports.

The first launch creates username `owner` with the head role and access to the fictional cases. It stores a salted scrypt hash, never the password, in the private identity database. Subsequent starts preserve the existing administrator and do not reset its password. After the first successful login, the bootstrap password environment value can be removed; recovery/account administration is available through `scripts/manage_users.py` in the service shell. A failed initial setup stops startup instead of exposing an unowned application.

Local `.env`, accounts, demo passwords, uploaded documents, and model caches are excluded from the Docker build. Local demonstration accounts are not copied to hosting. New registrations stay pending until an existing head approves their role and assigned cases.

## Persistence and scaling

The disk mounts at `/app/work`. SQLite identities, sessions, uploads and investigations use `/app/work/state`; extracted text, chunks and dense vectors use `/app/work/index`; embedding/reranking models use `/app/work/models`. Hugging Face and tokenizer caches also reside below the disk mount. Only that mount survives redeployment; the source corpus is immutable application data in the image.

Keep exactly one instance and one worker: SQLite and temporary personal keys currently depend on a single application process. Deployments with a disk can interrupt service briefly. Personal keys are intentionally in process memory and must be entered again after restarts; they never become persistent disk records. Horizontal scaling would require shared identity storage and a deliberate session/key design.

The container listens on Render's `PORT`. Secure cookies are enabled and forwarded HTTPS headers are trusted behind Render's managed ingress. `/health` is the platform health endpoint. It confirms the web process is available, not that every provider is healthy. First retrieval may take longer while the models download and chunk/vector caches are populated; later requests reuse the persistent caches.

## Release checks

With an authorized GitHub connection, Render waits for repository checks before automatic deployments. A deployment from a public repository URL without that connection needs manual redeployment; Render disables automatic deploys for that route. The runtime installs `requirements.lock`; evaluation-only dependencies are not included. Review build/runtime logs for a successful start, then verify the public login page, unauthenticated case API rejection, owner login, case/role restrictions, document upload and a cited answer. Confirm actual retrieval backend is Pinecone, with local fallback only on cloud failure. Never publish credentials or paste private environment values into logs for debugging.

Use only the provided fictional/reference corpus for the public demonstration. The application does not connect to live bank or telecom accounts, execute refunds, or prove production financial accuracy. The measured RAGAS and chunking comparison reports remain in `docs/` and `docs/pdf/`.
