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
