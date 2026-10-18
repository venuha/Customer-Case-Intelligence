"""Single server-side policy used by API projection, RAG and source downloads."""

from dataclasses import dataclass

ROLES = {"customer_service": 0, "supervisor": 1, "head": 2}
ROLE_LABELS = {
    "customer_service": "Customer service",
    "supervisor": "Supervisor",
    "head": "Head of operations",
}
KIND_ROLES = {
    "team_directory": "customer_service",
    "communication": "customer_service",
    "user_upload": "customer_service",
    "order": "customer_service",
    "payment": "supervisor",
    "return": "customer_service",
    "shipping": "customer_service",
    "conversation": "customer_service",
    "bank_status": "customer_service",
    "public_guidance": "customer_service",
    "routing": "supervisor",
    "inspection": "supervisor",
    "approval": "supervisor",
    "refund": "supervisor",
    "statement": "head",
    "account_history": "head",
    "bank_response": "head",
}


def minimum_role(kind):
    return KIND_ROLES.get(kind, "head")


def role_allows(role, required):
    return role in ROLES and required in ROLES and ROLES[role] >= ROLES[required]


@dataclass(frozen=True)
class Principal:
    username: str
    role: str
    case_ids: tuple[str, ...]

    def can_access_case(self, cid):
        return cid in self.case_ids

    def can_read(self, document):
        return (
            document.get("case_id") is None or self.can_access_case(document["case_id"])
        ) and role_allows(self.role, minimum_role(document.get("kind", "")))

    def public(self):
        return {
            "username": self.username,
            "role": self.role,
            "role_label": ROLE_LABELS[self.role],
        }


def visible_documents(principal, documents, cid=None):
    return [
        d
        for d in documents
        if (cid is None or d["case_id"] == cid) and principal.can_read(d)
    ]


def project_investigation(principal, value):
    result = dict(value)
    if principal.role != "head":
        result["provisional_cents"] = None
    if principal.role == "customer_service":
        # Source-derived bank summary is separately approved for support sharing.
        for key in ("approved_cents", "submitted_cents", "provisional_cents"):
            result[key] = None
        result["finance_detail_restricted"] = True
        restricted = {
            "Payment captured",
            "Device verified",
            "Refund approved",
            "Refund submitted",
        }
        result["timeline"] = [
            {**stage, "restricted": True} if stage["label"] in restricted else stage
            for stage in result["timeline"]
        ]
    return result
