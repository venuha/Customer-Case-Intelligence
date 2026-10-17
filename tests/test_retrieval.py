import json
from pathlib import Path
import numpy as np
import tiktoken
from langchain_core.documents import Document
from app.rag.retrieval import (
    chunks_for,
    CorpusLoader,
    HybridIndex,
    get_reranker,
    RERANK_MODEL,
)

ROOT = Path(__file__).resolve().parents[1]


def test_long_records_actually_split():
    docs = CorpusLoader().load()
    fixed = chunks_for(docs, "fixed")
    assert len(fixed) > len(docs)
    encoder = tiktoken.get_encoding("cl100k_base")
    long_pages = [d for d in docs if len(encoder.encode(d.page_content)) > 350]
    assert long_pages
    for page in long_pages:
        matching = [
            c
            for c in fixed
            if c.metadata["id"] == page.metadata["id"]
            and c.metadata["page"] == page.metadata["page"]
        ]
        assert len(matching) > 1
    assert all(len(encoder.encode(c.page_content)) <= 350 for c in fixed)


def test_table_headers_are_repeated_and_rows_preserved():
    header = "| Date | Amount USD | Reference |\n|---|---:|---|"
    rows = [f"| 2026-09-{j % 28 + 1:02d} | {j}.25 | TX-{j:04d} |" for j in range(50)]
    doc = Document(
        page_content=header + "\n" + "\n".join(rows),
        metadata={"id": "table", "case_id": "CASE-T"},
    )
    chunks = chunks_for([doc], "structure")
    assert len(chunks) > 1
    for chunk in chunks:
        assert chunk.page_content.startswith(header)
        assert (
            len(tiktoken.get_encoding("cl100k_base").encode(chunk.page_content)) <= 350
        )
    for row in rows:
        assert any(row in c.page_content for c in chunks)


def test_semantic_boundaries_use_embedding_distance():
    class Emb:
        def embed_documents(self, texts):
            return [[1, 0] if "warehouse" in t else [0, 1] for t in texts]

    d = Document(
        page_content="The warehouse received a package. The warehouse inspected the device. A refund was submitted. A credit was posted.",
        metadata={"id": "topic", "case_id": "CASE-T"},
    )
    chunks = chunks_for([d], "semantic", Emb())
    assert len(chunks) == 2
    assert "warehouse" in chunks[0].page_content
    assert "refund" in chunks[1].page_content


def test_cross_encoder_jointly_scores_relevance():
    scores = list(
        get_reranker().rerank(
            "Was the merchant refund posted on the bank statement?",
            [
                "A shipping label was created and a package was delivered.",
                "The bank statement shows a posted merchant refund credit of USD 899.00.",
            ],
        )
    )
    assert len(scores) == 2
    assert all(np.isfinite(scores))
    assert scores[1] > scores[0]


def test_reranking_is_case_scoped_and_exposes_model_score():
    index = HybridIndex()
    hits = index.search("Was the merchant refund posted?", "CASE-1002", k=6)
    assert hits
    assert all(h["case_id"] in ("CASE-1002", None) for h in hits)
    assert all(h["reranker"] == RERANK_MODEL for h in hits)
    assert [h["score"] for h in hits] == sorted(
        [h["score"] for h in hits], reverse=True
    )
    assert any(h["score"] != h["fusion_score"] for h in hits)


def test_gold_annotations_are_not_ingested():
    docs = CorpusLoader().load()
    assert not any("evidence_targets" in d.page_content for d in docs)
    assert len({d.metadata["id"] for d in docs}) == 91
    assert all(d.metadata.get("page", 0) > 0 and d.metadata.get("sha256") for d in docs)


def test_allocations_sum_to_control_total():
    raw = json.loads((ROOT / "data/documents.json").read_text())
    for d in raw:
        if d["kind"] not in ("order", "payment", "approval", "refund"):
            continue
        lines = d["text"].split("## Financial allocation table")[1].splitlines()
        amounts = []
        control = None
        from decimal import Decimal

        for line in lines:
            if not line.startswith("| "):
                continue
            cells = [x.strip() for x in line.strip("|").split("|")]
            if len(cells) < 4 or not cells[0].isdigit():
                continue
            value = Decimal(cells[2])
            if cells[1] == "Total for this record":
                control = value
            else:
                amounts.append(value)
        assert sum(amounts) == control


def test_reranker_preserves_parent_source_identity():
    from app.rag.retrieval import reranker_passage

    doc = Document(
        page_content="| Tax allocation | 71.90 |",
        metadata={
            "title": "Order confirmation",
            "source": "Synthetic order",
            "case_id": "CASE-1001",
        },
    )
    passage = reranker_passage(doc)
    assert "Document: Order confirmation" in passage
    assert "Source: Synthetic order" in passage
    assert doc.page_content in passage


def test_order_table_retrieval_uses_the_order_source():
    index = HybridIndex()
    hits = index.search(
        "For order ORD-24001, what tax allocation and control total are listed in the order confirmation financial allocation table?",
        "CASE-1001",
        k=6,
    )
    assert any(
        h["id"] == "CASE-1001-order"
        and "Tax allocation" in h["text"]
        and "Total for this record" in h["text"]
        for h in hits
    )
