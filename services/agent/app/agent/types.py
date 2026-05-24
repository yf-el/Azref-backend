"""
Pydantic models for agent input/output.
"""

from pydantic import BaseModel


class Source(BaseModel):
    type: str  # "law", "article", "document"
    reference: str  # e.g. "القانون الجنائي - المادة 505"
    title: str = ""
    pdf_url: str | None = None


class ToolStep(BaseModel):
    tool: str
    params: dict
    results_count: int


class AgentResponse(BaseModel):
    """Full internal response — used inside the agent."""
    answer: str
    sources: list[Source]
    steps: list[ToolStep]
    provider: str
    model: str
    total_tokens: int
    steps_taken: int
    fallback_url: str | None = None


class PublicSource(BaseModel):
    type: str
    reference: str
    title: str = ""
    pdf_url: str | None = None


class ChatResponse(BaseModel):
    """Public API response — hides internal details."""
    answer: str
    sources: list[PublicSource]
    fallback_url: str | None = None
