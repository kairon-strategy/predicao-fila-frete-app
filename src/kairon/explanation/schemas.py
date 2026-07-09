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


# ---- Configuração do copiloto (admin: copilot:read/write) --------------------


class PromptItem(BaseModel):
    key: str
    label: str
    content: str
    scope: str  # tenant | global | default
    is_override: bool
    updated_by: str | None = None
    updated_at: str | None = None
    default: str


class PromptUpdate(BaseModel):
    content: str = Field(..., min_length=1, max_length=20000)


class CopilotSettingsUpdate(BaseModel):
    """Todos opcionais; None em campo anulável = 'herda' (limpa o override)."""

    enabled: bool | None = None
    provider: str | None = Field(default=None, pattern="^(auto|openai|anthropic)$")
    model: str | None = Field(default=None, max_length=60)
    max_tokens: int | None = Field(default=None, ge=1, le=8192)
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    max_words: int | None = Field(default=None, ge=20, le=2000)
    rate_limit_per_min: int | None = Field(default=None, ge=1, le=600)
