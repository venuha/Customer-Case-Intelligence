"""Reproducible fictional records. No real consumers or institutional data."""

import json
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def generate():
    cases, docs = [], []
    scenarios = [
        ("Maya Chen", "warehouse", 109900, 0, 0, 0, 47, "Delivered, not reconciled"),
        ("Jordan Ellis", "submitted", 89900, 89900, 0, 0, 19, "Refund needs tracing"),
        (
            "Alex Morgan",
            "partial",
            159800,
            79900,
            79900,
            0,
            28,
            "One device unresolved",
        ),
        ("Sam Rivera", "complete", 64900, 64900, 64900, 0, 12, "Refund posted"),
        ("Taylor Brooks", "label", 119900, 0, 0, 0, 9, "Awaiting carrier acceptance"),
        ("Casey Park", "mismatch", 99900, 0, 0, 0, 35, "Device identifier mismatch"),
        ("Riley Quinn", "approved", 74900, 0, 0, 0, 22, "Approved, not submitted"),
        (
            "Avery Lane",
            "provisional",
            129900,
            129900,
            0,
            129900,
            31,
            "Temporary credit only",
        ),
    ]
    for i, (
        name,
        scenario,
        amount,
        submitted,
        posted,
        provisional,
        age,
        label,
    ) in enumerate(scenarios, 1):
        cid = f"CASE-{1000 + i}"
        order = f"ORD-{24000 + i}"
        device = f"DEV-{88000 + i}"
        case = dict(
            id=cid,
            customer=name,
            initials="".join(x[0] for x in name.split()),
            order_id=order,
            device_id=device,
            scenario=scenario,
            amount_cents=amount,
            currency="USD",
            age_days=age,
            contacts=18 if i == 1 else 2 + i,
            label=label,
            opened=(date(2026, 10, 17) - timedelta(days=age)).isoformat(),
            snapshot="2026-10-17",
            product="Two handheld devices"
            if scenario == "partial"
            else "Handheld device · 256 GB",
        )
        cases.append(case)

        def add(kind, title, date, text, facts=None):
            did = f"{cid}-{kind}"
            docs.append(
                dict(
                    id=did,
                    case_id=cid,
                    kind=kind,
                    title=title,
                    date=date,
                    source="Synthetic " + kind.replace("_", " "),
                    synthetic=True,
                    text=f"# {title}\nCase: {cid} | Order: {order}\nSnapshot: 2026-10-17\n\n"
                    + text,
                    facts=facts or {},
                )
            )
            return did

        add(
            "order",
            "Order confirmation",
            "2026-08-31",
            f"Customer: {name}. Device identifier: {device}.\n\n| Order | Item | Amount (USD) | Payment |\n|---|---|---:|---|\n| {order} | {case['product']} | {amount / 100:.2f} | Card ending 4242 |",
            {"purchase_cents": amount, "device_id": device},
        )
        add(
            "payment",
            "Captured purchase transaction",
            "2026-09-01",
            f"Transaction PAY-{i:04d}. Order {order}. Captured purchase: USD {amount / 100:.2f}. Currency USD. Status captured. This is a debit, not a refund.",
            {"captured_cents": amount},
        )
        add(
            "return",
            "Return authorization and label",
            "2026-09-04",
            f"Return RMA-{i:04d} authorized for {device}. Return label SHIP-{i:04d} created. Requested device refund USD {amount / 100:.2f}. A label is not proof of carrier acceptance.",
            {"return_requested_cents": amount, "label_created": True},
        )
        delivered = scenario != "label"
        add(
            "shipping",
            "Carrier tracking history",
            "2026-09-09" if delivered else "2026-09-04",
            f"Tracking SHIP-{i:04d}. "
            + (
                "Carrier accepted September 6. Delivered September 9 to returns receiving dock; signed by receiving clerk. Delivery does not identify package contents."
                if delivered
                else "Label created. No carrier acceptance or delivery scan appears in this snapshot."
            ),
            {"carrier_accepted": delivered, "delivered": delivered},
        )
        if scenario not in ("warehouse", "label"):
            mismatch = scenario == "mismatch"
            actual = "DEV-OTHER-771" if mismatch else device
            add(
                "inspection",
                "Warehouse inspection record",
                "2026-09-10",
                f"RMA-{i:04d}. Expected device {device}. Scanned device {actual}. "
                + (
                    "Identifier mismatch; return is held for reconciliation. No refund acceptance recorded."
                    if mismatch
                    else "First device accepted; second device has no inspection record in this snapshot."
                    if scenario == "partial"
                    else "Device matched and accepted; condition check passed."
                ),
                {
                    "expected_device": device,
                    "scanned_device": actual,
                    "accepted": not mismatch,
                    "accepted_cents": 79900
                    if scenario == "partial"
                    else (0 if mismatch else amount),
                },
            )
        if scenario not in ("warehouse", "label", "mismatch"):
            approved = 79900 if scenario == "partial" else amount
            add(
                "approval",
                "Refund approval record",
                "2026-09-11",
                f"Refund approval APR-{i:04d}: USD {approved / 100:.2f} approved. Approval is an internal decision and does not confirm payment submission or bank posting.",
                {"approved_cents": approved},
            )
        if submitted:
            add(
                "refund",
                "Processor refund record",
                "2026-09-12",
                f"Order {order}. Refund REF-{i:04d}. USD {submitted / 100:.2f} submitted to original card ending 4242. Processor status: submitted. Trace reference DEMO-TRACE-{i:04d} (fictional, not usable on payment networks). Customer posting is not confirmed by this record.",
                {
                    "submitted_cents": submitted,
                    "trace_reference": f"DEMO-TRACE-{i:04d}",
                },
            )
        add(
            "statement",
            "Customer-provided statement excerpt",
            "2026-10-16",
            "Customer-provided fictional card statement; review window September 1–October 16, 2026.\n\n| Entry | Type | Amount USD | Reference |\n|---|---|---:|---|\n"
            + f"| Purchase | Debit | {amount / 100:.2f} | PAY-{i:04d} |\n"
            + (
                f"| Merchant refund | Posted credit | {posted / 100:.2f} | REF-{i:04d} |\n"
                if posted
                else ""
            )
            + (
                f"| Dispute adjustment | Provisional credit | {provisional / 100:.2f} | DSP-{i:04d} |\n"
                if provisional
                else ""
            )
            + (
                "\nNo matching merchant refund credit appears in the supplied excerpt. This does not establish what occurred outside the supplied account and date range."
                if not posted
                else "\nMerchant refund credit appears in the supplied excerpt."
            ),
            {
                "posted_cents": posted,
                "provisional_cents": provisional,
                "window_end": "2026-10-16",
            },
        )
        add(
            "conversation",
            "Support conversation history",
            "2026-10-15",
            (
                "September 15, customer: I returned the device and tracking shows delivered. Agent: I will ask the warehouse.\nSeptember 28, agent: Your refund is completed. No payment reference was attached to that statement.\nOctober 15, store associate: Customer has repeated this history many times; please reconcile receiving and payment records."
                if scenario == "warehouse"
                else "Customer asks for a single explanation of the return and refund status. Agent opens a follow-up investigation. No external action was executed by this demonstration."
            ),
            {"refund_claimed_complete": scenario == "warehouse"},
        )
    try:
        from .enrich import extend
    except ImportError:
        from enrich import extend
    docs = extend(cases, docs)
    (ROOT / "data" / "cases.json").write_text(json.dumps(cases, indent=2))
    (ROOT / "data" / "documents.json").write_text(json.dumps(docs, indent=2))
    return cases, docs


if __name__ == "__main__":
    c, d = generate()
    print(f"{len(c)} cases; {len(d)} synthetic source documents")
