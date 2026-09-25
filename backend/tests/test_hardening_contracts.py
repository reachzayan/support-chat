from datetime import UTC, datetime
from uuid import uuid4

import jwt
import pytest

from app.security.jwt import create_access_token, decode_access_token
from app.services import app_log, site_admin
from app.settings import Settings


def _settings() -> Settings:
    return Settings(
        database_url="postgresql://chat:chat@127.0.0.1:55432/support_chat_test",
        jwt_secret="jwt-secret-" + "a" * 64,
        widget_token_secret="widget-secret-" + "b" * 64,
        rate_key_secret="rate-secret-" + "c" * 64,
    )


def test_access_token_requires_the_supportchat_issuer_audience_and_core_claims() -> None:
    settings = _settings()
    token = create_access_token(uuid4(), 3, settings)

    claims = decode_access_token(token, settings)

    assert claims["iss"] == "supportchat"
    assert claims["aud"] == "supportchat-staff"
    assert isinstance(claims["iat"], int)
    assert isinstance(claims["jti"], str) and claims["jti"]


@pytest.mark.parametrize(
    "payload",
    [
        {"sub": str(uuid4()), "token_version": 0, "exp": datetime(2099, 1, 1, tzinfo=UTC)},
        {
            "sub": str(uuid4()),
            "token_version": 0,
            "exp": datetime(2099, 1, 1, tzinfo=UTC),
            "iat": datetime.now(UTC),
            "jti": str(uuid4()),
            "iss": "another-service",
            "aud": "supportchat-staff",
        },
    ],
)
def test_access_token_rejects_missing_or_wrong_security_context(payload: dict) -> None:
    settings = _settings()
    token = jwt.encode(payload, settings.jwt_secret, algorithm="HS256")

    with pytest.raises(jwt.PyJWTError):
        decode_access_token(token, settings)


def test_log_sanitization_removes_secrets_from_messages_and_nested_values() -> None:
    message = "request failed Authorization: Bearer top-secret visitor@example.com"
    detail = {
        "reason": "password=hunter2",
        "items": ["https://example.test/path?resume_token=secret", "SSN 123-45-6789"],
        "nested": {"note": "Bearer another-secret"},
    }

    sanitize_message = getattr(app_log, "sanitize_log_message", lambda value: value)
    cleaned_message = sanitize_message(message)
    cleaned_detail = app_log.sanitize_log_detail(detail)
    serialized = f"{cleaned_message} {cleaned_detail}"

    assert "top-secret" not in serialized
    assert "visitor@example.com" not in serialized
    assert "hunter2" not in serialized
    assert "resume_token" not in serialized
    assert "another-secret" not in serialized
    assert "123-45-6789" not in serialized
    assert "[redacted]" in serialized


def test_production_site_urls_require_https_but_local_development_can_use_http() -> None:
    secure_origin = getattr(site_admin, "validate_site_origin", lambda value, **_: value)
    privacy_url = getattr(site_admin, "validate_privacy_url", lambda value, **_: value)

    assert secure_origin("http://localhost:3000", production=False) == "http://localhost:3000"
    assert privacy_url("http://localhost:3000/privacy", production=False).startswith("http://")
    with pytest.raises(ValueError):
        secure_origin("http://sample-site.example.com", production=True)
    with pytest.raises(ValueError):
        privacy_url("http://sample-site.example.com/privacy", production=True)


def test_embed_snippet_keeps_hostile_keys_inside_the_script_element() -> None:
    snippet = site_admin.build_snippet(
        "demo</script><script>alert(1)</script>",
        "public<key",
        "https://widget.example",
    )

    assert "</script><script>" not in snippet
    assert "\\u003c/script>" in snippet
    assert "\\u003ckey" in snippet
