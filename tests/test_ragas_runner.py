import math
from scripts.evaluate_ragas import read_references, clean_score, CONFIGURATIONS


def test_references_match_all_frozen_questions():
    rows = read_references()
    assert len(rows) == 32
    assert all(len(r["reference"]) > 20 for r in rows)
    assert len(CONFIGURATIONS) == 4


def test_invalid_metrics_are_missing_not_zero():
    for bad in (None, math.nan, math.inf, -1, 2, "bad"):
        assert clean_score(bad) is None
    assert clean_score(0) == 0
    assert clean_score(1) == 1


def test_real_ragas_metrics_with_mock_judge():
    """Check library/schema wiring; these mock scores never enter the report."""
    import asyncio
    import json
    import pytest

    pytest.importorskip("ragas")
    from ragas.dataset_schema import SingleTurnSample
    from ragas.llms import LangchainLLMWrapper
    from ragas.metrics import (
        Faithfulness,
        LLMContextPrecisionWithReference,
        LLMContextRecall,
    )
    from langchain_core.language_models.fake_chat_models import FakeListChatModel
    from scripts.evaluate_ragas import METRICS

    statement = "A refund was posted."
    model = FakeListChatModel(
        responses=[
            json.dumps({"statements": [statement]}),
            json.dumps(
                {
                    "statements": [
                        {
                            "statement": statement,
                            "reason": "In the context",
                            "verdict": 1,
                        }
                    ]
                }
            ),
            json.dumps({"reason": "In the context", "verdict": 1}),
            json.dumps(
                {
                    "classifications": [
                        {
                            "statement": statement,
                            "reason": "In the context",
                            "attributed": 1,
                        }
                    ]
                }
            ),
        ]
    )
    wrapper = LangchainLLMWrapper(model)
    metrics = [
        Faithfulness(llm=wrapper),
        LLMContextPrecisionWithReference(name="context_precision", llm=wrapper),
        LLMContextRecall(llm=wrapper),
    ]
    assert tuple(m.name for m in metrics) == METRICS
    sample = SingleTurnSample(
        user_input="Was a refund posted?",
        response=statement,
        retrieved_contexts=[statement],
        reference=statement,
    )

    async def run():
        return [await metric.single_turn_ascore(sample) for metric in metrics]

    assert all(abs(score - 1) < 0.00001 for score in asyncio.run(run()))
