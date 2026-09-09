import pytest

from tests.conftest import DEFAULT_TEST_REDIS_URL, _assert_test_redis_url


def test_default_test_redis_url_uses_dedicated_db_index() -> None:
    assert DEFAULT_TEST_REDIS_URL.endswith("/15")


def test_assert_test_redis_url_rejects_db_zero() -> None:
    with pytest.raises(RuntimeError, match="test"):
        _assert_test_redis_url("redis://:local-dev-redis@127.0.0.1:56379/0")


def test_assert_test_redis_url_rejects_production_host_on_db_zero() -> None:
    with pytest.raises(RuntimeError, match="test"):
        _assert_test_redis_url("redis://:secret@redis.prod.example.com:6379/0")


def test_assert_test_redis_url_accepts_dedicated_test_db_index() -> None:
    _assert_test_redis_url("redis://:local-dev-redis@127.0.0.1:56379/15")
