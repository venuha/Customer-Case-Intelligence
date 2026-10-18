"""Fictional routing directory, distinct from verified case evidence and identity."""

import re

CONTACTS = [
    {
        "id": "DEMO-WH-01",
        "name": "Alex Morgan",
        "team": "Return reconciliation",
        "role": "Warehouse intake coordinator",
        "email": "alex.morgan@warehouse.example",
        "responsibility": "Locate intake scans and match the parcel, return authorization and device identifier.",
    },
    {
        "id": "DEMO-WH-02",
        "name": "Sam Rivera",
        "team": "Return reconciliation",
        "role": "Warehouse reconciliation lead",
        "email": "sam.rivera@warehouse.example",
        "responsibility": "Escalate missing intake records or device identifier mismatches.",
    },
    {
        "id": "DEMO-CS-01",
        "name": "Taylor Brooks",
        "team": "Customer service",
        "role": "Customer case coordinator",
        "email": "taylor.brooks@support.example",
        "responsibility": "Maintain the shared customer history and follow up on commitments.",
    },
    {
        "id": "DEMO-ST-01",
        "name": "Jamie Lee",
        "team": "Store support",
        "role": "Store escalation specialist",
        "email": "jamie.lee@store.example",
        "responsibility": "Coordinate store visits and preserve the customer explanation.",
    },
    {
        "id": "DEMO-LG-01",
        "name": "Casey Reed",
        "team": "Return logistics",
        "role": "Return shipping coordinator",
        "email": "casey.reed@logistics.example",
        "responsibility": "Locate label, carrier acceptance and delivery evidence.",
    },
    {
        "id": "DEMO-PY-01",
        "name": "Robin Patel",
        "team": "Payments operations",
        "role": "Refund operations specialist",
        "email": "robin.patel@payments.example",
        "responsibility": "Verify approval and processor submission; request the refund trace reference.",
    },
    {
        "id": "DEMO-BK-01",
        "name": "Drew Chen",
        "team": "Bank refund operations",
        "role": "Bank refund liaison",
        "email": "drew.chen@bank.example",
        "responsibility": "Review supplied bank evidence and identify missing trace information.",
    },
    {
        "id": "DEMO-RV-01",
        "name": "Avery Quinn",
        "team": "Case review",
        "role": "Case resolution lead",
        "email": "avery.quinn@review.example",
        "responsibility": "Review evidence completeness before proposing case closure.",
    },
]
NOTE = "All directory contacts are fictional demo personas, not user accounts or verified employees. Addresses use reserved .example domains and are not delivery channels. Handoffs are internal records; no external notification is sent."


def contact(contact_id):
    return next((dict(c) for c in CONTACTS if c["id"] == contact_id), None)


def document(cid, ownership=None):
    lines = [
        NOTE,
        "Directory entries are suggested contacts, not proof of individual case assignment.",
    ]
    for c in CONTACTS:
        lines.append(
            f"{c['id']}: {c['name']} — {c['role']} — {c['team']} — {c['email']}. Responsibility: {c['responsibility']}"
        )
    if ownership:
        person = ownership.get("current_owner")
        lines.append("Recorded current team: " + ownership["current_team"])
        lines.append(
            "Acknowledged individual owner: "
            + (person["name"] if person else "Not recorded")
        )
        pending = ownership.get("pending_handoff")
        if pending:
            requested = pending.get("individual_owner")
            lines.append(
                "Pending handoff: "
                + pending["next_team"]
                + "; requested individual: "
                + (requested["name"] if requested else "Not selected")
                + ". Awaiting internal acknowledgement."
            )
    return {
        "id": "DIR-" + cid,
        "case_id": cid,
        "kind": "team_directory",
        "title": "Demo team directory and recorded ownership",
        "source": "App demo routing directory",
        "date": "2026-10-17",
        "text": "\n".join(lines),
        "facts": {},
        "synthetic": True,
    }


def routing_question(question):
    return bool(
        re.search(
            r"warehouse|\bcontact\b|connect with|\bperson\b|\bowner\b|\bwho\b|handoff|hand off|assign",
            question,
            re.I,
        )
    )


def suggestion(question, investigation, ownership):
    pending = ownership.get("pending_handoff")
    team = (
        "Return reconciliation"
        if re.search("warehouse", question, re.I)
        else ownership["current_team"]
    )
    existing = ownership.get("current_owner")
    candidate = (
        existing
        if existing and existing["team"] == team
        else next((dict(c) for c in CONTACTS if c["team"] == team), None)
    )
    if not candidate:
        return None
    return {
        "contact": candidate,
        "next_team": team,
        "next_action": candidate["responsibility"]
        if team != investigation["owner"]
        else investigation["next_action"],
        "message": "Request internal follow-up on the missing case evidence. No external contact or completed warehouse/payment action is implied.",
        "pending_handoff_id": pending["id"] if pending else None,
        "note": NOTE,
    }
