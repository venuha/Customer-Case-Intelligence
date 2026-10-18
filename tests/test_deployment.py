"""Hosted startup must preserve identities and put mutable data on the disk."""

import os
import secrets

import pytest
import yaml

from app.config import ROOT, index_dir
from app.security.auth import authenticate, create_user
from app.security.bootstrap import bootstrap_admin
from scripts import serve


def test_bootstrap_creates_head_once_without_resetting_password(tmp_path, monkeypatch):
    monkeypatch.setenv("CCI_RUNTIME_DIR", str(tmp_path / "state"))
    password = secrets.token_urlsafe(24)
    monkeypatch.setenv("CCI_BOOTSTRAP_PASSWORD", password)
    monkeypatch.setenv("CCI_BOOTSTRAP_USERNAME", "owner")
    assert bootstrap_admin()
    user = authenticate("owner", password)
    assert user.role == "head" and user.case_ids
    monkeypatch.delenv("CCI_BOOTSTRAP_PASSWORD")
    assert bootstrap_admin() is False
    assert authenticate("owner", password).role == "head"
    assert password.encode() not in (tmp_path / "state/identity.sqlite").read_bytes()


def test_bootstrap_missing_secret_fails_closed(tmp_path, monkeypatch):
    monkeypatch.setenv("CCI_RUNTIME_DIR", str(tmp_path))
    monkeypatch.delenv("CCI_BOOTSTRAP_PASSWORD", raising=False)
    with pytest.raises(ValueError, match="CCI_BOOTSTRAP_PASSWORD"):
        bootstrap_admin()


def test_bootstrap_cannot_promote_existing_account(tmp_path, monkeypatch):
    monkeypatch.setenv("CCI_RUNTIME_DIR", str(tmp_path))
    password = secrets.token_urlsafe(24)
    create_user("owner", password, "customer_service", ["CASE-1001"])
    monkeypatch.setenv("CCI_BOOTSTRAP_USERNAME", "owner")
    monkeypatch.setenv("CCI_BOOTSTRAP_PASSWORD", secrets.token_urlsafe(24))
    with pytest.raises(ValueError, match="already exists"):
        bootstrap_admin()
    assert authenticate("owner", password).role == "customer_service"


def test_container_launcher_uses_platform_port_single_worker(tmp_path, monkeypatch):
    monkeypatch.setenv("CCI_RUNTIME_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("CCI_INDEX_DIR", str(tmp_path / "index"))
    monkeypatch.setenv("PORT", "10000")
    monkeypatch.setenv("FORWARDED_ALLOW_IPS", "*")
    monkeypatch.setattr(serve, "bootstrap_admin", lambda: True)
    launched = []
    monkeypatch.setattr(
        serve.os, "execvp", lambda exe, args: launched.append((exe, args))
    )
    old_mask = os.umask(0o077)
    try:
        serve.main()
    finally:
        os.umask(old_mask)
    args = launched[0][1]
    assert args[args.index("--port") + 1] == "10000"
    assert args[args.index("--workers") + 1] == "1"
    assert args[args.index("--forwarded-allow-ips") + 1] == "*"
    assert index_dir() == tmp_path / "index"


def test_blueprint_keeps_secrets_out_of_source_and_state_on_disk():
    service = yaml.safe_load((ROOT / "render.yaml").read_text())["services"][0]
    settings = {item["key"]: item for item in service["envVars"]}
    for key in ("PINECONE_API_KEY", "CCI_BOOTSTRAP_PASSWORD"):
        assert settings[key] == {"key": key, "sync": False}
    assert "OPENAI_API_KEY" not in settings
    assert service["plan"] == "free" and "disk" not in service
    assert settings["REQUIRE_DURABLE_STORAGE"]["value"] == "true"
    for key in ("DATABASE_URL", "SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY"):
        assert settings[key] == {"key": key, "sync": False}
    mount = "/app/work/"
    for key in ("CCI_RUNTIME_DIR", "CCI_INDEX_DIR", "EMBEDDING_CACHE"):
        assert settings[key]["value"].startswith(mount)
    assert service["numInstances"] == 1
    assert service["renderSubdomainPolicy"] == "enabled"
