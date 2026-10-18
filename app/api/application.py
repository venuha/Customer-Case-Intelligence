import json
import os
import threading
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal
from uuid import uuid4

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field
from starlette.concurrency import run_in_threadpool

from app.storage.database import connect, private_local_file

from ..config import runtime_dir
from ..documents import uploads
from ..domain import communications, directory, simulation
from ..domain.investigation import investigate, money
from ..rag.capacity import bounded_inference
from ..rag.case_context import ContextIndex
from ..rag.graph import build_graph
from ..rag.retrieval import RERANK_MODEL, CorpusLoader, HybridIndex, chunks_for
from ..security import provider_keys
from ..security.auth import (
    SESSION_COOKIE,
    SESSION_TTL,
    approve_user,
    authenticate,
    initialize,
    new_session,
    pending_users,
    request_account,
    require_user,
    revoke,
)
from ..security.policy import project_investigation, visible_documents

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")
state = {}
limits = defaultdict(deque)
guard = threading.Lock()


@asynccontextmanager
async def lifespan(app):
    initialize()
    communications.initialize()
    simulation.initialize()
    communications.seed_history()
    data = ROOT / os.getenv("DATA_DIR", "data")
    cases = json.loads((data / "cases.json").read_text())
    docs = json.loads((data / "documents.json").read_text())
    public = json.loads((data / "public" / "references.json").read_text())
    from ..documents.loader import load_pdf_documents

    extracted = {}
    for page in load_pdf_documents():
        extracted.setdefault(page.metadata["id"], []).append(page.page_content)
    docs = [{**d, "text": "\n\n".join(extracted.get(d["id"], []))} for d in docs]
    state.update(cases={c["id"]: c for c in cases}, documents=docs, public=public)
    state["index"] = HybridIndex(strategy="fixed")
    state["graph"] = build_graph(state["index"], state["cases"], docs)
    work = runtime_dir()
    work.mkdir(exist_ok=True)
    state["db"] = work / "audit.sqlite"
    with connect(state["db"]) as db:
        db.execute(
            "CREATE TABLE IF NOT EXISTS runs (id TEXT PRIMARY KEY, case_id TEXT, created REAL, payload TEXT)"
        )
    private_local_file(state["db"])
    from ..storage.database import remote

    if remote():
        from ..storage.uploads import initialize as initialize_uploads

        initialize_uploads()
    yield


app = FastAPI(
    title="Customer Case Intelligence · Return & Refund Intelligence",
    description="One case. Every connection.",
    lifespan=lifespan,
    docs_url=None,
    openapi_url=None,
    redoc_url=None,
)


import psycopg
from fastapi.exceptions import RequestValidationError

from ..storage.errors import StorageUnavailable


@app.exception_handler(StorageUnavailable)
@app.exception_handler(psycopg.Error)
def storage_error(request: Request, error):
    return JSONResponse(
        {"detail": "Saved data is temporarily unavailable. Please try again."},
        status_code=503,
    )


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, error):
    if request.url.path == "/api/provider-key":
        return JSONResponse({"detail": "Enter a valid API key."}, status_code=422)
    return JSONResponse({"detail": "Please check the request fields."}, status_code=422)


@app.middleware("http")
async def security(request: Request, call_next):
    if request.method in ("POST", "DELETE"):
        host = request.headers.get("host", "")
        origin = request.headers.get("origin")
        if origin and origin not in ("http://" + host, "https://" + host):
            return JSONResponse(
                {"detail": "Cross-origin requests are not accepted."}, status_code=403
            )
        key = request.client.host if request.client else "unknown"
        with guard:
            queue = limits[key]
            now = time.monotonic()
            while queue and now - queue[0] > 60:
                queue.popleft()
            if len(queue) >= 20:
                return JSONResponse(
                    {"detail": "Please wait before starting another investigation."},
                    status_code=429,
                )
            queue.append(now)
    response = await call_next(request)
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    elif request.url.path == "/" or request.url.path.endswith((".js", ".css")):
        response.headers["Cache-Control"] = "no-cache"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
    )
    return response


def get_case(cid):
    if cid not in state["cases"]:
        raise HTTPException(404, "Case not found")
    return state["cases"][cid]


def case_docs(cid):
    return [d for d in state["documents"] if d["case_id"] == cid]


def authorize(cid, user):
    get_case(cid)
    if not user.can_access_case(cid):
        raise HTTPException(404, "Case not found")


def detail(cid, user):
    authorize(cid, user)
    case = get_case(cid)
    entries = communications.visible(user, cid)
    docs = (
        visible_documents(user, state["documents"], cid)
        + uploads.records(user, cid)
        + [communications.document(e) for e in entries]
    )
    investigation = project_investigation(user, investigate(case, docs))
    ownership = communications.ownership(entries, investigation["owner"])
    docs.append(directory.document(cid, ownership))
    return {
        **case,
        "investigation": investigation,
        "documents": docs,
        "team_ownership": ownership,
    }


class SimulationStep(BaseModel):
    model_config = ConfigDict(extra="forbid")
    revision: int = Field(ge=0)
    action: Literal[
        "received",
        "verified",
        "device_mismatch",
        "approved",
        "submitted",
        "bank_info_required",
        "bank_received",
        "posted",
    ]


@app.get("/api/cases/{cid}/simulation")
def simulation_latest(cid: str, user=Depends(require_user)):
    authorize(cid, user)
    return {"notice": simulation.NOTICE, "run": simulation.latest(user, cid)}


@app.post("/api/cases/{cid}/simulation")
def simulation_create(cid: str, user=Depends(require_user)):
    authorize(cid, user)
    try:
        return simulation.create(user, cid)
    except ValueError as error:
        raise HTTPException(422, str(error)) from None


@app.post("/api/cases/{cid}/simulation/{rid}/step")
def simulation_step(
    cid: str, rid: str, body: SimulationStep, user=Depends(require_user)
):
    authorize(cid, user)
    try:
        return simulation.advance(user, cid, rid, body.revision, body.action)
    except ValueError as error:
        raise HTTPException(
            409 if "changed" in str(error) else 422, str(error)
        ) from None


@app.get("/api/cases/{cid}/simulation/{rid}/sources/{eid}")
def simulation_source(cid: str, rid: str, eid: str, user=Depends(require_user)):
    authorize(cid, user)
    record = simulation.source(user, cid, rid, eid)
    if not record:
        raise HTTPException(404, "Simulation source not found.")
    return record


@app.get("/api/cases/{cid}/simulation/{rid}/brief")
def simulation_brief(cid: str, rid: str, user=Depends(require_user)):
    authorize(cid, user)
    try:
        return simulation.brief(user, cid, rid)
    except ValueError:
        raise HTTPException(404, "Simulation not found.") from None


@app.get("/health")
def health():
    return {"status": "ok", "synthetic": True, "index_ready": "index" in state}


@app.get("/api/config")
def config(request: Request, user=Depends(require_user)):
    return {
        "ai_configured": bool(
            provider_keys.personal_key(request.cookies.get(SESSION_COOKIE, ""))
            or os.getenv("OPENAI_API_KEY")
        ),
        "personal_key_connected": bool(
            provider_keys.personal_key(request.cookies.get(SESSION_COOKIE, ""))
        ),
        "model": os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
        "embedding": "BAAI/bge-small-en-v1.5",
        "vector_backend": os.getenv("VECTOR_BACKEND", "local"),
        "private_upload_backend": "local",
        "reranker": RERANK_MODEL,
        "corpus_documents": len(visible_documents(user, state["documents"])),
        "synthetic": True,
        "snapshot": "2026-10-17",
    }


@app.get("/api/cases")
def cases(user=Depends(require_user)):
    return [
        {k: v for k, v in detail(cid, user).items() if k != "documents"}
        for cid in state["cases"]
        if user.can_access_case(cid)
    ]


@app.get("/api/cases/{cid}")
def case(cid: str, user=Depends(require_user)):
    return detail(cid, user)


@app.get("/api/references")
def references(user=Depends(require_user)):
    return state["public"]


@app.get("/api/references/{did}/pdf")
def public_source_pdf(did: str, user=Depends(require_user)):
    if not any(d["id"] == did for d in state["public"]):
        raise HTTPException(404, "Document not found")
    path = ROOT / "data/corpus" / f"{did}.pdf"
    return FileResponse(path, media_type="application/pdf", filename=path.name)


class PersonalKey(BaseModel):
    model_config = ConfigDict(extra="forbid")
    api_key: str = Field(min_length=12, max_length=512, repr=False)


@app.post("/api/provider-key")
def connect_key(request: Request, body: PersonalKey, user=Depends(require_user)):
    if request.url.scheme != "https" and request.url.hostname not in (
        "localhost",
        "127.0.0.1",
        "testserver",
    ):
        raise HTTPException(400, "Use HTTPS to connect a personal key.")
    try:
        provider_keys.set_key(request.cookies.get(SESSION_COOKIE, ""), body.api_key)
    except ValueError as error:
        raise HTTPException(422, str(error)) from None
    return {
        "connected": True,
        "validated": False,
        "message": "Connected for this session. Your first AI request will verify provider access.",
    }


@app.delete("/api/provider-key")
def disconnect_key(request: Request, user=Depends(require_user)):
    provider_keys.forget_key(request.cookies.get(SESSION_COOKIE, ""))
    return {"connected": False}


class CommunicationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    event_type: Literal[
        "contact", "promise", "handoff", "acceptance", "update", "correction"
    ]
    team: str = Field(max_length=80)
    channel: Literal["Phone", "Email", "Store visit", "Internal note", "Chat"] = (
        "Internal note"
    )
    message: str = Field(min_length=3, max_length=1200)
    next_action: str = Field(default="", max_length=400)
    next_team: str = Field(default="", max_length=80)
    due_at: str = Field(default="", max_length=40)
    related_id: str = Field(default="", max_length=80)
    source_ids: list[str] = Field(default_factory=list, max_length=5)
    owner_contact_id: str = Field(default="", max_length=80)


@app.get("/api/cases/{cid}/communications")
def communication_timeline(cid: str, user=Depends(require_user)):
    authorize(cid, user)
    entries = communications.visible(user, cid)
    initial = detail(cid, user)["investigation"]["owner"]
    historic = [
        d
        for d in visible_documents(user, state["documents"], cid)
        if d["kind"] in ("conversation", "routing")
    ]
    return {
        "entries": entries,
        "ownership": communications.ownership(entries, initial),
        "teams": communications.TEAMS,
        "directory": directory.CONTACTS,
        "directory_note": directory.NOTE,
        "historical_sources": historic,
        "note": "Shared with authorized case members according to source permissions. Append a correction instead of editing history. Calls and emails are recorded manually; no external systems are connected.",
    }


@app.post("/api/cases/{cid}/communications")
def record_communication(
    cid: str, body: CommunicationInput, user=Depends(require_user)
):
    authorize(cid, user)
    try:
        return communications.append(user, cid, body.model_dump(), state["documents"])
    except ValueError as error:
        raise HTTPException(422, str(error)) from None


@app.get("/api/cases/{cid}/communications/{eid}")
def communication_source(cid: str, eid: str, user=Depends(require_user)):
    authorize(cid, user)
    entry = next((e for e in communications.visible(user, cid) if e["id"] == eid), None)
    if not entry:
        raise HTTPException(404, "Communication not found")
    return communications.document(entry)


@app.post("/api/cases/{cid}/uploads")
async def upload_pdf(cid: str, request: Request, user=Depends(require_user)):
    authorize(cid, user)
    content = bytearray()
    async for part in request.stream():
        content.extend(part)
        if len(content) > uploads.MAX_BYTES:
            raise HTTPException(413, "PDF limit is 10 MB.")
    import base64

    try:
        name = base64.b64decode(
            request.headers.get("x-document-name", ""), validate=True
        ).decode("utf-8")
    except Exception:
        name = "Uploaded document.pdf"
    try:
        record = await run_in_threadpool(
            uploads.store_pdf, user, cid, name, bytes(content)
        )
    except ValueError as error:
        raise HTTPException(422, str(error)) from None
    return {
        "id": record["id"],
        "title": record["title"],
        "pages": len(record["pages"]),
        "private": True,
    }


@app.get("/api/cases/{cid}/uploads/{did}/chunks")
@bounded_inference
def upload_chunks(
    cid: str,
    did: str,
    strategy: Literal["fixed", "semantic", "structure"] = "fixed",
    user=Depends(require_user),
):
    authorize(cid, user)
    record = uploads.get_record(user, cid, did)
    if not record:
        raise HTTPException(404, "Document not found")
    chunks = chunks_for(uploads.documents(record), strategy, state["index"].embeddings)
    return {
        "strategy": strategy,
        "count": len(chunks),
        "chunks": [
            {
                "id": c.metadata["chunk_id"],
                "page": c.metadata["page"],
                "text": c.page_content,
            }
            for c in chunks
        ],
    }


@app.delete("/api/cases/{cid}/uploads/{did}")
def delete_upload(cid: str, did: str, user=Depends(require_user)):
    authorize(cid, user)
    record = uploads.get_record(user, cid, did)
    if not record:
        raise HTTPException(404, "Document not found")
    uploads.remove(user, cid, did)
    uploads.remove_cached_indexes(did)
    with connect(state["db"]) as db:
        rows = db.execute(
            "SELECT id,payload FROM runs WHERE case_id=?", (cid,)
        ).fetchall()
        for run_id, payload in rows:
            run = json.loads(payload)
            if run.get("username") == user.username and (
                any(e.get("id") == did for e in run.get("evidence", []))
                or any(
                    c.get("source_id") == did
                    for c in run.get("answer", {}).get("claims", [])
                )
            ):
                db.execute("DELETE FROM runs WHERE id=?", (run_id,))
    return {
        "deleted": True,
        "note": "Private PDF, cached indexes and your saved answers citing this source were removed.",
    }


class Login(BaseModel):
    model_config = ConfigDict(extra="forbid")
    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1, max_length=512)


class Registration(Login):
    password: str = Field(min_length=12, max_length=512)


@app.post("/api/register", status_code=202)
def register(credentials: Registration):
    try:
        request_account(credentials.username, credentials.password)
    except ValueError as error:
        raise HTTPException(422, str(error)) from None
    return {
        "message": "If this username is available, your account request has been saved. An administrator must approve your access and assign cases before you can sign in. If you already have an account, use your existing password or contact your administrator."
    }


@app.post("/api/login")
def login(credentials: Login):
    user = authenticate(credentials.username, credentials.password)
    if not user:
        raise HTTPException(401, "Invalid username or password.")
    response = JSONResponse(user.public())
    response.set_cookie(
        SESSION_COOKIE,
        new_session(user),
        httponly=True,
        samesite="strict",
        secure=os.getenv("COOKIE_SECURE", "false").lower() == "true",
        max_age=SESSION_TTL,
    )
    return response


class AccountApproval(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role: Literal["customer_service", "supervisor"]
    case_ids: list[str] = Field(min_length=1, max_length=100)


@app.get("/api/admin/account-requests")
def account_requests(user=Depends(require_user)):
    if user.role != "head":
        raise HTTPException(403, "Head approval is required.")
    return {"usernames": pending_users()}


@app.post("/api/admin/account-requests/{username}/approve")
def approve_account(
    username: str, approval: AccountApproval, user=Depends(require_user)
):
    if user.role != "head":
        raise HTTPException(403, "Head approval is required.")
    if any(
        cid not in state["cases"] or not user.can_access_case(cid)
        for cid in approval.case_ids
    ):
        raise HTTPException(403, "You can only assign cases within your own access.")
    try:
        approve_user(username, approval.role, approval.case_ids)
    except ValueError:
        raise HTTPException(404, "Pending account not found.") from None
    return {"approved": True}


@app.get("/api/me")
def me(user=Depends(require_user)):
    return user.public()


@app.post("/api/logout")
def logout(request: Request, user=Depends(require_user)):
    provider_keys.forget_key(request.cookies.get(SESSION_COOKIE, ""))
    revoke(request.cookies.get(SESSION_COOKIE, ""))
    response = JSONResponse({"signed_out": True})
    response.delete_cookie(SESSION_COOKIE)
    return response


@app.get("/api/cases/{cid}/documents/{did}/pdf")
def source_pdf(cid: str, did: str, user=Depends(require_user)):
    authorize(cid, user)
    docs = (
        visible_documents(user, state["documents"], cid)
        + uploads.records(user, cid)
        + [communications.document(e) for e in communications.visible(user, cid)]
    )
    if not any(d["id"] == did for d in docs):
        raise HTTPException(404, "Document not found")
    if did.startswith("UPLOAD-"):
        from ..storage.database import remote

        if remote():
            from ..storage.uploads import read_pdf

            return Response(
                read_pdf(user, cid, did),
                media_type="application/pdf",
                headers={
                    "Content-Disposition": "inline; filename=private-document.pdf"
                },
            )
        path = uploads.folder(user, cid) / (did + ".pdf")
    else:
        path = ROOT / "data/corpus" / f"{did}.pdf"
    if not path.is_file():
        raise HTTPException(404, "PDF not generated")
    return FileResponse(path, media_type="application/pdf", filename=path.name)


class Query(BaseModel):
    model_config = ConfigDict(extra="forbid")
    rerank: bool = False
    question: str = Field(min_length=3, max_length=1500)


@app.post("/api/cases/{cid}/ask")
@bounded_inference
def ask(cid: str, query: Query, request: Request, user=Depends(require_user)):
    authorize(cid, user)
    question = query.question.strip()
    if len(question) < 3:
        raise HTTPException(422, "Please enter a question.")
    started = time.perf_counter()
    own = uploads.records(user, cid)
    graph = state["graph"]
    if own:
        # Reuse corpus document embeddings; embed only new private passages.
        if hasattr(state["index"].embeddings, "memo"):
            state["index"].embeddings.memo.update(
                {
                    d.page_content: v.tolist()
                    for d, v in zip(state["index"].docs, state["index"].vectors)
                }
            )
        docs = CorpusLoader().load() + [
            page for record in own for page in uploads.documents(record)
        ]
        index = HybridIndex(
            documents=docs, embeddings=state["index"].embeddings, strategy="fixed"
        )
        graph = build_graph(index, state["cases"], state["documents"] + own)
    shared = [communications.document(e) for e in communications.visible(user, cid)]
    visible = visible_documents(user, state["documents"], cid)
    case_detail = detail(cid, user)
    visible.append(directory.document(cid, case_detail["team_ownership"]))
    # Bounded recent context, explicitly disclosed to the reader.
    recent = shared[-40:]
    base = index if own else state["index"]
    graph = build_graph(
        ContextIndex(base, visible + own + recent),
        state["cases"],
        visible + own + recent,
    )
    bound = provider_keys.bind_key(
        provider_keys.personal_key(request.cookies.get(SESSION_COOKIE, ""))
    )
    try:
        # Suppress external tracing of personal-key and uploaded-document requests.
        from langsmith import tracing_context

        with tracing_context(enabled=False):
            result = graph.invoke(
                {
                    "case_id": cid,
                    "question": question,
                    "role": user.role,
                    "use_reranker": query.rerank,
                }
            )
    finally:
        provider_keys.reset_key(bound)
    if len(shared) > 40:
        result["answer"]["unknowns"].append(
            "This answer includes only the latest 40 shared entries. Review the full communication timeline for earlier entries."
        )
    proposed = (
        directory.suggestion(
            question, case_detail["investigation"], case_detail["team_ownership"]
        )
        if directory.routing_question(question) and not result.get("blocked")
        else None
    )
    if proposed:
        person = proposed["contact"]
        directory_id = "DIR-" + cid
        if any(e["id"] == directory_id for e in result.get("evidence", [])):
            quote = f"{person['id']}: {person['name']} — {person['role']} — {person['team']} — {person['email']}."
            result["answer"]["claims"].append(
                {
                    "text": f"Suggested fictional demo contact: {person['name']}, {person['role']} ({person['team']}). A directory suggestion is not an acknowledged case assignment.",
                    "source_id": directory_id,
                    "quote": quote,
                }
            )
            result["answer"]["suggested_next_step"] = (
                "A handoff is already awaiting acknowledgement; review it in Shared timeline."
                if proposed["pending_handoff_id"]
                else f"Review and save an internal handoff to {person['name']} in {person['team']}. No external message will be sent."
            )
    run = {
        "handoff_suggestion": proposed,
        "username": user.username,
        "role": user.role,
        "id": str(uuid4()),
        "case_id": cid,
        "question": question,
        "answer": result["answer"],
        "mode": result.get("mode", "evidence"),
        "trace": result["trace"],
        "evidence": result.get("evidence", []),
        "duration_ms": round((time.perf_counter() - started) * 1000),
    }
    with connect(state["db"]) as db:
        db.execute(
            "INSERT INTO runs VALUES (?,?,?,?)",
            (run["id"], cid, time.time(), json.dumps(run)),
        )
    return run


@app.get("/api/cases/{cid}/history")
def history(cid: str, user=Depends(require_user)):
    authorize(cid, user)
    with connect(state["db"]) as db:
        rows = db.execute(
            "SELECT payload FROM runs WHERE case_id=? ORDER BY created DESC LIMIT 20",
            (cid,),
        ).fetchall()
    return [
        json.loads(r[0])
        for r in rows
        if json.loads(r[0]).get("username") == user.username
        and json.loads(r[0]).get("role") == user.role
    ]


@app.get("/api/cases/{cid}/packet")
def packet(cid: str, user=Depends(require_user)):
    c = detail(cid, user)
    i = c["investigation"]
    text = (
        f"# Customer Case Intelligence — Return & Refund Intelligence\n\nOne case. Every connection.\n\n## Investigation handoff — {cid}\n\nDRAFT FOR HUMAN REVIEW · FICTIONAL DATA\n\nCustomer: {c['customer']}\nOrder: {c['order_id']}\nSnapshot: {c['snapshot']}\n\n## Finding\n{i['headline']}\n\nEvidence: "
        + ", ".join(i["source_ids"])
        + f"\n\n## Financial position\nRequested: {money(i['requested_cents'])}\nApproved: {money(i['approved_cents'])}\nSubmitted: {money(i['submitted_cents'])}\nPosted merchant credit: {money(i['posted_cents'])}\nProvisional credit (separate): {money(i['provisional_cents'])}\nNot evidenced as posted: {money(i['unconfirmed_cents'])}\n\n## Suggested owner\n{i['owner']} (demo routing, not an external assignment)\n\n## Next action\n{i['next_action']}\n\n## Conflicts\n"
        + (
            "\n".join(
                "- " + x["text"] + " [" + ", ".join(x["source_ids"]) + "]"
                for x in i["conflicts"]
            )
            or "No explicit conflicts detected by demo rules."
        )
        + "\n\n## Source register\n"
        + "\n".join(f"- {d['id']}: {d['title']} ({d['date']})" for d in c["documents"])
        + "\n\n## Limits\n"
        + i["coverage"]
        + " No external tickets, messages, disputes, or payments have been executed.\n"
    )
    bank = i.get("bank", {})
    if bank:
        text += (
            "\n\n## Bank connection\n"
            + bank["bank_case_id"]
            + " - "
            + bank["status"]
            + "\n"
            + bank["summary"]
            + "\nRequired information: "
            + bank["required_information"]
            + "\nNext owner: "
            + bank["next_owner"]
            + "\n"
        )
    entries = communications.visible(user, cid)
    team_state = communications.ownership(entries, i["owner"])
    text += "\n\n## Recorded team ownership\n" + team_state["current_team"]
    if team_state["pending_handoff"]:
        text += (
            "\nAwaiting acknowledgement: " + team_state["pending_handoff"]["next_team"]
        )
    person = team_state.get("current_owner")
    text += "\nAcknowledged demo individual: " + (
        person["name"] if person else "Not recorded"
    )
    text += "\n\n" + directory.document(cid, team_state)["text"]
    text += "\n\n## Shared communications (latest 40)\n" + "\n\n".join(
        communications.document(e)["text"] for e in entries[-40:]
    )
    return Response(
        text,
        media_type="text/markdown",
        headers={"Content-Disposition": f'attachment; filename="{cid}-handoff.md"'},
    )


@app.get("/api/cases/{cid}/packet.pdf")
def packet_pdf(cid: str, user=Depends(require_user)):
    from starlette.background import BackgroundTask

    from ..documents.rendering import render

    response = packet(cid, user)
    folder = runtime_dir() / "exports"
    folder.mkdir(exist_ok=True)
    path = folder / (str(uuid4()) + ".pdf")
    render(response.body.decode(), path, "Case handoff - " + cid, cid)
    os.chmod(path, 0o600)
    return FileResponse(
        path,
        media_type="application/pdf",
        filename=cid + "-handoff.pdf",
        background=BackgroundTask(path.unlink, missing_ok=True),
    )


@app.get("/")
def home():
    return FileResponse(ROOT / "app" / "static" / "index.html")


app.mount("/static", StaticFiles(directory=ROOT / "app" / "static"), name="static")
