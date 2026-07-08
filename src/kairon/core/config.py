"""Configuração central via pydantic-settings.

Uma única fonte de verdade para toda a app. Lê de variáveis de ambiente
(e do .env em dev). Importe `settings` — é um singleton cacheado.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",  # ignora vars extras no ambiente sem quebrar
        protected_namespaces=(),  # permite o campo model_version sem warning
    )

    # ---- App ----
    app_env: Literal["development", "staging", "production"] = "development"
    log_level: str = "INFO"
    model_version: str = "baseline-0.1.0"
    # Origens permitidas p/ CORS (front Next.js). Lista separada por vírgula.
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    # ---- Postgres ----
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_user: str = "kairon"
    postgres_password: str = "change-me-in-dev"
    postgres_db: str = "kairon"
    database_url: str = ""  # se vazio, é montado em `async_database_url`

    # ---- Anthropic ----
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-5"
    anthropic_max_tokens: int = 1024

    # ---- OpenAI (provedor alternativo do copiloto) ----
    # Se openai_api_key estiver setada, o copiloto usa OpenAI no lugar do Claude.
    openai_api_key: str = ""
    openai_model: str = "gpt-5.4-mini"
    openai_max_tokens: int = 1024

    # ---- Sentry ----
    sentry_dsn: str = ""
    sentry_traces_sample_rate: float = 0.1

    # ---- Auth / JWT (US-001) ----
    # Em produção, DEFINA jwt_secret via env. O default só serve para dev local.
    jwt_secret: str = "dev-insecure-change-me"
    jwt_algorithm: str = "HS256"
    access_token_ttl_min: int = 15
    refresh_token_ttl_days: int = 7
    # Registro: por convite (admin cria usuários). Cadastro aberto de novos
    # tenants fica desligado por padrão — ligue só para trials self-serve.
    allow_open_registration: bool = False
    # Rate limit no login (anti brute-force): X tentativas por janela (min) por IP+email.
    # Janela curta o suficiente para não travar QA/demo; em dev pode-se reduzir
    # ainda mais via env (LOGIN_WINDOW_MIN=1).
    login_max_attempts: int = 5
    login_window_min: int = 5

    # ---- Supabase ----
    supabase_url: str = ""
    supabase_key: str = ""
    supabase_jwt_secret: str = ""

    # ---- Backblaze ----
    backblaze_key_id: str = ""
    backblaze_app_key: str = ""
    backblaze_bucket: str = "kairon-frete-datalake"

    # ---- ANP ETL ----
    # CSV público de preços de combustíveis (ver ingestion/anp/scraper.py).
    anp_diesel_csv_url: str = Field(default="")

    @computed_field  # type: ignore[prop-decorator]
    @property
    def async_database_url(self) -> str:
        """URL async (asyncpg). Usa DATABASE_URL se fornecida, senão monta."""
        if self.database_url:
            return self.database_url
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    """Singleton cacheado. Facilita override em teste (get_settings.cache_clear())."""
    return Settings()


settings = get_settings()
