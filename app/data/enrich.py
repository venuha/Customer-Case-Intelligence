"""Deterministic, source-oriented long-form corpus. No evaluation queries or gold labels."""

from datetime import date, timedelta


def extend(cases, documents):
    by_case = {c["id"]: c for c in cases}
    for d in documents:
        c = by_case[d["case_id"]]
        kind = d["kind"]
        facts = d["facts"]
        cid = c["id"]
        amount = c["amount_cents"]
        serial = c["device_id"]
        header = f"\n\n## Record scope and provenance\nThis fictional {kind} export belongs to {cid}, order {c['order_id']}, and the snapshot ending October 17, 2026. The originating team retains ownership of its record. Source timestamps describe recorded events; a later export timestamp does not mean an earlier action was repeated. Historical attachments are retained to explain what the employee could see at each contact. This export is a simulation, contains no real customer information, and is not connected to any institution.\n"
        if kind == "statement":
            rows = [
                "| Date | Description | Debit USD | Merchant credit USD | Provisional credit USD | Reference |",
                "|---|---|---:|---:|---:|---|",
            ]
            # Other transactions are genuine distractors within the fictional account, not alternate truths about this return.
            for j in range(44):
                dt = (date(2026, 9, 1) + timedelta(days=j)).isoformat()
                cents = 895 + (j * 137) % 8400
                label = [
                    "Groceries",
                    "Transit pass",
                    "Home supplies",
                    "Book purchase",
                    "Utility payment",
                    "Restaurant",
                ][j % 6]
                rows.append(
                    f"| {dt} | {label} (unrelated to device return) | {cents / 100:.2f} | 0.00 | 0.00 | AUX-{cid[-4:]}-{j:03d} |"
                )
                if j == 16:
                    rows.append(
                        f"| 2026-09-17 | Reversal of unrelated book purchase | 0.00 | 24.95 | 0.00 | AUX-REV-{cid[-4:]} |"
                    )
            if facts["posted_cents"]:
                rows.append(
                    f"| 2026-09-18 | Device merchant refund | 0.00 | {facts['posted_cents'] / 100:.2f} | 0.00 | REF-{int(cid[-4:]) - 1000:04d} |"
                )
            if facts["provisional_cents"]:
                rows.append(
                    f"| 2026-09-20 | Temporary dispute adjustment | 0.00 | 0.00 | {facts['provisional_cents'] / 100:.2f} | DSP-{int(cid[-4:]) - 1000:04d} |"
                )
            d["text"] += (
                header
                + "\n## Expanded transaction ledger\nThe purchase in the original excerpt is not repeated below. Amounts are unsigned and separated by entry type; these are transaction movements, not an account balance. The unrelated book reversal is not a device refund.\n\n"
                + "\n".join(rows)
                + "\n\n## Statement reconciliation notes\nThe review covers one supplied account and its stated date window. Reference matching takes precedence over an equal amount from an unrelated purchase. A temporary dispute adjustment has its own column and does not establish that the merchant sent funds. Foreign-currency accounts and replacement-card histories were not supplied. The absence of an entry cannot establish what occurred outside this excerpt.\n"
            )
        elif kind == "conversation":
            topics = [
                (
                    "Return logistics",
                    "The customer asks whether creating a shipping label means the parcel was accepted. The specialist explains that the carrier scan is a separate source.",
                ),
                (
                    "Warehouse follow-up",
                    "The employee asks for intake evidence tied to the return authorization. A delivered parcel does not identify which device was inside.",
                ),
                (
                    "Payment follow-up",
                    "The employee distinguishes internal approval from a processor submission result. No new payment action is evidenced by the conversation alone.",
                ),
                (
                    "Statement review",
                    "The customer asks why a support promise differs from the account view. The specialist requests a statement excerpt with dates, entry type, and reference.",
                ),
                (
                    "Store visit",
                    "The associate reads the prior notes and requests a concise handoff so the customer does not repeat the history. The associate cannot confirm a refund from a call note.",
                ),
                (
                    "Escalation continuity",
                    "The receiving team requests source links, unresolved questions, and a named reviewer. This contact is a request for investigation rather than proof of resolution.",
                ),
            ]
            log = []
            for j in range(c["contacts"]):
                topic, content = topics[j % len(topics)]
                dt = date(2026, 9, 15) + timedelta(days=min(j * 2, 30))
                log.append(
                    f"### Contact {j + 1:02d} · {dt.isoformat()} · {topic}\nCustomer: Please retain the order and device history so I do not need to start again. Specialist: {content} The employee checks reference {c['order_id']} and notes device {serial}. The next reviewer must consult the actual source record, not infer an event from this summary. No additional capture, warehouse acceptance, processor submission, or posted credit was created by this contact. The conversation is retained as evidence of communication only."
                )
            d["text"] += (
                header
                + "\n## Detailed contact log\nThe following contacts are additional detail within the recorded contact count; they do not add new financial events.\n\n"
                + "\n\n".join(log)
            )
        else:
            sections = {
                "order": [
                    (
                        "Item allocation",
                        "The order amount is the device purchase total, not the sum of purchases elsewhere in the account. The invoice identifies the original payment instrument with a masked suffix and retains the original currency. A later return is linked through the order reference rather than a customer name alone.",
                    ),
                    (
                        "Fulfilment controls",
                        "The dispatch team records outbound tracking separately from return tracking. The outbound serial is the expected device for intake comparison. Packaging accessories can be listed for shipping completeness without representing separately refundable purchases.",
                    ),
                ],
                "payment": [
                    (
                        "Capture reconciliation",
                        "Authorization and capture are separate states. The captured purchase is a debit. A matching amount in an approval queue is not a customer credit, and a voided authorization should not be counted as a submitted refund.",
                    ),
                    (
                        "Settlement export boundaries",
                        "The payment export covers the captured transaction and its original instrument. Bank posting is not established by a merchant settlement export. Reviewers must distinguish an internal batch identifier from a network trace reference.",
                    ),
                ],
                "return": [
                    (
                        "Label handling",
                        "The return authorization defines the requested scope. Label generation only creates shipping paperwork; carrier possession requires an acceptance scan or equivalent evidence. An unused label does not establish either loss or a delivered return.",
                    ),
                    (
                        "Return item scope",
                        "Inspection is performed for each device independently. Multi-device orders can have separate intake and payment outcomes. The requested amount is a customer return request rather than an automatic eligibility decision.",
                    ),
                ],
                "shipping": [
                    (
                        "Tracking interpretation",
                        "Scan events are reported by the fictional carrier. Delivery establishes arrival at a receiving location, but does not establish package contents or the condition of a device. A receiving signature should not be translated into an inspection decision.",
                    ),
                    (
                        "Chain of custody",
                        "Carrier tracking, receiving dock manifest, and warehouse intake are separate records. A gap between delivery and intake requires reconciliation. A tracking number must be matched to its return authorization before it is used as evidence for another order.",
                    ),
                ],
                "inspection": [
                    (
                        "Device matching",
                        "An intake clerk compares the expected identifier to the scanned identifier. Similar model names do not establish identity. A mismatch is retained as a discrepancy and must not be silently corrected by a support summary.",
                    ),
                    (
                        "Inspection record boundaries",
                        "Inspection findings apply only to items actually inspected. A second device in a bundle can remain unresolved even when the first item passed. Return acceptance and refund approval have separate owners and separate evidence.",
                    ),
                ],
                "approval": [
                    (
                        "Approval accounting",
                        "Approval documents an internal financial decision. It does not establish that the processor accepted a request, that settlement completed, or that the customer statement contains a credit. The approved amount must remain distinguishable from the original purchase total.",
                    ),
                    (
                        "Maker-checker review",
                        "The review queue preserves the amount, currency, original instrument, and reviewer status. A queue entry must not be reused as a payment completion receipt. Exceptions require source evidence before a new payment request is proposed.",
                    ),
                ],
                "refund": [
                    (
                        "Processor state boundaries",
                        "The recorded submission applies to the original captured transaction. Processor submission does not independently prove bank posting. A failed, canceled, or duplicate request needs its own event record; none should be fabricated from a customer report.",
                    ),
                    (
                        "Trace reconciliation",
                        "The demonstration trace reference is fictional and cannot be sent to a real payment network. A real investigation would obtain an available reference from the provider and use a separately authorized bank handoff. Partial submissions must be matched by both amount and transaction identity.",
                    ),
                ],
            }
            parts = []
            for heading, content in sections[kind]:
                parts.append(
                    f"## {heading}\n{content} For this export, the controlling references are case {cid}, order {c['order_id']}, and device {serial}. Preserve the source date when forwarding the evidence, and do not replace the recorded status with an employee expectation."
                )
            d["text"] += header + "\n\n".join(parts)
            if kind in ("order", "payment", "approval", "refund"):
                value = (
                    amount
                    if kind in ("order", "payment")
                    else facts.get("approved_cents", facts.get("submitted_cents", 0))
                )
                rows = [
                    "| Line | Component | Amount USD | Treatment |",
                    "|---|---|---:|---|",
                ]
                tax = value * 7 // 107
                subtotal = value - tax
                first = (
                    subtotal // 2
                    if c["scenario"] == "partial" and kind in ("order", "payment")
                    else subtotal
                )
                rows.append(
                    f"| 1 | Device allocation A | {first / 100:.2f} | Included |"
                )
                if first != subtotal:
                    rows.append(
                        f"| 2 | Device allocation B | {(subtotal - first) / 100:.2f} | Included |"
                    )
                rows.extend(
                    [
                        f"| 3 | Tax allocation | {tax / 100:.2f} | Included |",
                        f"| 4 | Total for this record | {value / 100:.2f} | Control total; do not sum twice |",
                    ]
                )
                d["text"] += (
                    "\n\n## Financial allocation table\nThe control total equals the components; it is not an additional charge. These lines allocate the amount already recorded above.\n\n"
                    + "\n".join(rows)
                )
    # Long independent documents add realistic within-case distractors without modifying payment truth.
    for c in cases:
        for kind, title, topics in [
            (
                "routing",
                "Escalation transfer journal",
                [
                    "Contact intake",
                    "Receiving investigation",
                    "Payments evidence request",
                    "Statement request",
                    "Handoff review",
                    "Closure review",
                ],
            ),
            (
                "account_history",
                "Prior account activity review",
                [
                    "Historical purchase search",
                    "Unrelated reversal review",
                    "Address correction",
                    "Replacement accessory enquiry",
                    "Contact preference update",
                    "Archive retention",
                ],
            ),
        ]:
            sections = []
            for j, topic in enumerate(topics):
                sections.append(
                    f"## {topic}\nJournal entry {j + 1} for {c['id']}. The reviewer follows the customer narrative across order, returns, and payments records while keeping this administrative activity separate from financial events. The team requests the original source reference and records what remains unavailable. A transferred ticket does not itself move a device or money. Queue labels such as complete describe administrative handling and do not establish a refund. No warehouse, processor, or bank event is asserted in this journal section. Historical activities must not be joined to the current return solely because the customer or amount resembles another record. The reviewer records the next question and retains the prior note for continuity."
                )
            documents.append(
                dict(
                    id=f"{c['id']}-{kind}",
                    case_id=c["id"],
                    kind=kind,
                    title=title,
                    date="2026-10-17",
                    source="Synthetic administrative archive",
                    synthetic=True,
                    facts={},
                    text=f"# {title}\nCase: {c['id']} | Order: {c['order_id']}\n\n"
                    + "\n\n".join(sections),
                )
            )
    return documents
