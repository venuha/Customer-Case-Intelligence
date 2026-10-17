import json
from pathlib import Path

p = Path(__file__).resolve().parents[1] / "data"
docs = json.loads((p / "documents.json").read_text())
cases = json.loads((p / "cases.json").read_text())
states = [
    (
        "information_required",
        "Warehouse intake evidence is missing. No incoming bank refund is established.",
        "Intake scan and merchant processor reference",
        "Return reconciliation",
        0,
    ),
    (
        "received_pending_posting",
        "The synthetic bank acknowledgement confirms receipt for processing; posting is pending.",
        "Final posting confirmation",
        "Bank refund operations",
        0,
    ),
    (
        "partially_posted",
        "One device refund posted. The second refund is unresolved.",
        "Second device inspection and refund reference",
        "Return reconciliation",
        79900,
    ),
    (
        "posted",
        "The supplied bank evidence confirms matching merchant credit.",
        "Customer confirmation before closure",
        "Customer service",
        64900,
    ),
    (
        "awaiting_return",
        "A label is issued; carrier acceptance is not established.",
        "Carrier acceptance receipt",
        "Return logistics",
        0,
    ),
    (
        "information_required",
        "Device identifiers conflict; bank review requires merchant evidence.",
        "Correct device identifier and eligibility decision",
        "Return reconciliation",
        0,
    ),
    (
        "awaiting_merchant_submission",
        "Approval exists but submission is not established.",
        "Processor submission acknowledgement",
        "Payments operations",
        0,
    ),
    (
        "information_required",
        "Temporary dispute credit does not establish a final merchant refund.",
        "Final processor reference and bank posting confirmation",
        "Payments operations",
        0,
    ),
]
for c, (status, summary, required, owner, posted) in zip(cases, states):
    cid = c["id"]
    id = cid + "-BANK-SHARED"
    facts = dict(
        status=status,
        summary=summary,
        required_information=required,
        next_owner=owner,
        posted_cents=posted,
        bank_case_id="BC-" + cid.split("-")[1],
        order_id=c["order_id"],
        acceptance_scope="Synthetic evidence only; no live bank lookup",
    )
    record = dict(
        id=id,
        case_id=cid,
        kind="bank_status",
        title="Shared bank refund acknowledgement and information request",
        date="2026-10-17",
        source="Fictional bank liaison",
        synthetic=True,
        facts=facts,
        text=f"# Bank liaison record - {cid}\n\nFICTIONAL DEMONSTRATION. This approved support-sharing summary connects the order, return, merchant payment process and bank review. No real customer or institution is represented.\n\nOrder: {c['order_id']}. Bank case: {facts['bank_case_id']}. Status: {status}.\n\n{summary}\n\nRequired information: {required}. Next responsible team: {owner}. A requested item must be supplied with the case and order references so the receiving team can connect the evidence without asking the customer to repeat the history.\n\n| Connection | Verified value | Interpretation |\n| --- | --- | --- |\n| Customer case | {cid} | Shared investigation identifier |\n| Order | {c['order_id']} | Merchant order link |\n| Bank case | {facts['bank_case_id']} | Synthetic bank review link |\n| Posted credit cents | {posted} | Support-approved supplied evidence only |\n\nReceipt for processing is separate from posting to the customer account. Acceptance of a dispute for review is separate from acceptance of a merchant refund. Temporary dispute credit may be reversed and is never counted as final merchant credit. An absent entry in a supplied statement is not proof that no refund exists in another account or later window.\n\nThis record is authored synthetic data. It is not an API response, a payment instruction, or an executed bank action. Human review must verify provider references and account scope before closing a case.",
    )
    docs = [d for d in docs if d["id"] != id]
    docs.append(record)
(p / "documents.json").write_text(json.dumps(docs, indent=2))
print(len(docs) + len(json.loads((p / "public/references.json").read_text())))
