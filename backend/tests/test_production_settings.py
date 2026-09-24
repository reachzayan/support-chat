import pytest

from app.settings import Settings

_SECRETS = {
    "database_url": "postgresql://chat:chat@127.0.0.1:55432/support_chat_test",
    "jwt_secret": "a8f3c1e9b2d64750c4a1f8e3b6d9027c5e1a4b8f3c6d9e2a7b0c5d8e1f4a7b3c",
    "widget_token_secret": "d1e4a7b0c3f6d9e2a5b8c1d4e7f0a3b6c9d2e5f8a1b4c7d0e3f6a9b2c5d8e1f4",
    "rate_key_secret": "9c2f5a8d1e4b7c0f3a6d9e2b5c8f1a4d7e0b3c6f9a2d5e8b1c4f7a0d3e6b9c2f",
    "widget_csp_service_secret": "e1a4b7c0d3f6a9b2c5d8e1f4a7b0c3d6e9f2a5b8c1d4e7f0a3b6c9d2e5f8a1b4c",
}

_PROD = {
    "app_env": "production",
    "cookie_secure": True,
    "chat_retention_days": 30,
    "staff_app_origin": "https://admin.sample-site.example.com",
    "widget_origin": "https://widget.sample-site.example.com",
    "marketing_host_origin": "https://sample-site.example.com",
    "redis_url": "rediss://app:prod-redis-secret@127.0.0.1:6379/0",
}


def test_production_startup_rejects_insecure_cookies() -> None:
    with pytest.raises(ValueError, match="COOKIE_SECURE"):
        Settings(
            **_SECRETS,
            app_env="production",
            cookie_secure=False,
            chat_retention_days=30,
            staff_app_origin="https://admin.sample-site.example.com",
            widget_origin="https://widget.sample-site.example.com",
            marketing_host_origin="https://sample-site.example.com",
            redis_url="rediss://:prod-redis-secret@127.0.0.1:6379/0",
        )


def test_production_startup_rejects_http_staff_origin() -> None:
    with pytest.raises(ValueError, match="https"):
        Settings(
            **_SECRETS,
            app_env="production",
            cookie_secure=True,
            chat_retention_days=30,
            staff_app_origin="http://admin.sample-site.example.com",
            widget_origin="https://widget.sample-site.example.com",
            marketing_host_origin="https://sample-site.example.com",
            redis_url="rediss://:prod-redis-secret@127.0.0.1:6379/0",
        )


def test_production_startup_rejects_localhost_staff_origin() -> None:
    with pytest.raises(ValueError, match="localhost"):
        Settings(
            **_SECRETS,
            app_env="production",
            cookie_secure=True,
            chat_retention_days=30,
            staff_app_origin="https://localhost:3000",
            widget_origin="https://widget.sample-site.example.com",
            marketing_host_origin="https://sample-site.example.com",
            redis_url="rediss://:prod-redis-secret@127.0.0.1:6379/0",
        )


def test_production_startup_accepts_https_origins_and_secure_cookies() -> None:
    settings = Settings(
        **_SECRETS,
        app_env="production",
        cookie_secure=True,
        chat_retention_days=30,
        staff_app_origin="https://admin.sample-site.example.com",
        widget_origin="https://widget.sample-site.example.com",
        marketing_host_origin="https://sample-site.example.com",
        redis_url="rediss://app:prod-redis-secret@127.0.0.1:6379/0",
        anthropic_api_key="sk-ant-test-not-a-real-key",
        openai_api_key="sk-test-not-a-real-key",
    )
    assert settings.cookie_secure is True
    assert settings.staff_app_origin == "https://admin.sample-site.example.com"


def test_production_startup_rejects_default_redis_identity() -> None:
    with pytest.raises(ValueError, match="app ACL user"):
        Settings(
            **_SECRETS,
            **{**_PROD, "redis_url": "rediss://:prod-redis-secret@redis:6379/0"},
            anthropic_api_key="sk-ant-test-not-a-real-key",
            openai_api_key="sk-test-not-a-real-key",
        )


def test_production_geolocation_provider_must_be_canonical_https() -> None:
    with pytest.raises(ValueError, match="IP_GEOLOCATION_PROVIDER_URL"):
        Settings(
            **_SECRETS,
            **_PROD,
            ip_geolocation_provider_url="http://geo.example.test/api?token=secret",
            anthropic_api_key="sk-ant-test-not-a-real-key",
            openai_api_key="sk-test-not-a-real-key",
        )


def test_production_startup_rejects_plain_redis_url() -> None:
    with pytest.raises(ValueError, match="rediss"):
        Settings(
            **_SECRETS,
            app_env="production",
            cookie_secure=True,
            chat_retention_days=30,
            staff_app_origin="https://admin.sample-site.example.com",
            widget_origin="https://widget.sample-site.example.com",
            marketing_host_origin="https://sample-site.example.com",
            redis_url="redis://:prod-redis-secret@127.0.0.1:6379/0",
        )


def test_production_startup_rejects_default_local_redis_password() -> None:
    with pytest.raises(ValueError, match="redis"):
        Settings(
            **_SECRETS,
            app_env="production",
            cookie_secure=True,
            chat_retention_days=30,
            staff_app_origin="https://admin.sample-site.example.com",
            widget_origin="https://widget.sample-site.example.com",
            marketing_host_origin="https://sample-site.example.com",
            redis_url="redis://:local-dev-redis@127.0.0.1:56379/0",
        )


def test_production_startup_rejects_repeated_character_jwt_secret() -> None:
    with pytest.raises(ValueError, match="JWT_SECRET"):
        Settings(
            **_PROD,
            database_url=_SECRETS["database_url"],
            jwt_secret="j" * 64,
            widget_token_secret=_SECRETS["widget_token_secret"],
            rate_key_secret=_SECRETS["rate_key_secret"],
        )


def test_production_startup_rejects_env_example_placeholder_jwt_secret() -> None:
    with pytest.raises(ValueError, match="JWT_SECRET"):
        Settings(
            **_PROD,
            database_url=_SECRETS["database_url"],
            jwt_secret="replace-with-at-least-sixty-four-random-characters-please-do-not-use",
            widget_token_secret=_SECRETS["widget_token_secret"],
            rate_key_secret=_SECRETS["rate_key_secret"],
        )


def test_production_startup_rejects_mismatched_embed_dim() -> None:
    with pytest.raises(ValueError, match="OPENAI_EMBED_DIM"):
        Settings(
            **_SECRETS,
            **_PROD,
            openai_embed_dim=768,
            openai_api_key="sk-test",
        )


def test_production_startup_rejects_missing_openai_api_key() -> None:
    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        Settings(
            **_SECRETS,
            **_PROD,
            openai_api_key=None,
        )


def test_settings_reject_unknown_app_environment() -> None:
    with pytest.raises(ValueError, match=r"local.*test.*production"):
        Settings(
            **_SECRETS,
            app_env="dev",
        )


def test_production_startup_rejects_shared_staff_and_widget_origin() -> None:
    with pytest.raises(ValueError, match="distinct"):
        Settings(
            **_SECRETS,
            **{
                **_PROD,
                "widget_origin": "https://admin.sample-site.example.com",
            },
            anthropic_api_key="sk-ant-test-not-a-real-key",
            openai_api_key="sk-test-not-a-real-key",
        )


def test_production_startup_rejects_shared_marketing_and_widget_origin() -> None:
    with pytest.raises(ValueError, match="distinct"):
        Settings(
            **_SECRETS,
            **{
                **_PROD,
                "marketing_host_origin": "https://widget.sample-site.example.com",
            },
            anthropic_api_key="sk-ant-test-not-a-real-key",
            openai_api_key="sk-test-not-a-real-key",
        )


def test_production_startup_rejects_missing_anthropic_api_key() -> None:
    with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
        Settings(
            **_SECRETS,
            **_PROD,
            anthropic_api_key=None,
            openai_api_key="sk-test-not-a-real-key",
        )


@pytest.mark.parametrize(
    ("field", "value", "error"),
    [
        ("anthropic_api_key", "REPLACE_WITH_REAL_ANTHROPIC_KEY", "ANTHROPIC_API_KEY"),
        ("openai_api_key", "REPLACE_WITH_REAL_OPENAI_KEY", "OPENAI_API_KEY"),
    ],
)
def test_production_startup_rejects_provider_key_placeholders(
    field: str,
    value: str,
    error: str,
) -> None:
    values = {
        **_SECRETS,
        **_PROD,
        "anthropic_api_key": "sk-ant-api03-" + "a" * 64,
        "openai_api_key": "sk-proj-" + "b" * 64,
        field: value,
    }

    with pytest.raises(ValueError, match=error):
        Settings(**values)
