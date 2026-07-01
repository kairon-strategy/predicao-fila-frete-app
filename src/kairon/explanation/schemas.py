"""Schemas do context explanation."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ExplainRequest(BaseModel):
    prediction_id: str = Field(..., description="ID de uma predição já gerada em /v1/predict")
    question: str | None = Field(
        default=None,
        max_length=500,
        description="Pergunta livre sobre a predição (sanitizada; US-039). Vazio = explicação padrão.",
    )


class ExplainResponse(BaseModel):
    prediction_id: str
    explanation: str
    source: str = Field(..., description="llm | template — de onde veio o texto")
