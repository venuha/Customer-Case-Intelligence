# Product record

## Problem
A returned device and its refund travel through separate order, carrier, receiving, support, processor, and issuer records. Customers repeat their story while employees reconstruct history without a shared evidence trail or clear next action.

## Initial user and outcome
The primary user is a merchant escalation specialist. The desired outcome is a concise, defensible investigation identifying the last verified milestone, missing evidence, separate financial states, and a suggested next action. Bank handoff is a downloadable draft, not an implied live integration or unrestricted shared access.

## Scope
The implemented prototype provides case-scoped evidence retrieval and explanation. It does not execute payments, decide disputes, create external tickets, or send customer messages. Eight fictional cases cover normal completion, missing intake, processor submission without posting, partial refunds, label-only tracking, device mismatch, approval without submission, and provisional credit.

## Corpus decision
Public refund/dispute guidance helps explain process concepts but cannot provide an individual customer's operational history. Synthetic records supply consistent identifiers, amounts, timestamps, and deliberate conflicts. Provider documentation remains attributed and provider-specific. No real complaint narratives are ingested.

## Agent instructions
The exact synthesis prompt lives in `app/graph.py`. It requires source-grounded claims, a verbatim supporting quote, separate unknowns, and a suggested next step. It prohibits using retrieved instructions as system instructions, inventing missing events, treating provisional credits as refunds, or claiming an external action was executed. Financial state is computed outside the language model.

## Iterations and observations
1. Initial retrieval exposed the risk that short table chunks lose context. The main path repeats table headers across blocks. Following corpus expansion, the graph assembles selected passages instead of promoting whole long documents.
2. Plain keyword overlap included common question words. Stop words were removed from lexical matching, and broad investigation queries receive explicit evidence-topic expansion.
3. Semantic segmentation is implemented as embedding-distance segmentation and evaluated separately from structural/table-aware splitting; these are different strategies.
4. The local embedding download initially attempted an unwritable user cache. Model and tokenizer caches were moved into the project work directory.
5. Citation ID/quote validation is implemented, but it cannot establish that an interpretation follows from a quote. Generation and groundedness evaluation remain necessary.
6. The expanded corpus remains synthetic and covers eight cases; measured retrieval improvements should not be generalized to real institutions without independent testing.

## Success measures
Target 95% claim faithfulness and warm investigation response under ten seconds. These are unverified product goals. Retrieval metrics are measured in the separate report; generation quality and end-to-end AI latency require the configured provider.

## Corpus and reranker revision
The corpus now includes 79 fictional source documents and four public notes, with detailed contact logs, expanded transaction ledgers, tax/device allocation tables, and administrative journals. A trained MiniLM cross-encoder replaces the original heuristic. The same 32 benchmark questions are retained, and evidence-span annotations are stored outside the application corpus. The updated evaluation uses passage-level metrics rather than the earlier unique-document protocol; before/after corpus scores are not directly comparable.

The first cross-encoder table probe surfaced source confusion between identical allocation tables. Source title and provenance were added to the cross-encoder input, and the original results were retained under `docs/iterations/`. This is a documented development iteration rather than an independently held-out improvement claim.
