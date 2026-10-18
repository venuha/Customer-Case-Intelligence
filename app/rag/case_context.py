"""Scoped communications and broad summaries supplement the existing hybrid retriever."""

import re

from .retrieval import tokens
from app.domain.directory import routing_question


def is_summary(question):
    return bool(
        re.search(
            r"summari[sz]|brief|what happened|so far|case history|promis|which team|current team|who owns",
            question,
            re.I,
        )
    )


def opening(text):
    # The PDF extractor emits the title as its first paragraph. Keep the actual
    # opening facts/table too, stopping before the expanded provenance boilerplate.
    return re.split(r"(?:## )?Record scope and provenance", text, maxsplit=1)[
        0
    ].strip()[:3000]


def evidence(document, text=None):
    text = text if text is not None else document["text"]
    return {
        **document,
        "text": text,
        "chunk_id": document["id"] + ":case-context",
        "matched_terms": ["case context"],
        "retrieval_backend": "scoped-case-context",
    }


class ContextIndex:
    def __init__(self, base, documents):
        self.base = base
        self.documents = documents

    def search(self, question, cid, **kwargs):
        hits = self.base.search(question, cid, **kwargs)
        if is_summary(question):
            # Preserve milestone coverage; similarity-only top-k can omit the purchase/return.
            case_docs = [d for d in self.documents if d["case_id"] == cid]
            return [
                evidence(
                    d, opening(d["text"]) if d["kind"] != "communication" else d["text"]
                )
                for d in case_docs
            ]
        words = set(tokens(question))
        comms = [
            d
            for d in self.documents
            if d["case_id"] == cid and d["kind"] == "communication"
        ]
        comms.sort(key=lambda d: len(words & set(tokens(d["text"]))), reverse=True)
        routing = (
            [
                evidence(d)
                for d in self.documents
                if d["kind"] == "team_directory" and d["case_id"] == cid
            ]
            if routing_question(question)
            else []
        )
        return (
            routing
            + hits
            + [evidence(d) for d in comms[:8] if words & set(tokens(d["text"]))]
        )


def complete_brief(answer, evidence_items):
    """Ensure extractive stage coverage even if generated citations were rejected."""
    kinds = {
        "order": "Purchase",
        "payment": "Purchase payment",
        "return": "Return request",
        "shipping": "Carrier delivery",
        "inspection": "Warehouse inspection",
        "approval": "Refund approval",
        "refund": "Refund submission",
        "conversation": "Customer contacts and statements",
        "bank_status": "Bank evidence",
        "statement": "Supplied statement",
        "communication": "Shared communication",
    }
    claims = list(answer["claims"])
    for item in evidence_items:
        if item["kind"] not in kinds:
            continue
        text = item["text"]
        if item["kind"] == "communication":
            line = next(
                (
                    line
                    for line in text.splitlines()
                    if line.startswith("Communication: ")
                ),
                text,
            )
            quote = line[:230]
        else:
            paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
            if item["kind"] == "order":
                quote = next((p for p in paragraphs if p.startswith("|")), text)[:230]
            else:
                candidates = [
                    p
                    for p in paragraphs
                    if "." in p
                    and "Snapshot:" not in p
                    and not p.startswith("FICTIONAL")
                ]
                quote = (candidates[0] if candidates else text)[:230]
        if quote and not any(
            c["source_id"] == item["id"] and c["quote"] == quote for c in claims
        ):
            claims.append(
                {
                    "text": kinds[item["kind"]] + ": " + quote,
                    "source_id": item["id"],
                    "quote": quote,
                }
            )
    return {**answer, "claims": claims}
