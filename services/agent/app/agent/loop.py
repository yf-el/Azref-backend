"""
ReAct agent orchestration loop.
Reason → Act → Observe → Repeat (max 5 steps).
"""

import json
import logging
import re
from urllib.parse import quote

from cache_semantic import cache_exact

from app.agent.lang import detect_lang
from app.agent.prompt import get_system_prompt
from app.agent.tools import TOOL_SCHEMAS, execute_tool
from app.agent.types import AgentResponse, Source, ToolStep
from app.llm.cascade import get_cascade
from app.config import settings

NO_RESULTS_ANSWERS = {
    "ar": (
        "لم أجد معلومات محددة في قاعدة البيانات حول هذا الموضوع.\n\n"
        "يمكنك البحث يدوياً في الموقع للاطلاع على الوثائق المتاحة."
    ),
    "fr": (
        "Je n'ai pas trouvé d'information précise dans la base de données sur ce sujet.\n\n"
        "Vous pouvez effectuer une recherche manuelle sur le site pour consulter les documents disponibles."
    ),
}

FINAL_ANSWER_PROMPTS = {
    "ar": "أجب الآن بناءً على ما جمعته من معلومات.",
    "fr": "Réponds maintenant à l'utilisateur en te basant sur les informations collectées.",
}

logger = logging.getLogger(__name__)


@cache_exact(namespace="agent:answer", ttl=86400, prompt_arg="question", loads=AgentResponse.model_validate)
async def run_agent(question: str) -> AgentResponse:
    """
    Run the agent loop for a user question.
    Returns an AgentResponse with answer, sources, and reasoning steps.
    Cached for 24h on exact question match (Redis); see [[cache_semantic]] lib.
    """
    cascade = get_cascade()
    lang = detect_lang(question)

    messages = [
        {"role": "system", "content": get_system_prompt(lang)},
        {"role": "user", "content": question},
    ]

    steps: list[ToolStep] = []
    sources: list[Source] = []
    total_tokens = 0
    provider = ""
    model = ""

    for step in range(settings.max_agent_steps):
        logger.info(f"Agent step {step + 1}/{settings.max_agent_steps}")

        result = await cascade.chat(messages=messages, tools=TOOL_SCHEMAS)
        total_tokens += result["tokens_in"] + result["tokens_out"]
        provider = result["provider"]
        model = result["model"]

        # If LLM returns a final text answer (no tool calls)
        if not result.get("tool_calls"):
            answer = _strip_thinking(result["content"])
            fallback_url = None

            # Hard stop: if no sources found, don't trust the LLM answer
            if not sources:
                answer = NO_RESULTS_ANSWERS[lang]
                fallback_url = f"https://huquqai.ma/search?q={quote(question)}"

            return AgentResponse(
                answer=answer,
                sources=sources,
                steps=steps,
                provider=provider,
                model=model,
                total_tokens=total_tokens,
                steps_taken=step + 1,
                fallback_url=fallback_url,
            )

        # Process tool calls
        # Add assistant message with tool calls to history
        messages.append({
            "role": "assistant",
            "content": result.get("content", ""),
            "tool_calls": result["tool_calls"],
        })

        for tool_call in result["tool_calls"]:
            fn_name = tool_call["function"]["name"]
            fn_args = tool_call["function"]["arguments"]
            tool_call_id = tool_call.get("id", fn_name)

            logger.info(f"  Tool: {fn_name}({fn_args})")

            # Execute tool
            tool_result = await execute_tool(fn_name, fn_args)

            # Add tool result to message history
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call_id,
                "content": tool_result,
            })

            # Track step
            parsed_args = json.loads(fn_args)
            parsed_results = json.loads(tool_result)
            if isinstance(parsed_results, list):
                result_count = len(parsed_results)
            elif isinstance(parsed_results, dict) and "total_results" in parsed_results:
                result_count = parsed_results["total_results"]
            else:
                result_count = 0

            steps.append(ToolStep(
                tool=fn_name,
                params=parsed_args,
                results_count=result_count,
            ))

            # Extract sources from tool results
            sources.extend(_extract_sources(fn_name, parsed_results, lang))

    # Max steps reached — force a final answer
    logger.warning("Max steps reached, forcing final answer")
    messages.append({
        "role": "user",
        "content": FINAL_ANSWER_PROMPTS[lang],
    })

    result = await cascade.chat(messages=messages, max_tokens=3000)
    total_tokens += result["tokens_in"] + result["tokens_out"]

    answer = _strip_thinking(result["content"])
    fallback_url = None

    if not sources:
        answer = NO_RESULTS_ANSWER
        fallback_url = f"https://huquqai.ma/search?q={quote(question)}"

    return AgentResponse(
        answer=answer,
        sources=sources,
        steps=steps,
        provider=result["provider"],
        model=result["model"],
        total_tokens=total_tokens,
        steps_taken=settings.max_agent_steps,
        fallback_url=fallback_url,
    )


def _strip_thinking(content: str) -> str:
    """Strip <think>...</think> tags from Qwen/reasoning models."""
    return re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()


SOURCE_LABELS = {
    "ar": {
        "adala_documents": "وزارة العدل (عدالة)",
        "juriscassation_documents": "محكمة النقض",
        "sgg_documents": "الجريدة الرسمية",
        "collectivites_documents": "الجماعات الترابية",
        "cspj_documents": "المجلس الأعلى للسلطة القضائية",
    },
    "fr": {
        "adala_documents": "Ministère de la Justice (Adala)",
        "juriscassation_documents": "Cour de cassation",
        "sgg_documents": "Bulletin officiel",
        "collectivites_documents": "Collectivités territoriales",
        "cspj_documents": "Conseil supérieur du pouvoir judiciaire",
    },
}


def _article_ref(lang: str, article_numero: str, loi_numero: str) -> str:
    if lang == "fr":
        return f"Article {article_numero} de {loi_numero}"
    return f"المادة {article_numero} من {loi_numero}"


def _extract_sources(tool_name: str, results: list | dict, lang: str) -> list[Source]:
    """Extract Source objects from tool results, localized to `lang`."""
    sources = []
    labels = SOURCE_LABELS.get(lang, SOURCE_LABELS["ar"])

    # search_all returns a dict with chunks/lois/articles
    if tool_name == "search_all" and isinstance(results, dict):
        for r in results.get("chunks", []):
            table = r.get("source_table", "")
            label = labels.get(table, table)
            sources.append(Source(
                type="document",
                reference=label,
                title=r.get("doc_title") or (r.get("chunk_text", "")[:100] if r.get("chunk_text") else ""),
                pdf_url=r.get("pdf_url"),
            ))
        for r in results.get("lois", []):
            sources.append(Source(
                type="law",
                reference=f"{r.get('numero', '')} - {r.get('type', '')}",
                title=r.get("titre", ""),
            ))
        for r in results.get("articles", []):
            sources.append(Source(
                type="article",
                reference=_article_ref(lang, r.get("article_numero", ""), r.get("loi_numero", "")),
                title=r.get("contenu", "")[:100] if r.get("contenu") else "",
            ))
        return sources

    if not isinstance(results, list):
        return []

    for r in results:
        if tool_name == "search_laws":
            sources.append(Source(
                type="law",
                reference=f"{r.get('numero', '')} - {r.get('type', '')}",
                title=r.get("titre", ""),
            ))
        elif tool_name == "get_article":
            sources.append(Source(
                type="article",
                reference=_article_ref(lang, r.get("article_numero", ""), r.get("loi_numero", "")),
                title=r.get("contenu", "")[:100] if r.get("contenu") else "",
            ))
        elif tool_name == "search_documents":
            table = r.get("source_table", "")
            label = labels.get(table, table)
            sources.append(Source(
                type="document",
                reference=label,
                title=r.get("chunk_text", "")[:100] if r.get("chunk_text") else "",
            ))

    return sources
