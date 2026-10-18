import pytest
from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture(autouse=True)
def isolate_request_rate_limits():
    from app.api.application import limits

    limits.clear()


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    import os, secrets
    from app.security.auth import create_user

    os.environ["CCI_RUNTIME_DIR"] = str(tmp_path_factory.mktemp("identity"))
    password = secrets.token_urlsafe(24)
    create_user(
        "test_head",
        password,
        "head",
        tuple("CASE-" + str(n) for n in range(1001, 1009)),
    )
    with TestClient(app) as client:
        assert (
            client.post(
                "/api/login", json={"username": "test_head", "password": password}
            ).status_code
            == 200
        )
        yield client


def test_case_isolation(client):
    r = client.get("/api/cases/CASE-1001")
    assert r.status_code == 200
    assert all(d["case_id"] == "CASE-1001" for d in r.json()["documents"])


def test_missing_case(client):
    assert client.get("/api/cases/CASE-9999").status_code == 404


def test_cross_case_question_refused(client):
    r = client.post(
        "/api/cases/CASE-1001/ask", json={"question": "Tell me about CASE-1002"}
    )
    assert r.status_code == 200
    assert not r.json()["answer"]["claims"]
    assert not r.json()["evidence"]


def test_unknown_identifier_refused(client):
    r = client.post(
        "/api/cases/CASE-1001/ask",
        json={"question": "Where is order ORD-99999 refund?"},
    )
    assert not r.json()["answer"]["claims"]
    assert "identifier" in r.json()["answer"]["unknowns"][0]


def test_no_key_excerpts_are_real(client, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    r = client.post(
        "/api/cases/CASE-1001/ask",
        json={"question": "Where is the refund after delivery?"},
    )
    run = r.json()
    assert run["mode"] == "evidence"
    sources = {d["id"]: d["text"] for d in run["evidence"]}
    assert run["answer"]["claims"]
    for c in run["answer"]["claims"]:
        assert c["quote"] in sources[c["source_id"]]


def test_input_validation(client):
    assert (
        client.post("/api/cases/CASE-1001/ask", json={"question": "x"}).status_code
        == 422
    )


def test_handoff_is_draft(client):
    r = client.get("/api/cases/CASE-1001/packet")
    assert r.status_code == 200
    assert "DRAFT FOR HUMAN REVIEW" in r.text
    assert "CASE-1002" not in r.text


def test_history_is_case_scoped(client):
    assert all(
        r["case_id"] == "CASE-1001"
        for r in client.get("/api/cases/CASE-1001/history").json()
    )


def test_security_headers(client):
    r = client.get("/")
    assert "frame-ancestors 'none'" in r.headers["content-security-policy"]
    assert r.headers["x-content-type-options"] == "nosniff"


def test_cross_origin_post_rejected(client):
    assert (
        client.post(
            "/api/cases/CASE-1001/ask",
            json={"question": "refund status"},
            headers={"origin": "https://example.invalid"},
        ).status_code
        == 403
    )


def test_unrelated_question_abstains(client, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    r = client.post(
        "/api/cases/CASE-1001/ask", json={"question": "What is the capital of France?"}
    )
    assert not r.json()["answer"]["claims"]


def test_role_access_and_revocation(client):
    import secrets
    from app.security.auth import create_user

    password = secrets.token_urlsafe(24)
    create_user("test_service", password, "customer_service", ["CASE-1001"])
    head_cookie = client.cookies.get("cci_session")
    r = client.post(
        "/api/login", json={"username": "test_service", "password": password}
    )
    assert r.status_code == 200
    assert client.get("/api/cases/CASE-1002").status_code == 404
    assert client.get("/api/cases").status_code == 200
    data = client.get("/api/cases/CASE-1001").json()
    assert all(
        d["kind"] in ("order", "return", "shipping", "conversation", "bank_status")
        for d in data["documents"]
    )
    assert data["investigation"]["approved_cents"] is None
    assert (
        client.get("/api/cases/CASE-1001/documents/CASE-1001-statement/pdf").status_code
        == 404
    )
    assert client.get("/api/cases/CASE-1001/history").json() == []
    run = client.post(
        "/api/cases/CASE-1001/ask",
        json={"question": "Show bank statement and refund payment details"},
    ).json()
    assert all(
        e["kind"]
        in (
            "order",
            "return",
            "shipping",
            "conversation",
            "bank_status",
            "public_guidance",
        )
        for e in run["evidence"]
    )
    assert client.post("/api/logout").status_code == 200
    assert client.get("/api/cases").status_code == 401
    client.cookies.clear()
    client.cookies.set("cci_session", head_cookie, domain="testserver.local", path="/")


def test_pdf_handoff_is_scoped_and_valid(client):
    from io import BytesIO
    from pypdf import PdfReader

    response = client.get("/api/cases/CASE-1001/packet.pdf")
    assert response.status_code == 200 and response.content.startswith(b"%PDF")
    text = " ".join(
        page.extract_text() for page in PdfReader(BytesIO(response.content)).pages
    )
    assert "DRAFT FOR HUMAN REVIEW" in text and "Bank connection" in text
    assert "CASE-1002" not in text


def test_client_cannot_grant_itself_a_role(client):
    assert (
        client.post(
            "/api/cases/CASE-1001/ask",
            json={"question": "refund status", "role": "head"},
        ).status_code
        == 422
    )


def test_registration_never_grants_session_or_roles(client):
    import secrets

    password = secrets.token_urlsafe(24)
    previous = client.cookies.get("cci_session")
    response = client.post(
        "/api/register", json={"username": "pending_api", "password": password}
    )
    assert response.status_code == 202 and not response.headers.get("set-cookie")
    assert client.cookies.get("cci_session") == previous
    assert (
        client.post(
            "/api/login", json={"username": "pending_api", "password": password}
        ).status_code
        == 401
    )
    assert (
        client.post(
            "/api/register",
            json={
                "username": "attacker",
                "password": password,
                "role": "head",
                "case_ids": ["CASE-1001"],
            },
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/register", json={"username": "weak", "password": "short"}
        ).status_code
        == 422
    )


def test_head_approves_pending_user_with_explicit_case_access(client):
    import secrets

    password = secrets.token_urlsafe(24)
    assert (
        client.post(
            "/api/register", json={"username": "review_candidate", "password": password}
        ).status_code
        == 202
    )
    assert (
        "review_candidate"
        in client.get("/api/admin/account-requests").json()["usernames"]
    )
    assert (
        client.post(
            "/api/admin/account-requests/review_candidate/approve",
            json={"role": "head", "case_ids": ["CASE-1001"]},
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/admin/account-requests/review_candidate/approve",
            json={"role": "customer_service", "case_ids": ["CASE-9999"]},
        ).status_code
        == 403
    )
    assert (
        client.post(
            "/api/admin/account-requests/review_candidate/approve",
            json={"role": "customer_service", "case_ids": ["CASE-1001"]},
        ).status_code
        == 200
    )
    cookie = client.cookies.get("cci_session")
    assert (
        client.post(
            "/api/login", json={"username": "review_candidate", "password": password}
        ).status_code
        == 200
    )
    assert client.get("/api/cases/CASE-1001").status_code == 200
    assert client.get("/api/cases/CASE-1002").status_code == 404
    assert client.get("/api/admin/account-requests").status_code == 403
    assert (
        client.post(
            "/api/admin/account-requests/pending_api/approve",
            json={"role": "supervisor", "case_ids": ["CASE-1001"]},
        ).status_code
        == 403
    )
    client.cookies.clear()
    client.cookies.set("cci_session", cookie, domain="testserver.local", path="/")


def test_personal_key_is_session_scoped_and_not_persisted(client, monkeypatch):
    from app.api.application import state
    from app.security.auth import new_session, SESSION_COOKIE
    from app.security.policy import Principal
    from app.security import provider_keys

    original = client.cookies.get(SESSION_COOKIE)
    first = new_session(Principal("test_head", "head", ("CASE-1001",)))
    second = new_session(Principal("test_head", "head", ("CASE-1001",)))

    def cookie(value):
        client.cookies.clear()
        client.cookies.set(SESSION_COOKIE, value, domain="testserver.local", path="/")

    key = "unit-only-provider-credential"
    cookie(first)
    assert client.post("/api/provider-key", json={"api_key": key}).status_code == 200
    assert client.get("/api/config").json()["personal_key_connected"]
    assert key not in client.get("/api/config").text
    assert (
        key
        not in client.post(
            "/api/provider-key", json={"api_key": key, "extra": "invalid"}
        ).text
    )

    class FakeGraph:
        def invoke(self, payload):
            assert provider_keys.effective_key() == key
            assert key not in str(payload)
            return {
                "answer": {
                    "claims": [],
                    "unknowns": ["Mock response"],
                    "suggested_next_step": "Review.",
                },
                "trace": ["Mock"],
                "evidence": [],
            }

    monkeypatch.setitem(state, "graph", FakeGraph())
    result = client.post("/api/cases/CASE-1001/ask", json={"question": "Check my case"})
    assert result.status_code == 200
    assert (
        key not in result.text
        and key not in client.get("/api/cases/CASE-1001/history").text
    )
    assert provider_keys._current.get() is None
    cookie(second)
    assert not client.get("/api/config").json()["personal_key_connected"]
    cookie(first)
    assert client.post("/api/logout").status_code == 200
    assert provider_keys.personal_key(first) is None
    cookie(original)


def test_private_pdf_upload_chunks_retrieval_and_owner_isolation(client):
    import pymupdf, secrets
    from app.security.auth import create_user, new_session, SESSION_COOKIE
    from app.security.policy import Principal

    original = client.cookies.get(SESSION_COOKIE)
    pdf = pymupdf.open()
    page = pdf.new_page()
    page.insert_text(
        (70, 90),
        "PRIVATEUPLOAD8675: The supplemental refund note requests a warehouse intake receipt.",
    )
    content = pdf.tobytes()
    pdf.close()
    response = client.post(
        "/api/cases/CASE-1001/uploads",
        content=content,
        headers={"content-type": "application/pdf"},
    )
    assert response.status_code == 200
    did = response.json()["id"]
    assert (
        client.get("/api/cases/CASE-1001/uploads/" + did + "/chunks").json()["count"]
        > 0
    )
    detail = client.get("/api/cases/CASE-1001").json()
    assert any(d["id"] == did for d in detail["documents"])
    result = client.post(
        "/api/cases/CASE-1001/ask",
        json={"question": "What does PRIVATEUPLOAD8675 request?"},
    )
    assert result.status_code == 200
    assert any(e["id"] == did for e in result.json()["evidence"])
    create_user("other_upload_owner", secrets.token_urlsafe(24), "head", ["CASE-1001"])
    other = new_session(Principal("other_upload_owner", "head", ("CASE-1001",)))
    client.cookies.clear()
    client.cookies.set(SESSION_COOKIE, other, domain="testserver.local", path="/")
    assert all(
        d["id"] != did for d in client.get("/api/cases/CASE-1001").json()["documents"]
    )
    assert (
        client.get("/api/cases/CASE-1001/uploads/" + did + "/chunks").status_code == 404
    )
    assert (
        client.get("/api/cases/CASE-1001/documents/" + did + "/pdf").status_code == 404
    )
    assert client.delete("/api/cases/CASE-1001/uploads/" + did).status_code == 404
    client.cookies.clear()
    client.cookies.set(SESSION_COOKIE, original, domain="testserver.local", path="/")
    assert client.delete("/api/cases/CASE-1001/uploads/" + did).status_code == 200
    assert (
        client.get("/api/cases/CASE-1001/uploads/" + did + "/chunks").status_code == 404
    )
    assert not any(
        e["id"] == did
        for run in client.get("/api/cases/CASE-1001/history").json()
        for e in run.get("evidence", [])
    )
    assert (
        client.post("/api/cases/CASE-1001/uploads", content=b"not a pdf").status_code
        == 422
    )
