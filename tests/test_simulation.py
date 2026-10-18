import secrets
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from app.domain import simulation
from app.main import app
from app.security.auth import create_user
from app.security.policy import Principal


@pytest.fixture
def simulator(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "")
    monkeypatch.setenv("CCI_RUNTIME_DIR", str(tmp_path))
    monkeypatch.setenv("CCI_SEED_HISTORY", "false")
    monkeypatch.setenv("OPENAI_API_KEY", "")
    from app.api.application import limits

    limits.clear()
    password = secrets.token_urlsafe(24)
    for name in ["trainee", "colleague"]:
        create_user(name, password, "customer_service", ["CASE-1001"])
    with TestClient(app) as client:

        def login(name="trainee"):
            assert (
                client.post(
                    "/api/login", json={"username": name, "password": password}
                ).status_code
                == 200
            )

        yield client, login


def step(client, run, action, expected=200):
    response = client.post(
        f"/api/cases/CASE-1001/simulation/{run['id']}/step",
        json={"revision": run["revision"], "action": action},
    )
    assert response.status_code == expected
    return response.json()


def test_complete_journey_is_persistent_cited_and_leaves_case_unchanged(simulator):
    client, login = simulator
    login()
    base = "/api/cases/CASE-1001"
    before = client.get(base).json()
    run = client.post(base + "/simulation").json()
    assert run["simulation"] and "No money moves" in run["notice"]
    assert run["posted_cents"] == 0 and run["next_action"] == "received"
    for action in [
        "received",
        "verified",
        "approved",
        "submitted",
        "bank_received",
        "posted",
    ]:
        run = step(client, run, action)
        if action != "posted":
            assert run["posted_cents"] == 0
    assert run["posted_cents"] == 109900 and run["next_action"] is None
    login()
    assert client.get(base + "/simulation").json()["run"]["id"] == run["id"]
    assert client.get(base + "/simulation").json()["run"]["posted_cents"] == 109900
    assert client.get(base).json() == before
    brief = client.get(f"{base}/simulation/{run['id']}/brief").json()
    assert len(brief["claims"]) == 9
    for claim in brief["claims"]:
        source = client.get(
            f"{base}/simulation/{run['id']}/sources/{claim['source_id']}"
        )
        assert source.status_code == 200
        assert claim["text"] in source.json()["text"]
        assert source.json()["kind"] == "simulation_event"
    step(client, run, "posted", 422)
    next_run = client.post(base + "/simulation").json()
    assert next_run["id"] != run["id"]
    assert client.get(f"{base}/simulation/{run['id']}/brief").status_code == 200


def test_simulated_exceptions_block_progress_and_keep_original_history(simulator):
    client, login = simulator
    login()
    run = client.post("/api/cases/CASE-1001/simulation").json()
    step(client, run, "approved", 422)
    run = step(client, run, "received")
    run = step(client, run, "device_mismatch")
    assert run["issue"] == "device_mismatch" and run["approved_cents"] == 0
    step(client, run, "approved", 422)
    run = step(client, run, "verified")
    assert not run["issue"] and any(
        e["action"] == "device_mismatch" for e in run["events"]
    )
    run = step(client, run, "approved")
    run = step(client, run, "submitted")
    run = step(client, run, "bank_info_required")
    assert run["issue"] == "bank_info_required" and run["next_person"] == "Robin Patel"
    step(client, run, "posted", 422)
    run = step(client, run, "bank_received")
    assert not run["issue"] and run["posted_cents"] == 0
    run = step(client, run, "posted")
    assert any(e["action"] == "bank_info_required" for e in run["events"])


def test_simulation_permissions_and_untrusted_fields(simulator):
    client, login = simulator
    assert client.get("/api/cases/CASE-1001/simulation").status_code == 401
    login()
    run = client.post("/api/cases/CASE-1001/simulation").json()
    assert client.post("/api/cases/CASE-1002/simulation").status_code == 404
    assert (
        client.post(
            f"/api/cases/CASE-1001/simulation/{run['id']}/step",
            json={
                "revision": run["revision"],
                "action": "posted",
                "amount_cents": 109900,
                "username": "forged",
            },
        ).status_code
        == 422
    )
    login("colleague")
    assert client.get("/api/cases/CASE-1001/simulation").json()["run"] is None
    assert (
        client.get(f"/api/cases/CASE-1001/simulation/{run['id']}/brief").status_code
        == 404
    )
    eid = run["events"][0]["id"]
    assert (
        client.get(
            f"/api/cases/CASE-1001/simulation/{run['id']}/sources/{eid}"
        ).status_code
        == 404
    )
    step(client, run, "received", 422)


def test_simulation_retries_are_serialized(simulator):
    client, login = simulator
    login()
    run = client.post("/api/cases/CASE-1001/simulation").json()
    user = Principal("trainee", "customer_service", ("CASE-1001",))

    def advance():
        try:
            simulation.advance(
                user, "CASE-1001", run["id"], run["revision"], "received"
            )
            return "ok"
        except ValueError:
            return "stale"

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(lambda _: advance(), range(2))) == ["ok", "stale"]
    result = simulation.latest(user, "CASE-1001")
    assert sum(e["action"] == "received" for e in result["events"]) == 1
