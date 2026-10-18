"""Append-only case communications; recorded commitments never prove a payment."""

import hashlib
import json
import time
from datetime import datetime, timezone
from uuid import uuid4

from app.config import runtime_dir
from app.domain.directory import contact
from app.security.policy import minimum_role, role_allows
from app.storage.database import connect, remote

TEAMS = (
    "Customer service",
    "Store support",
    "Return logistics",
    "Return reconciliation",
    "Payments operations",
    "Bank refund operations",
    "Case review",
)
KINDS = ("contact", "promise", "handoff", "acceptance", "update", "correction")


def db_path():
    return runtime_dir() / "communications.sqlite"


def initialize():
    with connect(db_path()) as db:
        db.execute(
            "CREATE TABLE IF NOT EXISTS communications (id TEXT PRIMARY KEY, case_id TEXT NOT NULL, created REAL NOT NULL, payload TEXT NOT NULL)"
        )
        db.execute(
            "CREATE INDEX IF NOT EXISTS communications_case ON communications(case_id,created)"
        )


def all_entries(cid, db=None):
    if db is None:
        with connect(db_path()) as connection:
            return all_entries(cid, connection)
    return [
        json.loads(r[0])
        for r in db.execute(
            "SELECT payload FROM communications WHERE case_id=? ORDER BY created,id",
            (cid,),
        ).fetchall()
    ]


def visible(user, cid):
    return [e for e in all_entries(cid) if role_allows(user.role, e["minimum_role"])]


def ownership(entries, initial):
    current = initial
    acknowledged = False
    action = ""
    person = None
    pending = None
    for entry in entries:
        if entry["event_type"] == "handoff":
            pending = entry
        elif (
            entry["event_type"] == "acceptance"
            and pending
            and entry["related_id"] == pending["id"]
        ):
            current = entry["team"]
            acknowledged = True
            person = entry.get("individual_owner")
            action = pending["next_action"]
            pending = None
    return {
        "current_team": current,
        "current_owner": person,
        "acknowledged": acknowledged,
        "next_action": action,
        "pending_handoff": pending,
        "note": "Internal recorded ownership. Team labels are supplied by authors; external team membership and systems are not verified.",
    }


def append(user, cid, fields, source_docs):
    if not user.can_access_case(cid):
        raise ValueError("Case not found.")
    event_type = fields["event_type"]
    if event_type not in KINDS or fields["team"] not in TEAMS:
        raise ValueError("Choose a valid communication type and team.")
    if len(fields["message"].strip()) < 3:
        raise ValueError("Describe what happened.")
    if event_type != "handoff" and fields["next_team"]:
        raise ValueError("Only a handoff selects a receiving team.")
    requested_owner = fields.get("owner_contact_id", "")
    person = contact(requested_owner) if requested_owner else None
    if requested_owner and (
        event_type != "handoff" or not person or person["team"] != fields["next_team"]
    ):
        raise ValueError(
            "Choose a demo individual in the receiving team for a handoff."
        )
    sources = {
        d["id"]: d
        for d in source_docs
        if d["case_id"] == cid and user.can_read(d) and d["kind"] != "user_upload"
    }
    if any(s not in sources for s in fields["source_ids"]):
        raise ValueError(
            "Choose permitted shared case sources; private uploads cannot be shared through references."
        )
    required = max(
        (minimum_role(sources[s]["kind"]) for s in fields["source_ids"]),
        key=lambda r: {"customer_service": 0, "supervisor": 1, "head": 2}[r],
        default="customer_service",
    )
    if event_type in ("handoff", "acceptance") and required != "customer_service":
        raise ValueError(
            "Handoffs must use support-shareable sources so the receiving team can see them."
        )
    if event_type == "handoff" and (
        fields["next_team"] not in TEAMS or not fields["next_action"].strip()
    ):
        raise ValueError("A handoff needs a receiving team and a next action.")
    if event_type == "promise" and not fields["next_action"].strip():
        raise ValueError("Record the promised action.")
    if fields.get("due_at"):
        due = datetime.fromisoformat(fields["due_at"].replace("Z", "+00:00"))
        if due.tzinfo is None:
            raise ValueError("Use a deadline with a timezone.")
    with connect(db_path()) as db:
        if remote():
            lock = int(hashlib.sha256(cid.encode()).hexdigest()[:14], 16)
            db.execute("SELECT pg_advisory_xact_lock(?)", (lock,))
        else:
            db.execute("BEGIN IMMEDIATE")
        entries = all_entries(cid, db)
        if len(entries) >= 500:
            raise ValueError(
                "This demo case has reached its 500-entry communication limit."
            )
        related = next((e for e in entries if e["id"] == fields["related_id"]), None)
        state = ownership(entries, "Unassigned")
        if event_type == "handoff" and state["pending_handoff"]:
            raise ValueError("A handoff is already awaiting acknowledgement.")
        if event_type == "acceptance":
            pending = state["pending_handoff"]
            if (
                not pending
                or fields["related_id"] != pending["id"]
                or fields["team"] != pending["next_team"]
            ):
                raise ValueError(
                    "Acknowledge the current handoff as its receiving team."
                )
            person = pending.get("individual_owner")
        if event_type == "correction":
            if not related or not role_allows(user.role, related["minimum_role"]):
                raise ValueError("Select a visible entry in this case to correct.")
            required = max(
                (required, related["minimum_role"]),
                key=lambda r: {"customer_service": 0, "supervisor": 1, "head": 2}[r],
            )
        elif event_type not in ("acceptance",) and fields["related_id"]:
            raise ValueError(
                "Only corrections and acknowledgements reference another entry."
            )
        now = time.time()
        entry = {
            **fields,
            "id": "COM-" + uuid4().hex,
            "case_id": cid,
            "author": user.username,
            "individual_owner": person,
            "author_role": user.role,
            "recorded_at": datetime.now(timezone.utc).isoformat(),
            "minimum_role": required,
            "origin": "Recorded in this app",
            "synthetic": False,
        }
        db.execute(
            "INSERT INTO communications VALUES (?,?,?,?)",
            (entry["id"], cid, now, json.dumps(entry)),
        )
    return entry


def document(entry):
    text = "\n".join(
        [
            f"Entry: {entry['id']}",
            f"Type: {entry['event_type']}",
            f"Recorded by: {entry['author']} ({entry['author_role']})",
            f"Reporting team: {entry['team']}",
            f"Recorded at: {entry['recorded_at']}",
            f"Historical contact date: {entry.get('historical_date', 'Not supplied')}",
            f"Channel: {entry['channel']}",
            f"Communication: {entry['message']}",
            f"Promised or next action: {entry['next_action'] or 'Not recorded'}",
            f"Receiving team: {entry['next_team'] or 'Not recorded'}",
            "Requested / acknowledged demo individual: "
            + ((entry.get("individual_owner") or {}).get("name", "Not selected")),
            "Individual labels are demo routing; acknowledgement is recorded by the signed-in author, not verified external employee acceptance.",
            f"Deadline: {entry['due_at'] or 'Not recorded'}",
            f"Related entry: {entry['related_id'] or 'None'}",
            "Source references: "
            + (
                ", ".join(entry["source_ids"])
                or "Author report; no supporting attachment"
            ),
            "A recorded statement or promise is not proof that a device, payment, or external ticket changed state.",
        ]
    )
    return {
        "id": entry["id"],
        "case_id": entry["case_id"],
        "kind": "communication",
        "title": entry["event_type"].capitalize() + " · " + entry["team"],
        "source": entry["origin"],
        "date": entry["recorded_at"][:10],
        "text": text,
        "facts": {},
        "synthetic": entry["synthetic"],
    }


def seed_history():
    """Import only the three dated statements actually present in the fictional PDF."""
    import os

    if os.getenv("CCI_SEED_HISTORY", "true") != "true":
        return
    import json

    from app.config import data_dir

    docs = json.loads((data_dir() / "documents.json").read_text())
    source = next((d for d in docs if d["id"] == "CASE-1001-conversation"), None)
    if not source:
        return
    statements = [
        (
            "2026-09-15",
            "promise",
            "Customer service",
            "September 15, customer: I returned the device and tracking shows delivered. Agent: I will ask the warehouse.",
            "Ask the warehouse for the intake evidence.",
        ),
        (
            "2026-09-28",
            "contact",
            "Customer service",
            "September 28, agent: Your refund is completed. No payment reference was attached to that statement.",
            "Verify the completion claim against processor and bank evidence.",
        ),
        (
            "2026-10-15",
            "update",
            "Store support",
            "October 15, store associate: Customer has repeated this history many times; please reconcile receiving and payment records.",
            "Reconcile receiving and payment records.",
        ),
    ]
    with connect(db_path()) as db:
        for date, kind, team, message, action in statements:
            if message not in source["text"]:
                continue
            when = date + "T12:00:00+00:00"
            entry = {
                "id": "COM-SEED-1001-" + date,
                "case_id": "CASE-1001",
                "author": "Historical employee (fictional)",
                "author_role": "customer_service",
                "team": team,
                "channel": "Phone" if team == "Customer service" else "Store visit",
                "event_type": kind,
                "message": message,
                "next_action": action,
                "next_team": "",
                "due_at": "",
                "related_id": "",
                "source_ids": [source["id"]],
                "recorded_at": datetime.now(timezone.utc).isoformat(),
                "historical_date": date,
                "minimum_role": "customer_service",
                "origin": "Imported from synthetic support conversation PDF; precise contact time and employee name are not supplied",
                "synthetic": True,
            }
            db.execute(
                "INSERT INTO communications VALUES (?,?,?,?) ON CONFLICT (id) DO NOTHING",
                (
                    entry["id"],
                    "CASE-1001",
                    datetime.fromisoformat(when).timestamp(),
                    json.dumps(entry),
                ),
            )
