from types import SimpleNamespace as NS

import numpy as np
import pytest
from langchain_core.documents import Document
from app.rag import pinecone_store as store
from app.rag.retrieval import HybridIndex


def documents():
    return [
        Document(
            page_content="refund evidence",
            metadata={
                "chunk_id": str(i),
                "id": str(i),
                "case_id": cid,
                "kind": kind,
                "strategy": "fixed",
            },
        )
        for i, cid, kind in [
            (0, "CASE-1001", "order"),
            (1, "CASE-1001", "statement"),
            (2, "CASE-1002", "order"),
            (3, None, "public_guidance"),
        ]
    ]


class Remote:
    def __init__(self, docs):
        self.docs = docs
        self.matches = [
            NS(id=store.vector_id(docs[0])),
            NS(id=store.vector_id(docs[3])),
        ]
        self.count = len(docs)
        self.batches = []

    def describe_index_stats(self, **kwargs):
        return NS(namespaces={self.namespace: NS(vector_count=self.count)})

    def query(self, **kwargs):
        self.query_args = kwargs
        return NS(matches=self.matches)

    def upsert(self, **kwargs):
        self.batches.append(kwargs)


def test_cloud_filters_and_local_scope_validation(monkeypatch):
    docs = documents()
    cloud = store.PineconeDense(docs, "test", "fixed")
    remote = Remote(docs)
    remote.namespace = cloud.namespace
    monkeypatch.setattr(store, "connect", lambda: remote)
    assert cloud.ranking(np.ones(384), "CASE-1001", "customer_service", [0, 3]) == [
        0,
        3,
    ]
    assert remote.query_args["filter"] == {
        "$and": [
            {"case_scope": {"$in": ["CASE-1001", "__public__"]}},
            {"role_rank": {"$lte": 0}},
        ]
    }
    for bad in [1, 2]:
        remote.matches = [NS(id=store.vector_id(docs[bad]))]
        with pytest.raises(store.PineconeUnavailable):
            cloud.ranking(np.ones(384), "CASE-1001", "customer_service", [0, 3])
    remote.matches = [NS(id="unknown")]
    with pytest.raises(store.PineconeUnavailable):
        cloud.ranking(np.ones(384), "CASE-1001", "head", [0, 1, 3])


def test_sync_idempotent_and_private_upload_rejected(monkeypatch):
    docs = documents()
    cloud = store.PineconeDense(docs, "test", "semantic")
    remote = Remote(docs)
    monkeypatch.setattr(store, "connect", lambda: remote)
    assert cloud.sync(np.ones((4, 384))) == 4
    cloud.sync(np.ones((4, 384)))
    assert remote.batches[0] == remote.batches[1]
    assert remote.batches[0]["vectors"][1]["metadata"]["role_rank"] == 2
    docs[0].metadata["kind"] = "user_upload"
    with pytest.raises(store.PineconeUnavailable):
        store.PineconeDense(docs, "test", "fixed")


def test_unsynced_namespace_rejected(monkeypatch):
    docs = documents()
    cloud = store.PineconeDense(docs, "test", "fixed")
    remote = Remote(docs)
    remote.namespace = cloud.namespace
    remote.count = 1
    monkeypatch.setattr(store, "connect", lambda: remote)
    with pytest.raises(store.PineconeUnavailable):
        cloud.ranking(np.ones(384), "CASE-1001", "head", [0, 1, 3])


def index_with_cloud(cloud, backend):
    # Exercise the real hybrid search without downloading models or writing caches.
    index = HybridIndex.__new__(HybridIndex)
    index.docs = documents()
    index.lexical = [["refund", "evidence"] for d in index.docs]
    index.vectors = np.ones((4, 384)) / np.sqrt(384)
    index.embeddings = NS(embed_query=lambda q: np.ones(384).tolist())
    index.backend = backend
    index.cloud = cloud
    return index


def test_local_fallback_and_strict_evaluation():
    class Broken:
        def ranking(self, *args):
            raise RuntimeError("sensitive provider detail")

    index = index_with_cloud(Broken(), "pinecone")
    hits = index.search("refund", "CASE-1001", role="customer_service", rerank=False)
    assert {h["id"] for h in hits} == {"0", "3"}
    assert all(h["retrieval_backend"] == "local-fallback" for h in hits)
    index.backend = "pinecone-strict"
    with pytest.raises(
        RuntimeError, match="strict evaluation refuses fallback"
    ) as error:
        index.search("refund", "CASE-1001", role="head", rerank=False)
    assert "sensitive" not in str(error.value)


def test_successful_cloud_path():
    index = index_with_cloud(NS(ranking=lambda *args: [3, 0]), "pinecone")
    hits = index.search("refund", "CASE-1001", role="customer_service", rerank=False)
    assert all(h["retrieval_backend"] == "pinecone" for h in hits)


def test_connect_checks_dimension_and_bounds_provider_lookup(monkeypatch):
    import httpx
    import pinecone

    monkeypatch.setenv("PINECONE_API_KEY", "mock-infrastructure-value")
    monkeypatch.setenv("PINECONE_INDEX_NAME", "customer-case-intelligence")
    response = {
        "dimension": 768,
        "metric": "cosine",
        "status": {"ready": True},
        "host": "test.svc.pinecone.io",
    }

    class Response:
        def raise_for_status(self):
            pass

        def json(self):
            return response

    def get(url, **kwargs):
        assert url == "https://api.pinecone.io/indexes/customer-case-intelligence"
        assert kwargs["timeout"] == 5
        return Response()

    monkeypatch.setattr(httpx, "get", get)
    monkeypatch.setattr(
        pinecone, "Pinecone", lambda **kwargs: NS(Index=lambda **kwargs: "mock-index")
    )
    store.connect.cache_clear()
    with pytest.raises(store.PineconeUnavailable, match="384"):
        store.connect()
    response["dimension"] = 384
    assert store.connect() == "mock-index"
    store.connect.cache_clear()
    response["host"] = "untrusted.example"
    with pytest.raises(store.PineconeUnavailable, match="host"):
        store.connect()
    store.connect.cache_clear()
