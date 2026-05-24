import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.agent.loop import run_agent
from app.agent.types import ChatResponse, PublicSource
from app.llm.cascade import get_cascade
from auth_clerk import ClerkClaims, get_current_clerk_user

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

    response = await run_agent(request.question)

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
