import pytest
from fastapi.testclient import TestClient
from app.main import app


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
    client.cookies.set("cci_session", head_cookie)


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
