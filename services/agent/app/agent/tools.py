"""
Agent tool definitions and execution.
"""

import json
from app.db import queries

# Tool schemas (OpenAI function calling format)
TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "search_all",
            "description": "البحث الشامل في جميع المصادر القانونية المغربية: النصوص الكاملة والقوانين والمواد القانونية. يجب استخدام هذه الأداة أولاً دائماً.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "مصطلح البحث بالعربية",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_article",
            "description": "استرجاع مادة قانونية محددة من قانون معين. استخدم هذه الأداة بعد search_all للحصول على نص مادة محددة.",
            "parameters": {
                "type": "object",
                "properties": {
                    "loi_numero": {
                        "type": "string",
                        "description": "رقم القانون (مثل: ق.ج، 70.03، ق.م.م، ق.ل.ع)",
                    },
                    "article_numero": {
                        "type": "string",
                        "description": "رقم المادة",
                    },
                },
                "required": ["loi_numero", "article_numero"],
            },
        },
    },
]


async def execute_tool(name: str, arguments: str) -> str:
    """Execute a tool by name and return results as JSON string."""
    args = json.loads(arguments)

    if name == "search_all":
        results = await queries.search_all(args["query"])
        # Truncate chunk text for context window efficiency
        for r in results.get("chunks", []):
            if len(r.get("chunk_text", "")) > 500:
                r["chunk_text"] = r["chunk_text"][:500] + "..."
        return json.dumps(results, ensure_ascii=False, default=str)

    elif name == "get_article":
        results = await queries.search_articles(
            loi_numero=args.get("loi_numero"),
            article_numero=args.get("article_numero"),
        )
        return json.dumps(results, ensure_ascii=False, default=str)

    # Keep backward compat for individual tools if LLM calls them
    elif name == "search_documents":
        results = await queries.search_document_chunks(args["query"])
        for r in results:
            if len(r.get("chunk_text", "")) > 500:
                r["chunk_text"] = r["chunk_text"][:500] + "..."
        return json.dumps(results, ensure_ascii=False, default=str)

    elif name == "search_laws":
        results = await queries.search_lois(args["query"])
        return json.dumps(results, ensure_ascii=False, default=str)

    else:
        return json.dumps({"error": f"Unknown tool: {name}"}, ensure_ascii=False)
