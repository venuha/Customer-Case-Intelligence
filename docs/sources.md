# Public source register

Reviewed: October 17, 2026. The application ingests four concise attributed paraphrases, not full third-party websites. Public reference guidance remains distinct from fictional customer evidence. No real telecom or bank names appear in case data.

| Source | Purpose | Included in retrieval? |
|---|---|---|
| [CFPB: credit-card refunds](https://www.consumerfinance.gov/ask-cfpb/how-can-i-get-a-refund-on-a-product-or-service-i-purchased-with-my-credit-card-en-1969/) | Explain merchant contact and issuer dispute options without determining legal eligibility. | Curated paraphrase |
| [CFPB: credit-card billing disputes](https://www.consumerfinance.gov/ask-cfpb/how-do-i-dispute-a-charge-on-my-credit-card-bill-en-61/) | Explain keeping correspondence and call history. | Curated paraphrase |
| [Provider documentation: refund trace references](https://support.stripe.com/questions/how-to-trace-a-refund-using-reference-numbers) | Explain ARN/STAN/RRN availability; provider-specific behavior is not universal policy. | Curated paraphrase |
| [Provider documentation: refund states](https://docs.stripe.com/refunds) | Inform pending, partial, failed, and posted state distinctions. | Curated paraphrase |
| [CFPB Consumer Complaint Database](https://www.consumerfinance.gov/data-research/consumer-complaints/) | Potential future research source; the CFPB states published complaint data are freely available to use, analyze, and build on. Complaints are allegations and are not representative or verified event histories. | No customer narratives downloaded or ingested |

## Source-use boundaries
Government educational references and short attributed provider paraphrases support this educational prototype; this is not a blanket legal opinion about reuse of every website or dataset. Review current terms before expanding ingestion or redistribution. Do not use real complaint narratives to reconstruct identifiable customers, assert allegations as facts, or impersonate institutional source systems.

## Framework documentation used while coding
- Official LangChain documentation MCP: https://docs.langchain.com/mcp (connected and searched successfully; development helper in scripts/langchain_docs.py).
- LangGraph graph API: https://docs.langchain.com/oss/python/langgraph/graph-api
- LangChain MCP integration: https://docs.langchain.com/oss/python/langchain/mcp
- OpenAI model documentation: https://developers.openai.com/api/docs/models/gpt-4.1-mini

## Trained reranker reference
FastEmbed cross-encoder integration: https://qdrant.tech/documentation/fastembed/fastembed-rerankers/ . Selected model: Xenova/ms-marco-MiniLM-L-6-v2 (Apache-2.0 as listed by FastEmbed). The trained model runs locally through ONNX Runtime. Model metadata is recorded separately from the application corpus.
