> Historical pre-PDF-migration record. See evaluation-pdf.md for the revised corpus experiment when available.

# Controlled financial retrieval experiment

## What is held constant
The same 79 synthetic source documents, four public-reference notes, BGE embedding model, case filter, BM25 implementation, reciprocal-rank-fusion parameters, top-20 shortlist, and top-six passage budget are used across conditions. The 32 original benchmark queries remain unchanged. The exact source corpus and query list are hashed in the result file.

## Conditions
1. Fixed-size recursive chunking, 350-token target and 40-token overlap; hybrid retrieval.
2. Same fixed-size chunks and hybrid candidates; trained MiniLM cross-encoder reranking.
3. Embedding-distance semantic chunking at the 70th percentile of adjacent normalized embedding distances; a 350-token safety splitter; hybrid retrieval.
4. Same semantic chunks and hybrid candidates; trained MiniLM cross-encoder reranking.
5. Section/table-aware chunks with repeated table headers; hybrid retrieval and the same trained cross-encoder.

The semantic method embeds sentence/paragraph units; it does not ask a generative model to choose boundaries. Oversized units are split before embedding. The semantic threshold is fixed before this expanded-corpus evaluation; it is not optimized against the benchmark answers.

## What is measured
- Evidence recall@6: fraction of annotated source-ID-plus-exact-span evidence units found in the six returned passages. Multi-document questions require evidence from each annotated source.
- Evidence precision@6: fraction of the six returned passages containing an annotated evidence span from its designated source.
- Evidence MRR@6: reciprocal rank of the first passage containing an annotated evidence span.
- Document recall@6: supplementary measure of whether the gold source document appears, even when the returned chunk lacks the annotated evidence.
- Warm median and p95 retrieval latency, including reranking where enabled. Model downloads, ingestion, embeddings at index construction, and generation are excluded.

The paired reranking deltas compare conditions 1→2 and 3→4. They change only reranking. Fixed-versus-semantic comparison is evaluated with reranking either absent in both or present in both.

## Annotation integrity and limits
`data/eval/evidence.json` identifies concise evidence spans in the original source portions. The retriever never reads that file. The benchmark contains eight multiple-source questions and 24 single-source questions. Financial tables and unrelated statement entries create harder within-case candidates; cross-case leakage remains prohibited.

This is still a development benchmark on fictional cases, not a statistically representative or independently held-out institutional benchmark. Exact-span grading is conservative: it can miss alternative sufficient passages. Some document text uses shared source-control templates. The expanded-corpus passage metrics must not be compared directly with the earlier short-corpus unique-document metrics.

## Generation assessment
Retrieval evaluation can run without an OpenAI key. Live generated-answer faithfulness requires configured OpenAI access and a separately executed judge run. No faithfulness result is inferred from retrieval scores or quote validation. This project does not claim the reference implementation's RAGAS scores, costs, or universal superiority of semantic chunking.

## Supplementary table probe
`scripts/evaluate_tables.py` adds eight separately reported questions asking for tax allocation and control totals in designated order documents. It is a source-specific probe: a numerically identical table in a payment or approval record does not satisfy an order-document target. The probe compares fixed-size and table-aware splitting with and without the cross-encoder; semantic chunking remains covered by the unchanged primary 32-query benchmark. Results are written to `docs/table-evaluation.md` and `.json`.

## Development iteration: preserve source identity in reranking
The first trained-cross-encoder table probe confused identical financial allocation text from order, payment, approval, and refund records. Its raw passage scoring omitted parent source identity. The final reranker scores the document title, source label, case scope, and passage together with the query. This change is applied uniformly to all reranked conditions; candidate generation and the evaluation queries/annotations are unchanged. Initial results are retained in `docs/iterations/`. Because the benchmark informed this development change, final scores remain development results, not held-out estimates.
