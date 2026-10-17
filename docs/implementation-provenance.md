# Implementation provenance

This repository is an original implementation of the customer device return and refund investigation use case. The academy solution kit is a requirements reference only: no kit code, synthetic records, prompts, reports or assets are copied into this repository.

The implementation uses public framework interfaces from LangChain, LangGraph, FastAPI, FastEmbed, ReportLab and PyMuPDF. The local source PDFs are generated from original fictional records; the public guidance notes are attributed paraphrases with original URLs. Optional bank integration follows the official Plaid sandbox transaction API; it does not access real accounts.

The comparison reports measure retrieval on declared synthetic development questions. No claims of production deployment, real bank acceptance, or measured OpenAI faithfulness are made without corresponding evidence.
