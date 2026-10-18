"""Persistent, isolated training journeys. No network or payment capabilities."""

import hashlib
import json
from datetime import datetime, timezone
from uuid import uuid4

from app.config import runtime_dir
from app.storage.database import connect, private_local_file, remote

NOTICE = "SIMULATION ONLY — fictional training data. No external warehouse, bank, payment, email or ticket system is connected. No money moves. Original case evidence and balances are unchanged."
STEPS = [
    ("purchase", "Purchase captured", "Customer service", "Taylor Brooks"),
    ("return", "Return authorized", "Return logistics", "Casey Reed"),
    ("delivered", "Carrier delivery", "Return logistics", "Casey Reed"),
    ("received", "Warehouse receipt", "Return reconciliation", "Alex Morgan"),
    ("verified", "Device verified", "Return reconciliation", "Sam Rivera"),
    ("approved", "Refund approved", "Payments operations", "Robin Patel"),
    ("submitted", "Refund submitted", "Payments operations", "Robin Patel"),
    ("bank_received", "Bank acknowledgement", "Bank refund operations", "Drew Chen"),
    ("posted", "Refund posted", "Case review", "Avery Quinn"),
]


def path():
    return runtime_dir() / "simulation.sqlite"


def initialize():
    with connect(path()) as db:
        db.execute(
            "CREATE TABLE IF NOT EXISTS simulation_runs (id TEXT PRIMARY KEY, username TEXT NOT NULL, case_id TEXT NOT NULL, created TEXT NOT NULL, payload TEXT NOT NULL)"
        )
        db.execute(
            "CREATE INDEX IF NOT EXISTS simulation_owner ON simulation_runs(username,case_id,created)"
        )
    private_local_file(path())


def lock(db, user, cid):
    if remote():
        key = int(
            hashlib.sha256((user.username + ":" + cid).encode()).hexdigest()[:14], 16
        )
        db.execute("SELECT pg_advisory_xact_lock(?)", (key,))
    else:
        db.execute("BEGIN IMMEDIATE")


def owned(db, user, cid, rid=None):
    if not user.can_access_case(cid):
        raise ValueError("Simulation not found.")
    sql = "SELECT payload FROM simulation_runs WHERE username=? AND case_id=?"
    params = [user.username, cid]
    if rid:
        sql += " AND id=?"
        params.append(rid)
    row = db.execute(sql + " ORDER BY created DESC LIMIT 1", tuple(params)).fetchone()
    return json.loads(row[0]) if row else None


def event(run, action, author, description):
    run["events"].append(
        {
            "id": f"SIM-{run['id']}-{len(run['events']) + 1}",
            "action": action,
            "recorded_at": datetime.now(timezone.utc).isoformat(),
            "recorded_by": author,
            "description": description,
            "simulation": True,
        }
    )
    run["revision"] += 1


def create(user, cid):
    if not user.can_access_case(cid):
        raise ValueError("Simulation not found.")
    with connect(path()) as db:
        lock(db, user, cid)
        count = db.execute(
            "SELECT COUNT(*) FROM simulation_runs WHERE username=? AND case_id=?",
            (user.username, cid),
        ).fetchone()[0]
        if count >= 20:
            raise ValueError(
                "This demo allows 20 training runs per user and case. Existing runs remain available."
            )
        run = {
            "id": uuid4().hex,
            "case_id": cid,
            "created": datetime.now(timezone.utc).isoformat(),
            "revision": 0,
            "amount_cents": 109900,
            "device_id": "TRAINING-DEVICE-001",
            "order_id": "TRAINING-ORDER-001",
            "stage": "delivered",
            "issue": "",
            "trace": "",
            "events": [],
        }
        event(
            run,
            "purchase",
            user.username,
            "Simulated purchase captured: USD 1,099.00 for TRAINING-DEVICE-001. No real purchase or debit occurred.",
        )
        event(
            run,
            "return",
            user.username,
            "Simulated return authorized and shipping label issued for TRAINING-ORDER-001.",
        )
        event(
            run,
            "delivered",
            user.username,
            "Simulated carrier delivery recorded. Warehouse intake and device verification are not yet evidenced in this training run.",
        )
        db.execute(
            "INSERT INTO simulation_runs VALUES (?,?,?,?,?)",
            (run["id"], user.username, cid, run["created"], json.dumps(run)),
        )
    return project(run)


def latest(user, cid):
    with connect(path()) as db:
        run = owned(db, user, cid)
    return project(run) if run else None


def advance(user, cid, rid, revision, action):
    with connect(path()) as db:
        lock(db, user, cid)
        run = owned(db, user, cid, rid)
        if not run:
            raise ValueError("Simulation not found.")
        if run["revision"] != revision:
            raise ValueError(
                "This simulation changed. Refresh before taking the next step."
            )
        if len(run["events"]) >= 100:
            raise ValueError("This training run has reached its 100-event limit.")
        next_step = next_action(run)
        if (
            action == "device_mismatch"
            and next_step == "verified"
            and run["issue"] != "device_mismatch"
        ):
            run["issue"] = "device_mismatch"
            event(
                run,
                action,
                user.username,
                "SIMULATED EXCEPTION: scanned TRAINING-DEVICE-999 differs from expected TRAINING-DEVICE-001. Refund approval is blocked; warehouse reconciliation must resolve the discrepancy.",
            )
        elif (
            action == "bank_info_required"
            and next_step == "bank_received"
            and run["issue"] != "bank_info_required"
        ):
            run["issue"] = "bank_info_required"
            event(
                run,
                action,
                user.username,
                "SIMULATED EXCEPTION: bank operations requests the processor trace reference. No posted credit is evidenced yet; Payments operations owns the information request.",
            )
        elif action != next_step or not next_step:
            raise ValueError("Complete the required previous simulation step first.")
        else:
            messages = {
                "received": "Simulated warehouse intake scan links the parcel to TRAINING-ORDER-001. Receipt alone does not verify the device.",
                "verified": "Simulated warehouse reconciliation confirms TRAINING-DEVICE-001 matches the return. Any prior mismatch is resolved in this new event; the original exception remains in history.",
                "approved": "Simulated refund approval recorded for USD 1,099.00. Approval does not establish processor submission or bank posting.",
                "submitted": "Simulated processor refund submission recorded for USD 1,099.00. Trace reference: TRAINING-TRACE-"
                + run["id"][:12]
                + ". Bank acknowledgement and posting are not yet evidenced.",
                "bank_received": "Simulated bank acknowledgement recorded using the supplied training trace. Any information request is resolved. This acknowledgement is not a posted credit.",
                "posted": "Simulated statement credit of USD 1,099.00 matches the training order, device and trace. Training journey complete; no actual bank credit or money movement occurred.",
            }
            run["stage"] = action
            run["issue"] = ""
            if action == "submitted":
                run["trace"] = "TRAINING-TRACE-" + run["id"][:12]
            event(run, action, user.username, messages[action])
        db.execute(
            "UPDATE simulation_runs SET payload=? WHERE id=? AND username=? AND case_id=?",
            (json.dumps(run), rid, user.username, cid),
        )
    return project(run)


def next_action(run):
    names = [s[0] for s in STEPS]
    i = names.index(run["stage"])
    return names[i + 1] if i < len(names) - 1 else None


def project(run):
    i = [s[0] for s in STEPS].index(run["stage"])
    following = STEPS[i + 1] if i + 1 < len(STEPS) else None
    return {
        **run,
        "simulation": True,
        "notice": NOTICE,
        "next_action": following[0] if following else None,
        "next_label": following[1] if following else None,
        "next_team": "Payments operations"
        if run["issue"] == "bank_info_required"
        else following[2]
        if following
        else "Case review",
        "next_person": "Robin Patel"
        if run["issue"] == "bank_info_required"
        else following[3]
        if following
        else "Avery Quinn",
        "milestones": [
            {"action": s[0], "label": s[1], "complete": j <= i}
            for j, s in enumerate(STEPS)
        ],
        "approved_cents": run["amount_cents"] if i >= 5 else 0,
        "submitted_cents": run["amount_cents"] if i >= 6 else 0,
        "posted_cents": run["amount_cents"] if i >= 8 else 0,
        "history_available": True,
    }


def source(user, cid, rid, eid):
    with connect(path()) as db:
        run = owned(db, user, cid, rid)
    if not run:
        return None
    record = next((e for e in run["events"] if e["id"] == eid), None)
    if not record:
        return None
    return {
        "id": eid,
        "case_id": cid,
        "kind": "simulation_event",
        "title": "SIMULATION · " + record["action"],
        "source": "Internal training simulator; no external system",
        "date": record["recorded_at"][:10],
        "text": NOTICE
        + "\n\n"
        + record["description"]
        + "\nRecorded by: "
        + record["recorded_by"]
        + "\nRecorded at: "
        + record["recorded_at"],
        "synthetic": True,
    }


def brief(user, cid, rid):
    with connect(path()) as db:
        run = owned(db, user, cid, rid)
    if not run:
        raise ValueError("Simulation not found.")
    view = project(run)
    return {
        "simulation": True,
        "notice": NOTICE,
        "claims": [
            {"text": e["description"], "source_id": e["id"]} for e in run["events"]
        ],
        "next_step": (
            f"{view['next_team']} · {view['next_person']}: " + view["next_label"]
        )
        if view["next_action"]
        else "Training refund posted. Real case evidence and balances remain unchanged.",
    }
