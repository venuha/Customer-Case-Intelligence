import secrets
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from app.domain import communications
from app.main import app
from app.security.auth import create_user
from app.security.policy import Principal


@pytest.fixture
def communication_client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "")
    monkeypatch.setenv("CCI_SEED_HISTORY", "false")
    monkeypatch.setenv("CCI_RUNTIME_DIR", str(tmp_path))
    monkeypatch.setenv("OPENAI_API_KEY", "")
    from app.api.application import limits

    limits.clear()
    password = secrets.token_urlsafe(24)
    for name, role, cases in [
        ("alice", "customer_service", ["CASE-1001"]),
        ("bob", "customer_service", ["CASE-1001"]),
        ("head", "head", ["CASE-1001"]),
        ("foreign", "head", ["CASE-1002"]),
    ]:
        create_user(name, password, role, cases)
    with TestClient(app) as client:

        def login(name):
            assert (
                client.post(
                    "/api/login", json={"username": name, "password": password}
                ).status_code
                == 200
            )

        yield client, login


def entry(**changes):
    return {
        "event_type": "promise",
        "team": "Customer service",
        "channel": "Phone",
        "message": "Agent promised to locate the warehouse intake scan.",
        "next_action": "Request the intake scan from Return reconciliation.",
        **changes,
    }


def test_shared_ownership_requires_acknowledgement_and_preserves_author(
    communication_client,
):
    client, login = communication_client
    login("alice")
    result = client.post(
        "/api/cases/CASE-1001/communications",
        json=entry(event_type="handoff", next_team="Return reconciliation"),
    )
    assert result.status_code == 200
    eid = result.json()["id"]
    login("bob")
    data = client.get("/api/cases/CASE-1001/communications").json()
    assert data["entries"][0]["author"] == "alice"
    assert data["ownership"]["pending_handoff"]["id"] == eid
    assert (
        client.post(
            "/api/cases/CASE-1001/communications",
            json=entry(
                event_type="acceptance", team="Payments operations", related_id=eid
            ),
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/cases/CASE-1001/communications",
            json=entry(
                event_type="acceptance", team="Return reconciliation", related_id=eid
            ),
        ).status_code
        == 200
    )
    data = client.get("/api/cases/CASE-1001/communications").json()
    assert data["ownership"]["pending_handoff"] is None
    assert data["ownership"]["current_team"] == "Return reconciliation"
    assert data["entries"][1]["author"] == "bob"
    assert (
        client.post(
            "/api/cases/CASE-1001/communications",
            json=entry(
                event_type="acceptance", team="Return reconciliation", related_id=eid
            ),
        ).status_code
        == 422
    )
    assert (
        client.patch("/api/cases/CASE-1001/communications/" + eid, json={}).status_code
        == 405
    )


def test_communication_access_sources_and_actor_cannot_be_forged(communication_client):
    client, login = communication_client
    assert client.get("/api/cases/CASE-1001/communications").status_code == 401
    login("alice")
    assert (
        client.post(
            "/api/cases/CASE-1001/communications", json=entry(author="head")
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/cases/CASE-1001/communications",
            json=entry(source_ids=["CASE-1001-statement"]),
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/cases/CASE-1001/communications",
            json=entry(source_ids=["UPLOAD-private"]),
        ).status_code
        == 422
    )
    assert (
        client.post("/api/cases/CASE-1002/communications", json=entry()).status_code
        == 404
    )
    eid = client.post("/api/cases/CASE-1001/communications", json=entry()).json()["id"]
    login("foreign")
    assert client.get("/api/cases/CASE-1001/communications/" + eid).status_code == 404
    assert client.get("/api/cases/CASE-1002/communications/" + eid).status_code == 404


def test_restricted_source_restricts_entry_and_corrections(communication_client):
    client, login = communication_client
    login("head")
    eid = client.post(
        "/api/cases/CASE-1001/communications",
        json=entry(source_ids=["CASE-1001-statement"]),
    ).json()["id"]
    correction = client.post(
        "/api/cases/CASE-1001/communications",
        json=entry(event_type="correction", related_id=eid),
    ).json()
    assert correction["minimum_role"] == "head"
    login("alice")
    assert not client.get("/api/cases/CASE-1001/communications").json()["entries"]
    assert client.get("/api/cases/CASE-1001/communications/" + eid).status_code == 404
    assert (
        client.post(
            "/api/cases/CASE-1001/communications",
            json=entry(event_type="correction", related_id=eid),
        ).status_code
        == 422
    )


def test_agent_summary_covers_milestones_and_shared_entries(communication_client):
    client, login = communication_client
    login("alice")
    eid = client.post("/api/cases/CASE-1001/communications", json=entry()).json()["id"]
    response = client.post(
        "/api/cases/CASE-1001/ask",
        json={"question": "Summarize what happened so far, promises and next team."},
    )
    assert response.status_code == 200
    run = response.json()
    cited = {c["source_id"] for c in run["answer"]["claims"]}
    assert {
        "CASE-1001-order",
        "CASE-1001-return",
        "CASE-1001-shipping",
        "CASE-1001-conversation",
        eid,
    } <= cited
    sources = {e["id"]: e["text"] for e in run["evidence"]}
    assert all(c["quote"] in sources[c["source_id"]] for c in run["answer"]["claims"])
    assert any(
        c["source_id"] == "CASE-1001-order" and "1099.00" in c["quote"]
        for c in run["answer"]["claims"]
    )
    assert all(e["case_id"] == "CASE-1001" for e in run["evidence"])
    packet = client.get("/api/cases/CASE-1001/packet").text
    assert eid in packet and "alice" in packet


def test_concurrent_handoffs_are_serialized(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "")
    monkeypatch.setenv("CCI_RUNTIME_DIR", str(tmp_path))
    communications.initialize()
    user = Principal("alice", "customer_service", ("CASE-1001",))
    fields = {
        **entry(event_type="handoff", next_team="Return reconciliation"),
        "source_ids": [],
        "related_id": "",
        "due_at": "",
    }

    def submit(_):
        try:
            communications.append(user, "CASE-1001", fields, [])
            return True
        except ValueError:
            return False

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(submit, range(2))) == [False, True]
    assert len(communications.visible(user, "CASE-1001")) == 1


def test_historical_import_is_idempotent_and_does_not_invent_contacts(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("DATABASE_URL", "")
    monkeypatch.setenv("CCI_RUNTIME_DIR", str(tmp_path))
    monkeypatch.setenv("CCI_SEED_HISTORY", "true")
    communications.initialize()
    communications.seed_history()
    communications.seed_history()
    entries = communications.visible(
        Principal("viewer", "customer_service", ("CASE-1001",)), "CASE-1001"
    )
    assert len(entries) == 3
    assert [e["historical_date"] for e in entries] == [
        "2026-09-15",
        "2026-09-28",
        "2026-10-15",
    ]
    assert all(
        e["synthetic"] and e["source_ids"] == ["CASE-1001-conversation"]
        for e in entries
    )
    assert not communications.ownership(entries, "Return reconciliation")[
        "acknowledged"
    ]
