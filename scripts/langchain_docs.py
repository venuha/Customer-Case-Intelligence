import asyncio
from pathlib import Path
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client


async def main():
    Path("work").mkdir(exist_ok=True)
    async with streamablehttp_client("https://docs.langchain.com/mcp") as (r, w, _):
        async with ClientSession(r, w) as session:
            await session.initialize()
            result = await session.list_tools()
            Path("work/langchain_mcp_tools.json").write_text(
                result.model_dump_json(indent=2)
            )
            answer = await session.call_tool(
                "search_docs_by_lang_chain",
                {
                    "query": "Python StateGraph conditional edges LangChain ChatOpenAI with_structured_output LCEL prompt"
                },
            )
            Path("work/langchain_mcp_reference.json").write_text(
                answer.model_dump_json(indent=2)
            )
            print(str(answer)[:4000])


asyncio.run(main())
