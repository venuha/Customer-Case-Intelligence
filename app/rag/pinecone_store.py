"""Optional dense search for the versioned, fictional PDF corpus only.

Synchronization is explicit; requests never create indexes or publish uploads.
Local chunk metadata remains authoritative for access checks and returned text.
"""

import hashlib
import os
from functools import lru_cache

from ..security.policy import ROLES, minimum_role


class PineconeUnavailable(RuntimeError):
    pass


def vector_id(document):
    return hashlib.sha256(document.metadata["chunk_id"].encode()).hexdigest()


def configured():
    return bool(os.getenv("PINECONE_API_KEY") and os.getenv("PINECONE_INDEX_NAME"))


@lru_cache(maxsize=1)
def connect():
    if not configured():
        raise PineconeUnavailable("Pinecone credentials or index name missing")
    from pinecone import Pinecone
    import httpx
    import re

    client = Pinecone(api_key=os.environ["PINECONE_API_KEY"])
    name = os.environ["PINECONE_INDEX_NAME"]
    if not re.fullmatch(r"[a-z0-9-]{1,45}", name):
        raise PineconeUnavailable("Invalid index name")
    # Bounded control-plane lookup: never let a missing cloud stall local fallback.
    response = httpx.get(
        f"https://api.pinecone.io/indexes/{name}",
        headers={
            "Api-Key": os.environ["PINECONE_API_KEY"],
            "X-Pinecone-API-Version": "2025-10",
        },
        timeout=5,
    )
    response.raise_for_status()
    description = response.json()
    if description.get("dimension") != 384 or description.get("metric") != "cosine":
        raise PineconeUnavailable("Pinecone index must use 384 dimensions and cosine")
    if not description.get("status", {}).get("ready"):
        raise PineconeUnavailable("Pinecone index is not ready")
    host = description["host"]
    if not re.fullmatch(r"[a-z0-9.-]+\.pinecone\.io", host):
        raise PineconeUnavailable("Unexpected index host")
    return client.Index(host=host)


class PineconeDense:
    def __init__(self, documents, fingerprint, strategy):
        if any(d.metadata.get("kind") == "user_upload" for d in documents):
            raise PineconeUnavailable("Private uploads remain local")
        self.documents = documents
        self.namespace = f"cci-{strategy}-{fingerprint}"
        self.positions = {vector_id(d): i for i, d in enumerate(documents)}

    def sync(self, vectors):
        index = connect()
        for start in range(0, len(self.documents), 100):
            batch = []
            for i in range(start, min(start + 100, len(self.documents))):
                doc = self.documents[i]
                batch.append(
                    {
                        "id": vector_id(doc),
                        "values": vectors[i].tolist(),
                        "metadata": {
                            "text": doc.page_content,
                            "chunk_id": doc.metadata["chunk_id"],
                            "source_id": doc.metadata["id"],
                            "case_scope": doc.metadata.get("case_id") or "__public__",
                            "role_rank": ROLES[
                                minimum_role(doc.metadata.get("kind", ""))
                            ],
                            "page": doc.metadata.get("page", 0),
                            "strategy": doc.metadata["strategy"],
                        },
                    }
                )
            index.upsert(vectors=batch, namespace=self.namespace, timeout=15)
        return len(self.documents)

    def ranking(self, query_vector, case_id, role, allowed_ids):
        if role not in ROLES:
            raise PineconeUnavailable("Unknown role")
        index = connect()
        stats = index.describe_index_stats(timeout=5)
        namespace = stats.namespaces.get(self.namespace)
        if namespace is None or namespace.vector_count != len(self.documents):
            raise PineconeUnavailable("Namespace absent or not fully synchronized")
        response = index.query(
            vector=query_vector.tolist(),
            top_k=min(20, len(allowed_ids)),
            namespace=self.namespace,
            include_metadata=False,
            filter={
                "$and": [
                    {"case_scope": {"$in": [case_id, "__public__"]}},
                    {"role_rank": {"$lte": ROLES[role]}},
                ]
            },
            timeout=5,
        )
        # Fail closed on unknown IDs or an access-filter violation; never trust remote text.
        allowed = set(allowed_ids)
        positions = []
        for match in response.matches:
            position = self.positions.get(match.id)
            if position is None or position not in allowed or position in positions:
                raise PineconeUnavailable("Remote result failed local scope validation")
            positions.append(position)
        if not positions:
            raise PineconeUnavailable("No cloud matches; use local evidence")
        return positions
