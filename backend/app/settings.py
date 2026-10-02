from enum import StrEnum
from functools import lru_cache
from ipaddress import ip_network
from urllib.parse import urlsplit

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _reject_weak_production_secret(name: str, value: str) -> None:
    if len(set(value)) < 2:
        raise ValueError(f"{name} must not be a repeated character in production")
    lowered = value.casefold()
    if "replace-with" in lowered or "please-do-not-use" in lowered:
        raise ValueError(f"{name} must not use a documented placeholder in production")


def _validate_provider_key(name: str, value: str | None) -> None:
    key = value.strip() if value else ""
    if len(key) < 20 or "replace" in key.casefold():
        raise ValueError(f"{name} must be a real provider credential in production")


def _validate_production_origins(origins: tuple[tuple[str, str], ...]) -> None:
    for name, origin in origins:
        parsed = urlsplit(origin)
        if parsed.scheme != "https" or not parsed.hostname:
            raise ValueError(f"{name} must be an https origin in production")
        if parsed.username or parsed.password or parsed.path or parsed.query or parsed.fragment:
            raise ValueError(f"{name} must be a canonical origin in production")
        host = parsed.hostname.casefold()
        if host in {"localhost", "127.0.0.1"} or host.endswith(".localhost"):
            raise ValueError(f"{name} must not use localhost in production")


def _origin_key(origin: str) -> tuple[str, int]:
    parsed = urlsplit(origin)
    host = parsed.hostname
    assert host is not None
    return host.casefold(), parsed.port or 443


def _validate_production_redis(url: str) -> None:
    if not url.startswith("rediss://"):
        raise ValueError("REDIS_URL must use rediss:// in production")
    if urlsplit(url).username != "app":
        raise ValueError("REDIS_URL must authenticate as the app ACL user in production")
    if "local-dev-redis" in url:
        raise ValueError("production redis URL must not use the local-dev-redis password")


def _validate_optional_provider_url(name: str, url: str | None) -> None:
    if not url:
        return
    provider = urlsplit(url)
    invalid = (
        provider.scheme != "https"
        or not provider.hostname
        or provider.username
        or provider.password
        or provider.query
        or provider.fragment
        or provider.hostname.casefold() in {"localhost", "127.0.0.1"}
    )
    if invalid:
        raise ValueError(f"{name} must be a canonical https URL in production")


class AppEnvironment(StrEnum):
    LOCAL = "local"
    TEST = "test"
    PRODUCTION = "production"


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
    widget_csp_service_secret: str = ""
    trusted_proxy_cidrs: str = ""
    app_env: AppEnvironment = AppEnvironment.LOCAL
    internal_eval_enabled: bool = False
    enable_background_workers: bool = True
    status_api_probe_url: str = "http://127.0.0.1:8000/health"
    chat_retention_days: int = 30
    rate_bootstrap: int = 60
    rate_bootstrap_window: int = 600
    rate_widget_csp_ip: int = 120
    rate_widget_csp_site: int = 3000
    rate_widget_csp_window: int = 60
    rate_visitor_create: int = 10
    rate_visitor_create_window: int = 3600
    rate_visitor_submit: int = 20
    rate_visitor_submit_window: int = 60
    rate_visitor_submit_ip: int = 60
    rate_visitor_submit_ip_window: int = 60
    rate_login_failure: int = 10
    rate_login_ip_failure: int = 100
    rate_login_failure_window: int = 900
    anthropic_model: str = "claude-haiku-4-5-20251001"
    anthropic_api_key: str | None = None
    anthropic_max_tokens: int = 500
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
    chunk_target_chars: int = 900
    chunk_overlap_chars: int = 150
    openai_embed_max_tokens: int = 8000
    max_answer_chars: int = 20000
    max_bot_answer_chars: int = 1500
    anthropic_calls_per_minute: int = 6
    full_context_max_tokens: int = 50_000
    fast_path_min_score: float = 0.15
    fast_path_margin_ratio: float = 1.5
    conversation_window_size: int = 24
    message_replay_limit: int = 500
    query_vector_cache_ttl: int = 24 * 60 * 60
    kb_ingest_page_concurrency: int = 4
    kb_ingest_source_concurrency: int = 2
    kb_ingest_host_delay_ms: int = 500
    kb_ingest_stuck_minutes: int = 10
    kb_ingest_source_timeout_seconds: float = 600.0
    kb_llm_extract_concurrency: int = 4
    kb_ingest_retry_sleep: float = 0.0
    bot_generation_lease_seconds: int = 90
    bot_generation_recovery_grace_seconds: int = 2
    background_job_poll_seconds: float = 1.0
    handoff_summary_max_attempts: int = 3
    knowledge_gap_min_conversations: int = 5
    knowledge_gap_window_days: int = 14
    knowledge_gap_spike_conversations: int = 3
    knowledge_gap_spike_hours: int = 24
    knowledge_gap_similarity: float = 0.82
    ip_geolocation_provider_url: str | None = None
    ip_geolocation_retry_hours: int = 24

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

    @field_validator("widget_csp_service_secret")
    @classmethod
    def widget_csp_service_secret_min_length(cls, value: str) -> str:
        if value and len(value) < 64:
            raise ValueError("WIDGET_CSP_SERVICE_SECRET must be at least 64 characters")
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

    @field_validator(
        "openai_embed_dim",
        "haiku_max_tokens",
        "chat_retention_days",
        "rate_bootstrap",
        "rate_bootstrap_window",
        "rate_widget_csp_ip",
        "rate_widget_csp_site",
        "rate_widget_csp_window",
        "rate_visitor_create",
        "rate_visitor_create_window",
        "rate_visitor_submit",
        "rate_visitor_submit_window",
        "rate_visitor_submit_ip",
        "rate_visitor_submit_ip_window",
        "rate_login_failure",
        "rate_login_ip_failure",
        "rate_login_failure_window",
        "embed_batch",
        "chunk_target_chars",
        "chunk_overlap_chars",
        "openai_embed_max_tokens",
        "max_answer_chars",
        "max_bot_answer_chars",
        "anthropic_calls_per_minute",
        "full_context_max_tokens",
        "conversation_window_size",
        "message_replay_limit",
        "query_vector_cache_ttl",
        "kb_ingest_page_concurrency",
        "kb_ingest_source_concurrency",
        "kb_ingest_stuck_minutes",
        "kb_llm_extract_concurrency",
        "bot_generation_lease_seconds",
        "bot_generation_recovery_grace_seconds",
        "handoff_summary_max_attempts",
        "knowledge_gap_min_conversations",
        "knowledge_gap_window_days",
        "knowledge_gap_spike_conversations",
        "knowledge_gap_spike_hours",
        "ip_geolocation_retry_hours",
    )
    @classmethod
    def positive_int(cls, value: int) -> int:
        if value < 1:
            raise ValueError("must be a positive integer")
        return value

    @field_validator(
        "anthropic_timeout",
        "haiku_timeout",
        "embed_query_timeout",
        "embed_ingest_timeout",
        "kb_ingest_source_timeout_seconds",
        "fast_path_min_score",
        "fast_path_margin_ratio",
        "background_job_poll_seconds",
        "knowledge_gap_similarity",
    )
    @classmethod
    def positive_float(cls, value: float) -> float:
        if value < 0:
            raise ValueError("must be zero or positive")
        return value

    @field_validator("kb_ingest_host_delay_ms", "kb_ingest_retry_sleep")
    @classmethod
    def non_negative_int(cls, value: int) -> int:
        if value < 0:
            raise ValueError("must be zero or positive")
        return value

    @field_validator("anthropic_max_tokens")
    @classmethod
    def anthropic_max_tokens_positive(cls, value: int) -> int:
        if value < 1:
            raise ValueError("ANTHROPIC_MAX_TOKENS must be a positive integer")
        return value

    @model_validator(mode="after")
    def production_must_fail_closed(self) -> "Settings":
        if self.app_env is not AppEnvironment.PRODUCTION:
            return self
        if self.internal_eval_enabled:
            raise ValueError("INTERNAL_EVAL_ENABLED must be false in production")
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
        origins = {
            _origin_key(self.staff_app_origin),
            _origin_key(self.widget_origin),
            _origin_key(self.marketing_host_origin),
        }
        if len(origins) != 3:
            raise ValueError(
                "STAFF_APP_ORIGIN, WIDGET_ORIGIN, and MARKETING_HOST_ORIGIN must be distinct"
            )
        _validate_production_redis(self.redis_url)
        _validate_optional_provider_url(
            "IP_GEOLOCATION_PROVIDER_URL", self.ip_geolocation_provider_url
        )
        _reject_weak_production_secret("JWT_SECRET", self.jwt_secret)
        _reject_weak_production_secret("WIDGET_TOKEN_SECRET", self.widget_token_secret)
        _reject_weak_production_secret("RATE_KEY_SECRET", self.rate_key_secret)
        if not self.widget_csp_service_secret:
            raise ValueError("WIDGET_CSP_SERVICE_SECRET is required in production")
        _reject_weak_production_secret("WIDGET_CSP_SERVICE_SECRET", self.widget_csp_service_secret)
        if self.openai_embed_dim != 1536:
            raise ValueError("OPENAI_EMBED_DIM must be 1536 in production")
        _validate_provider_key("OPENAI_API_KEY", self.openai_api_key)
        _validate_provider_key("ANTHROPIC_API_KEY", self.anthropic_api_key)
        if not self.trusted_proxy_networks():
            raise ValueError("TRUSTED_PROXY_CIDRS must list at least one CIDR in production")
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


@lru_cache
def get_settings() -> Settings:
    return Settings()


def reset_settings_cache() -> None:
    get_settings.cache_clear()
