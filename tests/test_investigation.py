import json
from pathlib import Path
import pytest
from app.domain.investigation import investigate

ROOT = Path(__file__).resolve().parents[1]
CASES = json.loads((ROOT / "data/cases.json").read_text())
DOCS = json.loads((ROOT / "data/documents.json").read_text())


def result(n):
    c = CASES[n - 1]
    return investigate(c, [d for d in DOCS if d["case_id"] == c["id"]])


def test_delivery_is_not_warehouse_verification():
    i = result(1)
    assert i["status"] == "blocked"
    assert i["last_verified"] == "Carrier delivery"
    assert i["posted_cents"] == 0
    assert not next(t for t in i["timeline"] if t["label"] == "Device verified")[
        "verified"
    ]


def test_submitted_is_not_posted():
    i = result(2)
    assert i["submitted_cents"] == 89900
    assert i["posted_cents"] == 0
    assert i["status"] == "tracing"


def test_partial_refund_balance():
    i = result(3)
    assert i["unconfirmed_cents"] == 79900
    assert i["posted_cents"] == 79900
    assert i["status"] == "blocked"


def test_posted_refund_resolved():
    assert result(4)["status"] == "resolved"
    assert result(4)["last_verified"] == "Refund posted"


def test_label_is_not_delivery():
    i = result(5)
    assert i["status"] == "waiting"
    assert i["last_verified"] == "Return authorized"


def test_device_mismatch_prevents_acceptance():
    i = result(6)
    assert i["status"] == "blocked"
    assert "identifier" in i["headline"]
    assert i["approved_cents"] == 0


def test_approval_is_not_submission():
    i = result(7)
    assert i["approved_cents"] == 74900
    assert i["submitted_cents"] == 0
    assert i["status"] == "blocked"


def test_provisional_credit_is_not_refund():
    i = result(8)
    assert i["provisional_cents"] == 129900
    assert i["posted_cents"] == 0
    assert i["unconfirmed_cents"] == 129900


@pytest.mark.parametrize("n", range(1, 9))
def test_all_findings_have_case_specific_citations(n):
    i = result(n)
    c = CASES[n - 1]
    ids = {d["id"] for d in DOCS if d["case_id"] == c["id"]}
    assert i["source_ids"]
    assert set(i["source_ids"]) <= ids


def test_bank_receipt_is_not_posting():
    import json
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    case = next(
        c
        for c in json.loads((root / "data/cases.json").read_text())
        if c["id"] == "CASE-1002"
    )
    docs = [
        d
        for d in json.loads((root / "data/documents.json").read_text())
        if d["case_id"] == case["id"]
    ]
    result = investigate(case, docs)
    assert result["bank"]["status"] == "received_pending_posting"
    assert result["submitted_cents"] > 0 and result["posted_cents"] == 0
    assert result["status"] != "resolved"


def test_every_case_has_a_linked_bank_information_handoff():
    import json
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    cases = json.loads((root / "data/cases.json").read_text())
    docs = json.loads((root / "data/documents.json").read_text())
    bank_ids = []
    for case in cases:
        bank = next(
            d for d in docs if d["case_id"] == case["id"] and d["kind"] == "bank_status"
        )
        facts = bank["facts"]
        assert facts["order_id"] == case["order_id"]
        assert facts["required_information"] and facts["next_owner"]
        assert 0 <= facts["posted_cents"] <= case["amount_cents"]
        bank_ids.append(facts["bank_case_id"])
    assert len(set(bank_ids)) == len(cases)
