from app.security.policy import Principal, visible_documents
from app.security.auth import (
    create_user,
    authenticate,
    new_session,
    revoke,
    require_user,
    SESSION_COOKIE,
)
from starlette.requests import Request
from fastapi import HTTPException
import secrets, pytest


def test_server_policy_denies_unassigned_and_private_sources():
    user = Principal("service", "customer_service", ("CASE-1001",))
    docs = [
        {"id": "shared", "case_id": "CASE-1001", "kind": "bank_status"},
        {"id": "private", "case_id": "CASE-1001", "kind": "statement"},
        {"id": "foreign", "case_id": "CASE-1002", "kind": "order"},
    ]
    assert [d["id"] for d in visible_documents(user, docs)] == ["shared"]
    assert not Principal("head", "head", ("CASE-1001",)).can_access_case("CASE-1002")


def test_hashed_revocable_sessions(tmp_path, monkeypatch):
    monkeypatch.setenv("CCI_RUNTIME_DIR", str(tmp_path))
    password = secrets.token_urlsafe(24)
    create_user("local", password, "supervisor", ["CASE-1001"])
    assert authenticate("local", "wrong") is None
    principal = authenticate("local", password)
    assert principal.role == "supervisor"
    token = new_session(principal)
    request = Request(
        {"type": "http", "headers": [(b"cookie", f"{SESSION_COOKIE}={token}".encode())]}
    )
    assert require_user(request).username == "local"
    assert password.encode() not in (tmp_path / "identity.sqlite").read_bytes()
    assert token.encode() not in (tmp_path / "identity.sqlite").read_bytes()
    revoke(token)
    with pytest.raises(HTTPException):
        require_user(request)
