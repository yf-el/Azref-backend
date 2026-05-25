import logging
import time

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.agent.lang import detect_lang
from app.agent.loop import run_agent
from app.agent.types import ChatResponse, PublicSource
from app.llm.cascade import get_cascade
from auth_clerk import ClerkClaims, get_current_clerk_user
from kafka_events import (
    TOPIC_AGENT_EVENTS,
    AgentQuestionAnsweredPayload,
    AgentQuestionAnsweredV1,
    producer as kafka_producer,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1")


class ChatRequest(BaseModel):
    question: str


@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    claims: ClerkClaims = Depends(get_current_clerk_user),
):
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="Question is required")

    logger.info("chat request user=%s question_len=%d", claims.sub, len(request.question))

    started_at = time.perf_counter()
    response = await run_agent(request.question)
    duration_ms = int((time.perf_counter() - started_at) * 1000)

    # Publish to Kafka fire-and-forget — the user response below must never be
    # delayed or blocked by broker availability (cf. ADR-006 / outbox roadmap).
    # `user_name` is None until we propagate it from Clerk JWT claims.

    # Clerk doesn't send Email by  default,
    # TODO: update frontend to use the custom template to include email in the JWT, or remove email from the event payload if we don't want to use it.
    event = AgentQuestionAnsweredV1(
        user_id=claims.sub,
        payload=AgentQuestionAnsweredPayload(
            user_email=claims.email,
            user_name=None,
            question_text=request.question,
            answer_text=response.answer,
            language=detect_lang(request.question),
            llm_provider=response.provider,
            llm_model=response.model,
            duration_ms=duration_ms,
        ),
    )
    kafka_producer.publish_nowait(TOPIC_AGENT_EVENTS, event, key=claims.sub)

    return ChatResponse(
        answer=response.answer,
        sources=[
            PublicSource(
                type=s.type,
                reference=s.reference,
                title=s.title,
                pdf_url=s.pdf_url,
            )
            for s in response.sources
        ],
        fallback_url=response.fallback_url,
    )


@router.get("/health")
async def health():
    cascade = get_cascade()
    return {
        "status": "ok",
        "providers_count": len(cascade.get_available_providers()),
    }
