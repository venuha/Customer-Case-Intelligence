"""Build only fictional corpus caches into the image; no credentials or user data."""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ["VECTOR_BACKEND"] = "local"
from app.rag.retrieval import HybridIndex, get_reranker

for strategy in ("fixed", "semantic", "structure"):
    index = HybridIndex(strategy=strategy, backend="local")
    print(
        f"Prepared {strategy}: {len(index.docs)} fictional/reference chunks", flush=True
    )
    del index
get_reranker()
