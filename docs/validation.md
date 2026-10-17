# Validation of the revised PDF application

The final full test run passed 44 tests. Following the extraction-cache relocation, 16 focused API/security tests passed; 22 focused financial, session-policy and bank-adapter tests passed, including two additional bank-lifecycle invariants. The 46 distinct tests are not claimed to have run as one final combined command.

A live local server was checked with all three privately generated roles: case visibility, PDF exports and denial of restricted statement URLs passed. The browser sign-in layout was visually reviewed. JavaScript syntax, Python compilation, Ruff formatting and undefined-name/import checks passed.

All 91 corpus PDFs were readable and their manifest hashes verified. Representative long documents, financial tables and bank summaries were visually reviewed. The final fixed strategy produced 274 unique chunk IDs, with the explicit cl100k_base token cap checked. Supplemental table retrieval found all required source-specific tax/control-total evidence for all eight cases in all four conditions.

The primary comparison is docs/evaluation-pdf.json and .md, using the final corrected tokenizer. Historical pre-PDF reports and preliminary measurements must not be substituted for that version. OpenAI generation quality is unmeasured; bank API tests use mock transports. No real payments or external customer actions were executed.

The publication scanner checks allowlisted source and extracted PDF text against common credential patterns and privately configured secret values without printing those values. Runtime files, credentials, SQLite identities/sessions/history, extracted caches, vector indexes and model weights are excluded. This is a useful publication check, not a guarantee that every possible secret format is detectable.
