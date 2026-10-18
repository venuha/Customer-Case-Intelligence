# Render Free + durable Supabase storage

The default `render.yaml` uses **Render Free**, with no paid disk or paid compute selection. Supabase Free stores accounts, revocable sessions, investigation history, PDF metadata and private PDF objects outside the disposable Render filesystem. Local development retains SQLite and local files when `DATABASE_URL` is absent. Hosted startup requires durable storage explicitly and refuses to run with missing settings.

## Supabase Free setup

Create a Free project. Save its database password privately. Disable automatic exposure of new tables. Create a **private** bucket named `cci-private-documents`, restricted to `application/pdf`, with a 10 MB file limit. Do not make it public or grant anonymous access.

The app creates a `cci_private` database schema and revokes schema access from `PUBLIC`, `anon`, and `authenticated`. It uses server-side Postgres connections, not browser-side database credentials. App authorization still checks the signed-in user's role, assigned case, and upload ownership. The bucket must be verified private at startup; a public bucket stops startup.

## Private Render settings

Create the Blueprint from this repository's `main` branch. Select only Free compute and do not add payment details. Configure these private environment values directly in Render:

- `DATABASE_URL`: Supabase **Transaction pooler** Postgres URI, obtained from Connect. Insert the saved password and percent-encode special characters in it. The app requires TLS and disables prepared statements for pooler compatibility.
- `SUPABASE_URL`: the project HTTPS URL.
- `SUPABASE_SERVICE_ROLE_KEY`: the legacy server-side `service_role` key, never the `anon`/publishable key. This key must never enter frontend code, reports, screenshots or GitHub.
- `PINECONE_API_KEY`: existing replacement key for the 384-dimensional cosine index `customer-case-intelligence`.
- `OPENAI_API_KEY`: existing replacement generation key. Users may alternatively connect a personal key after signing in.
- `CCI_BOOTSTRAP_PASSWORD`: a new unique 12–512 character administrator password, entered directly in Render.

Non-secret defaults, including `SUPABASE_STORAGE_BUCKET=cci-private-documents`, are in the Blueprint. The first launch creates username `owner`, role head, assigned the fictional cases. Passwords remain salted scrypt hashes in Postgres. Restarts preserve existing users and never reset passwords. New registrations remain pending until head approval. Local demo identities and private `.env` are excluded from the Docker image.

Once the first owner login succeeds, the bootstrap password setting can be removed. Render Free lacks a shell: for additional administration, run `scripts/manage_users.py` locally with the same private database configuration. Do not publish local credentials.

## Restart behavior and limits

Accounts, sessions, uploaded PDFs, extracted upload text and investigation history are durable in Supabase. Derived chunks, local dense vectors and model caches are rebuildable local files. The image prepares only the fictional/reference corpus caches at build time, without provider credentials. Private uploads remain excluded from Pinecone; their retrieved passages are sent to OpenAI only when AI answering is used.

Render Free sleeps after inactivity, so the first visitor can see a wake-up delay. Supabase Free can pause inactive projects; retain private backups and respect the provider's quotas. Free hosting does not provide an always-on production guarantee. The app limits each user to ten PDFs per case, each at most 10 MB, and the hosted demo to fifty stored PDFs globally. Removal deletes the object and its metadata; a provider failure during cross-service writes can require administrator cleanup of a private orphan. No automatic paid upgrade is configured.

One instance and one worker are required. Temporary personal OpenAI keys remain in process memory and are lost on restart; they are intentionally never saved. Secure cookies and proxy HTTPS handling are enabled. Model work uses single-item batches with CPU memory arenas disabled in low-memory mode, plus one concurrent assistant/chunk request. These settings preserve the selected model weights; performance must still be verified in the hosted environment. OpenAI/Pinecone API usage remains separate from free hosting.

## Verification before sharing

Check build and runtime logs, `/health`, unauthenticated API rejection, owner login, case/role restrictions, PDF upload/read/delete and a cited Pinecone-backed answer. Restart/redeploy the service and verify the same account and uploaded PDF still work. Confirm anonymous Supabase object access is denied. The public HTTPS app URL is assigned by Render; do not claim deployment before that address responds successfully.

With an authorized GitHub connection, automatic deployments can wait for checks. Public-repository URL deployments without that connection require manual redeployment. See the existing RAGAS reports for measured retrieval and generation quality; deployment changes do not imply a new evaluation run or production readiness.


## Live deployment verification — October 17, 2026

Public application: https://customer-case-intelligence.onrender.com/

The Free service was deployed from application commit `26c7bd3c887986bb2ea56ef21f7105e9eb9b5814`. Render reports the service as Free and Live; no payment details were supplied. Its image built successfully with all three fictional corpus caches. The deployment's GitHub checks passed and the local suite passed 74 tests.

Live checks passed for `/health`, unauthenticated case API rejection, secure/HttpOnly/Strict session cookies, assigned-case access, unassigned-case denial, an OpenAI-generated answer with actual Pinecone retrieval and cross-encoder reranking, and private PDF upload/download. A second user assigned to the same case could not read the first user's PDF. Render recorded a service restart; the existing account/session, exact PDF bytes and saved investigation remained accessible afterward. Disposable verification identities and documents were deleted. A separate-process Supabase persistence test and anonymous denial for an existing private PDF also passed.

This is a synthetic portfolio demonstration, not a production security certification, backup guarantee or new RAGAS benchmark. Provider free-tier limits, idle wake-up delays and project inactivity policies still apply. Personal OpenAI keys remain temporary by design.

## Shared timeline release

The application creates the additive `cci_private.communications` table on startup. Existing accounts, uploads, sessions and investigation history are preserved. Shared entries are restricted by case assignment and the highest permission of their attached canonical source; private uploads cannot become shared references. Handoffs use support-shareable sources and serialize per case to prevent competing pending owners. Acceptance references the active handoff; corrections reference a visible same-case entry. Team labels are employee-reported and external membership is not verified. No external notifications or tickets are dispatched.

CASE-1001 imports three dated fictional statements from its conversation source, using deterministic IDs so redeployment cannot duplicate them. Entries are append-only through public application APIs. The briefing uses up to 40 recent entries with an explicit truncation notice; the full case timeline remains available up to the demo's 500-entry cap. New summary context is role-filtered and request-scoped, and never synchronized to Pinecone. No new financial events are established by these communications.
