from ipaddress import ip_network

from pydantic import AliasChoices, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _reject_weak_production_secret(name: str, value: str) -> None:
    if len(set(value)) < 2:
        raise ValueError(f"{name} must not be a repeated character in production")
    lowered = value.casefold()
    if "replace-with" in lowered or "please-do-not-use" in lowered:
        raise ValueError(f"{name} must not use a documented placeholder in production")


def _validate_production_origins(origins: tuple[tuple[str, str], ...]) -> None:
    for name, origin in origins:
        if not origin.startswith("https://"):
            raise ValueError(f"{name} must be an https origin in production")
        host = origin.split("://", 1)[1].split("/", 1)[0].split(":")[0]
        if host in {"localhost", "127.0.0.1"} or host.endswith(".localhost"):
            raise ValueError(f"{name} must not use localhost in production")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", populate_by_name=True)

    database_url: str
    redis_url: str = "redis://:local-dev-redis@127.0.0.1:56379/0"
    jwt_secret: str
    widget_token_secret: str
    rate_key_secret: str
    cookie_secure: bool = False
    staff_app_origin: str = "http://localhost:3000"
    widget_origin: str = "http://widget.localhost:3000"
    marketing_host_origin: str = "http://host.localhost:3000"
    approved_frame_ancestors: str = Field(
        default="http://localhost:3000",
        validation_alias=AliasChoices(
            "WIDGET_FRAME_ANCESTORS",
            "APPROVED_FRAME_ANCESTORS",
            "approved_frame_ancestors",
        ),
    )
    trusted_proxy_cidrs: str = ""
    app_env: str = "local"
    chat_retention_days: int = 30
    rate_bootstrap: int = 60
    rate_bootstrap_window: int = 600
    rate_visitor_create: int = 10
    rate_visitor_create_window: int = 3600
    rate_visitor_submit: int = 20
    rate_visitor_submit_window: int = 60
    rate_visitor_submit_ip: int = 60
    rate_visitor_submit_ip_window: int = 60
    rate_login_failure: int = 10
    rate_login_failure_window: int = 900
    anthropic_model: str = "claude-haiku-4-5-20251001"
    anthropic_api_key: str | None = None
    anthropic_temperature: float = 0.0
    anthropic_max_tokens: int = 250
    anthropic_timeout: float = 30.0
    haiku_model: str = "claude-haiku-4-5-20251001"
    haiku_max_tokens: int = 350
    haiku_timeout: float = 10.0
    openai_api_key: str | None = None
    openai_embed_model: str = "text-embedding-3-small"
    openai_embed_dim: int = 1536
    embed_query_timeout: float = 3.0
    embed_ingest_timeout: float = 30.0
    embed_batch: int = 32
    chunk_target_chars: int = 1800
    chunk_overlap_chars: int = 200
    openai_embed_max_tokens: int = 8000
    max_answer_chars: int = 20000
    max_bot_answer_chars: int = 2000
    anthropic_calls_per_minute: int = 6
    full_context_max_tokens: int = 50_000
    fast_path_min_score: float = 0.15
    fast_path_margin_ratio: float = 1.5
    conversation_window_size: int = 6
    query_vector_cache_ttl: int = 300
    kb_ingest_page_concurrency: int = 4
    kb_ingest_source_concurrency: int = 2
    kb_ingest_host_delay_ms: int = 500
    kb_ingest_stuck_minutes: int = 10
    kb_llm_extract_concurrency: int = 4
    kb_llm_extract_prompt_version: str = "v1"
    kb_ingest_retry_sleep: float = 0.0

    def frame_ancestor_origins(self) -> list[str]:
        return [part.strip() for part in self.approved_frame_ancestors.split(",") if part.strip()]

    def trusted_proxy_networks(self) -> list:
        networks = []
        for part in self.trusted_proxy_cidrs.split(","):
            raw = part.strip()
            if not raw:
                continue
            networks.append(ip_network(raw, strict=False))
        return networks

    @field_validator("jwt_secret")
    @classmethod
    def jwt_secret_min_length(cls, value: str) -> str:
        if len(value) < 64:
            raise ValueError("JWT_SECRET must be at least 64 characters")
        return value

    @field_validator("widget_token_secret")
    @classmethod
    def widget_token_secret_min_length(cls, value: str) -> str:
        if len(value) < 64:
            raise ValueError("WIDGET_TOKEN_SECRET must be at least 64 characters")
        return value

    @field_validator("rate_key_secret")
    @classmethod
    def rate_key_secret_min_length(cls, value: str) -> str:
        if len(value) < 64:
            raise ValueError("RATE_KEY_SECRET must be at least 64 characters")
        return value

    @field_validator("anthropic_model")
    @classmethod
    def anthropic_model_nonempty(cls, value: str) -> str:
        model_id = value.strip()
        if not model_id:
            raise ValueError("ANTHROPIC_MODEL must be a non-empty model id")
        return model_id

    @field_validator("openai_embed_model")
    @classmethod
    def openai_embed_model_nonempty(cls, value: str) -> str:
        model_id = value.strip()
        if not model_id:
            raise ValueError("OPENAI_EMBED_MODEL must be a non-empty model id")
        return model_id

    @field_validator("openai_embed_dim")
    @classmethod
    def openai_embed_dim_positive(cls, value: int) -> int:
        if value < 1:
            raise ValueError("OPENAI_EMBED_DIM must be a positive integer")
        return value

    @field_validator("anthropic_max_tokens")
    @classmethod
    def anthropic_max_tokens_positive(cls, value: int) -> int:
        if value < 1:
            raise ValueError("ANTHROPIC_MAX_TOKENS must be a positive integer")
        return value

    @model_validator(mode="after")
    def production_must_fail_closed(self) -> "Settings":
        if self.app_env != "production":
            return self
        if self.chat_retention_days < 1:
            raise ValueError("CHAT_RETENTION_DAYS must be a positive integer in production")
        if not self.cookie_secure:
            raise ValueError("COOKIE_SECURE must be true in production")
        _validate_production_origins(
            (
                ("STAFF_APP_ORIGIN", self.staff_app_origin),
                ("WIDGET_ORIGIN", self.widget_origin),
                ("MARKETING_HOST_ORIGIN", self.marketing_host_origin),
            )
        )
        if not self.redis_url.startswith("rediss://"):
            raise ValueError("REDIS_URL must use rediss:// in production")
        if "local-dev-redis" in self.redis_url:
            raise ValueError("production redis URL must not use the local-dev-redis password")
        _reject_weak_production_secret("JWT_SECRET", self.jwt_secret)
        _reject_weak_production_secret("WIDGET_TOKEN_SECRET", self.widget_token_secret)
        _reject_weak_production_secret("RATE_KEY_SECRET", self.rate_key_secret)
        if self.openai_embed_dim != 1536:
            raise ValueError("OPENAI_EMBED_DIM must be 1536 in production")
        if not self.openai_api_key or not self.openai_api_key.strip():
            raise ValueError("OPENAI_API_KEY is required in production")
        return self

    @property
    def async_database_url(self) -> str:
        if self.database_url.startswith("postgresql://"):
            return self.database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
        return self.database_url

    @property
    def sync_database_url(self) -> str:
        url = self.database_url.replace("+asyncpg", "")
        if url.startswith("postgresql://"):
            return url.replace("postgresql://", "postgresql+psycopg://", 1)
        return url


def get_settings() -> Settings:
    return Settings()
