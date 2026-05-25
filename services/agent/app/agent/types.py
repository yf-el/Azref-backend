"""
Pydantic models for agent input/output.
"""

from pydantic import BaseModel, field_validator


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

    @field_validator("sources", mode="after")
    @classmethod
    def _drop_documents_without_pdf(cls, sources: list[PublicSource]) -> list[PublicSource]:
        # Une source `document` sans pdf_url n'est pas actionnable côté UI (pas de lien à suivre).
        # Articles/lois n'ont pas vocation à avoir un pdf_url, on les garde.
        return [s for s in sources if s.type != "document" or s.pdf_url]
