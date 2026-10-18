"""LangChain Documents/splitting, local embeddings, BM25 and persisted dense index."""

import hashlib
import json
import os
import re
from functools import lru_cache
from threading import Lock
import tiktoken
from pathlib import Path
import numpy as np
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from rank_bm25 import BM25Okapi
from ..security.policy import minimum_role, role_allows
from ..config import index_dir

ROOT = Path(__file__).resolve().parents[2]
os.environ.setdefault("HF_HOME", str(ROOT / "work" / "huggingface"))
os.environ.setdefault("HF_HUB_DISABLE_XET", "1")
os.environ.setdefault("TIKTOKEN_CACHE_DIR", str(ROOT / "work" / "tiktoken"))
TOKEN = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
STOP = set(
    "a an the is are was were be been being what where when why how who which did does do has have had of for to from in on at by with and or it its this that these those me my your please can could would should tell about after before".split()
)


def tokens(text):
    return [w for w in TOKEN.findall(text.lower()) if w not in STOP]


class LocalEmbeddings(Embeddings):
    def __init__(self):
        from fastembed import TextEmbedding

        self.model = TextEmbedding(
            "BAAI/bge-small-en-v1.5",
            cache_dir=str(ROOT / os.getenv("EMBEDDING_CACHE", "work/models")),
            threads=2,
        )
        self.memo = {}

    def embed_documents(self, texts):
        missing = list(dict.fromkeys(t for t in texts if t not in self.memo))
        if missing:
            values = [v.tolist() for v in self.model.embed(missing, batch_size=8)]
            self.memo.update(zip(missing, values))
        return [self.memo[t] for t in texts]

    def embed_query(self, text):
        return next(self.model.query_embed(text)).tolist()


class CorpusLoader:
    def load(self):
        from ..documents.loader import load_pdf_documents

        return load_pdf_documents()


def chunks_for(documents, strategy="structure", embeddings=None):
    splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
        encoding_name="cl100k_base", chunk_size=350, chunk_overlap=40
    )
    encoder = tiktoken.get_encoding("cl100k_base")
    result = []
    for d in documents:
        if strategy == "fixed":
            pieces = splitter.split_text(d.page_content)
        elif strategy == "semantic":
            # Sentence/paragraph embedding-distance segmentation; distinct from table-aware sections.
            units = re.split(r"(?<=[.!?])\s+|\n\n", d.page_content)
            units = [
                piece
                for u in units
                if u.strip()
                for piece in splitter.split_text(u.strip())
            ]
            vectors = np.array(embeddings.embed_documents(units))
            vectors = vectors / np.maximum(
                np.linalg.norm(vectors, axis=1, keepdims=True), 1e-9
            )
            distances = 1 - np.sum(vectors[:-1] * vectors[1:], axis=1)
            threshold = float(np.percentile(distances, 70)) if len(distances) else 2
            pieces = []
            group = []
            for j, u in enumerate(units):
                group.append(u)
                if j == len(units) - 1 or distances[j] > threshold:
                    pieces.extend(splitter.split_text("\n\n".join(group)))
                    group = []
        else:
            # Preserve Markdown tables as blocks; repeat header when a table exceeds the hard limit.
            blocks = re.split(r"\n\n+", d.page_content)
            pieces = []
            group = []
            for block in blocks:
                if block.lstrip().startswith("|"):
                    if group:
                        pieces.extend(splitter.split_text("\n\n".join(group)))
                        group = []
                    lines = block.splitlines()
                    header = "\n".join(lines[:2])
                    body = lines[2:]
                    table = header
                    for row in body:
                        if len(encoder.encode(table + "\n" + row)) > 350:
                            pieces.append(table)
                            table = header
                        table += "\n" + row
                    pieces.append(table)
                else:
                    group.append(block)
            if group:
                pieces.extend(splitter.split_text("\n\n".join(group)))
        for j, piece in enumerate(pieces):
            result.append(
                Document(
                    page_content=piece,
                    metadata={
                        **d.metadata,
                        "chunk_id": f"{d.metadata['id']}:p{d.metadata.get('page', 0)}:c{j}",
                        "strategy": strategy,
                    },
                )
            )
    return result


RERANK_MODEL = "Xenova/ms-marco-MiniLM-L-6-v2"
RERANK_LOCK = Lock()


@lru_cache(maxsize=1)
def get_reranker():
    from fastembed.rerank.cross_encoder import TextCrossEncoder

    return TextCrossEncoder(
        RERANK_MODEL,
        cache_dir=str(ROOT / os.getenv("EMBEDDING_CACHE", "work/models")),
        threads=2,
    )


def reranker_passage(document):
    # Source identity matters when multiple ledgers contain identical amounts.
    return f"Document: {document.metadata.get('title', '')}\nSource: {document.metadata.get('source', '')}\nCase: {document.metadata.get('case_id') or 'public guidance'}\n\n{document.page_content}"


class HybridIndex:
    def __init__(
        self, documents=None, embeddings=None, strategy="structure", backend=None
    ):
        self.backend = backend or os.getenv("VECTOR_BACKEND", "local")
        if self.backend not in ("local", "pinecone", "pinecone-strict"):
            raise ValueError("Unsupported vector backend")
        self.strategy = strategy
        self.embeddings = embeddings or LocalEmbeddings()
        source_docs = documents if documents is not None else CorpusLoader().load()
        folder = index_dir()
        folder.mkdir(parents=True, exist_ok=True)
        segmentation_key = hashlib.sha256(
            (
                "segment-v3-cl100k-bge-350-40-p70-"
                + strategy
                + json.dumps(
                    [(d.page_content, d.metadata) for d in source_docs], sort_keys=True
                )
            ).encode()
        ).hexdigest()[:20]
        segmentation_path = folder / f"{segmentation_key}.chunks.json"
        if segmentation_path.exists():
            self.docs = [
                Document(page_content=d["text"], metadata=d["metadata"])
                for d in json.loads(segmentation_path.read_text())
            ]
        else:
            self.docs = chunks_for(source_docs, strategy, self.embeddings)
            temporary = folder / f"{segmentation_key}.{os.getpid()}.tmp.json"
            temporary.write_text(
                json.dumps(
                    [
                        {"text": d.page_content, "metadata": d.metadata}
                        for d in self.docs
                    ]
                )
            )
            temporary.replace(segmentation_path)
        self.lexical = [tokens(d.page_content) for d in self.docs]
        payload = json.dumps(
            [(d.page_content, d.metadata) for d in self.docs], sort_keys=True
        )
        fingerprint = hashlib.sha256(
            ("bge-small-en-v1.5-v1" + payload).encode()
        ).hexdigest()[:20]
        folder = index_dir()
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"{fingerprint}.npy"
        if path.exists():
            self.vectors = np.load(path, allow_pickle=False)
        else:
            self.vectors = np.array(
                self.embeddings.embed_documents([d.page_content for d in self.docs]),
                dtype=np.float32,
            )
            temp = folder / f"{fingerprint}.{os.getpid()}.tmp.npy"
            np.save(temp, self.vectors)
            temp.replace(path)
        self.fingerprint = fingerprint
        self.cloud = None
        if not any(d.metadata.get("kind") == "user_upload" for d in self.docs):
            from .pinecone_store import PineconeDense

            self.cloud = PineconeDense(self.docs, fingerprint, strategy)
        norms = np.linalg.norm(self.vectors, axis=1, keepdims=True)
        self.vectors = self.vectors / np.maximum(norms, 1e-9)

    def search(self, query, case_id, k=6, rerank=True, role="head"):
        ids = [
            i
            for i, d in enumerate(self.docs)
            if d.metadata["case_id"] in (case_id, None)
            and role_allows(
                role, minimum_role(d.metadata.get("kind", "public_guidance"))
            )
        ]
        if not ids:
            return []
        lex = BM25Okapi([self.lexical[i] for i in ids])
        words = tokens(query)
        sparse = lex.get_scores(words)
        q = np.array(self.embeddings.embed_query(query))
        q = q / max(np.linalg.norm(q), 1e-9)
        dense = self.vectors[ids] @ q
        a = np.argsort(-sparse)[:20]
        b = np.argsort(-dense)[:20]
        backend_used = "local"
        if self.backend != "local" and self.cloud is not None:
            try:
                positions = self.cloud.ranking(q, case_id, role, ids)
                local_positions = {position: j for j, position in enumerate(ids)}
                b = [local_positions[position] for position in positions]
                backend_used = "pinecone"
            except Exception:
                # Never expose provider errors/credentials; controlled experiments fail instead.
                if self.backend == "pinecone-strict":
                    raise RuntimeError(
                        "Pinecone unavailable; strict evaluation refuses fallback"
                    ) from None
                backend_used = "local-fallback"
        elif self.backend == "pinecone-strict":
            raise RuntimeError("Private uploads cannot use the cloud benchmark backend")
        scores = {}
        for ranking in (a, b):
            for rank, index in enumerate(ranking):
                scores[int(index)] = scores.get(int(index), 0) + 1 / (60 + rank)
        ordered = sorted(scores, key=scores.get, reverse=True)
        # Same fused top-20 candidate pool for both paired experimental conditions.
        ordered = ordered[:20]
        cross_scores = {}
        if rerank:
            model = get_reranker()
            with RERANK_LOCK:
                values = list(
                    model.rerank(
                        query,
                        [reranker_passage(self.docs[ids[j]]) for j in ordered],
                        batch_size=8,
                    )
                )
            cross_scores = dict(zip(ordered, map(float, values)))
            ordered.sort(key=lambda j: cross_scores[j], reverse=True)

        return [
            dict(
                **self.docs[ids[j]].metadata,
                text=self.docs[ids[j]].page_content,
                score=round(cross_scores.get(j, float(scores[j])), 5),
                fusion_score=round(float(scores[j]), 5),
                reranker=RERANK_MODEL if rerank else None,
                retrieval_backend=backend_used,
                dense_score=round(float(dense[j]), 4),
                matched_terms=sorted(set(words) & set(self.lexical[ids[j]])),
            )
            for j in ordered[:k]
        ]
