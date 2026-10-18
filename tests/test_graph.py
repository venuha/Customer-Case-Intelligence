import json
from pathlib import Path
from app.rag.graph import build_graph
from app.rag.retrieval import HybridIndex

ROOT = Path(__file__).resolve().parents[1]


def test_invalid_generated_quote_is_removed(monkeypatch):
    import app.rag.graph as mod
    from langchain_core.runnables import RunnableLambda
    from app.rag.graph import Answer, Claim

    class Model:
        def __init__(self, **kwargs):
            pass

        def with_structured_output(self, *args, **kwargs):
            return RunnableLambda(
                lambda x: Answer(
                    claims=[
                        Claim(
                            text="Invented refund completion",
                            source_id="CASE-1001-statement",
                            quote="This exact quote never appeared.",
                        )
                    ],
                    unknowns=[],
                    suggested_next_step="Review evidence.",
                )
            )

    monkeypatch.setenv("OPENAI_API_KEY", "test-key-not-a-real-secret")
    monkeypatch.setattr(mod, "ChatOpenAI", Model)
    cases = {c["id"]: c for c in json.loads((ROOT / "data/cases.json").read_text())}
    docs = json.loads((ROOT / "data/documents.json").read_text())
    graph = build_graph(HybridIndex(), cases, docs)
    run = graph.invoke(
        {"case_id": "CASE-1001", "question": "Was the refund posted in the statement?"}
    )
    assert not run["answer"]["claims"]
    assert "removed" in run["answer"]["unknowns"][0]


def test_personal_key_reaches_real_graph_without_state_leak(monkeypatch):
    import app.rag.graph as mod
    from app.security.provider_keys import bind_key, reset_key
    from langchain_core.runnables import RunnableLambda

    seen = []

    class Model:
        def __init__(self, **kwargs):
            seen.append(kwargs["api_key"])
            assert kwargs["base_url"] == "https://api.openai.com/v1"

        def with_structured_output(self, *args, **kwargs):
            return RunnableLambda(
                lambda value: mod.Answer(
                    claims=[], unknowns=["Mock response"], suggested_next_step="Review"
                )
            )

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(mod, "ChatOpenAI", Model)
    cases = {c["id"]: c for c in json.loads((ROOT / "data/cases.json").read_text())}
    docs = json.loads((ROOT / "data/documents.json").read_text())
    graph = build_graph(HybridIndex(backend="local"), cases, docs)
    handle = bind_key("mock-personal-value")
    try:
        run = graph.invoke(
            {
                "case_id": "CASE-1001",
                "question": "Was the refund posted in the statement?",
            }
        )
    finally:
        reset_key(handle)
    assert seen == ["mock-personal-value"]
    assert run["mode"] == "openai"
    assert "mock-personal-value" not in json.dumps(run)
