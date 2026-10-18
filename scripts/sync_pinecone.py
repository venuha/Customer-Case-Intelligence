"""Explicitly upload only the fixed fictional corpus; never private uploads."""

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv

load_dotenv(ROOT / ".env")
from app.rag.retrieval import CorpusLoader, HybridIndex, LocalEmbeddings
from app.rag.pinecone_store import configured, connect, PineconeUnavailable


def main():
    if not configured():
        raise SystemExit(
            "Add PINECONE_API_KEY and PINECONE_INDEX_NAME to private .env. No credentials printed."
        )
    try:
        emb = LocalEmbeddings()
        docs = CorpusLoader().load()
        for strategy in ("fixed", "semantic", "structure"):
            index = HybridIndex(docs, emb, strategy, backend="local")
            count = index.cloud.sync(index.vectors)
            ready = False
            for _ in range(12):
                stats = connect().describe_index_stats(timeout=5)
                ns = stats.namespaces.get(index.cloud.namespace)
                if ns is not None and ns.vector_count == count:
                    ready = True
                    break
                time.sleep(2)
            print(
                f"{strategy}: {count} vectors; namespace {index.cloud.namespace}; visible={ready}",
                flush=True,
            )
            if not ready:
                raise SystemExit(
                    "Pinecone writes not yet visible. Retry sync later; app uses local fallback."
                )
    except PineconeUnavailable as error:
        raise SystemExit(str(error)) from None
    except Exception:
        raise SystemExit(
            "Pinecone synchronization failed. Check key permissions, index name, 384 dimensions and cosine. Provider details suppressed."
        ) from None


if __name__ == "__main__":
    main()
