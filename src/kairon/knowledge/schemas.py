"""Schemas do contexto knowledge (RAG)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class IngestRequest(BaseModel):
    title: str = Field(..., min_length=2, max_length=300)
    text: str = Field(..., min_length=10, max_length=200_000)
    source: str | None = Field(default=None, max_length=300, description="URL/origem citável")


class IngestResponse(BaseModel):
    document_id: str
    title: str
    chunks: int


class DocumentItem(BaseModel):
    id: str
    title: str
    source: str | None = None
    scope: str  # global | tenant
    created_at: str


class AskRequest(BaseModel):
    question: str = Field(..., min_length=3, max_length=800)
    k: int | None = Field(default=None, ge=1, le=20)


class SourceItem(BaseModel):
    title: str
    source: str | None = None


class AskResponse(BaseModel):
    answer: str
    sources: list[SourceItem]
    grounded: bool
