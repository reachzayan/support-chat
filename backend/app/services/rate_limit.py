from hashlib import sha256
from hmac import new as hmac_new

from app.redis import get_redis
from app.settings import Settings, get_settings


class RateLimitExceeded(Exception):
    pass


class RateLimitUnavailable(Exception):
    pass


INCR_EXPIRE = """
local current = redis.call("incr", KEYS[1])
if current == 1 then
    redis.call("expire", KEYS[1], tonumber(ARGV[1]))
end
return current
"""

RESERVE_LOGIN = """
local budget = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
for _, key in ipairs(KEYS) do
    local current = tonumber(redis.call("get", key) or "0")
    if current >= budget then
        return 0
    end
end
for _, key in ipairs(KEYS) do
    local current = redis.call("incr", key)
    if current == 1 then
        redis.call("expire", key, window)
    end
end
return 1
"""

RELEASE_LOGIN = """
for _, key in ipairs(KEYS) do
    local current = tonumber(redis.call("get", key) or "0")
    if current <= 1 then
        redis.call("del", key)
    else
        redis.call("decr", key)
    end
end
return 1
"""


class RateLimiter:
    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()

    def hash_value(self, value: str) -> str:
        return hmac_new(
            self._settings.rate_key_secret.encode("utf-8"),
            value.encode("utf-8"),
            sha256,
        ).hexdigest()

    def _key(self, bucket: str, *parts: str) -> str:
        return "rate:" + bucket + ":" + ":".join(parts)

    async def hit(self, bucket: str, budget: int, window: int, *parts: str) -> None:
        key = self._key(bucket, *parts)
        try:
            count = int(await get_redis().eval(INCR_EXPIRE, 1, key, str(window)))
        except Exception as exc:
            raise RateLimitUnavailable() from exc
        if count > budget:
            raise RateLimitExceeded()

    async def hit_bootstrap(self, ip: str | None, site_key: str) -> None:
        settings = self._settings
        await self.hit(
            "bootstrap",
            settings.rate_bootstrap,
            settings.rate_bootstrap_window,
            self.hash_value(ip or "none"),
            self.hash_value(site_key),
        )

    async def hit_widget_csp(self, ip: str | None, site_key: str, public_key: str) -> None:
        settings = self._settings
        await self.hit(
            "widget-csp-ip",
            settings.rate_widget_csp_ip,
            settings.rate_widget_csp_window,
            self.hash_value(ip or "none"),
        )
        await self.hit(
            "widget-csp-site",
            settings.rate_widget_csp_site,
            settings.rate_widget_csp_window,
            self.hash_value(f"{site_key}:{public_key}"),
        )

    async def hit_visitor_create(self, ip: str | None, site_id: str) -> None:
        settings = self._settings
        await self.hit(
            "visitor-new",
            settings.rate_visitor_create,
            settings.rate_visitor_create_window,
            self.hash_value(ip or "none"),
            site_id,
        )

    async def hit_visitor_submit(self, site_id: str, visitor_id: str, ip: str | None) -> None:
        settings = self._settings
        await self.hit(
            "visitor-sub",
            settings.rate_visitor_submit,
            settings.rate_visitor_submit_window,
            site_id,
            visitor_id,
        )
        await self.hit(
            "visitor-sub-ip",
            settings.rate_visitor_submit_ip,
            settings.rate_visitor_submit_ip_window,
            self.hash_value(ip or "none"),
        )

    def _login_email_key(self, email: str) -> str:
        return self.hash_value(email.strip().lower())

    def _login_ip_key(self, ip: str | None) -> str:
        return self.hash_value(ip or "none")

    async def reserve_login(self, email: str, ip: str | None) -> None:
        settings = self._settings
        keys = (
            self._key("login-email", self._login_email_key(email)),
            self._key("login-ip", self._login_ip_key(ip)),
        )
        try:
            admitted = int(
                await get_redis().eval(
                    RESERVE_LOGIN,
                    len(keys),
                    *keys,
                    str(settings.rate_login_failure),
                    str(settings.rate_login_failure_window),
                )
            )
        except Exception as exc:
            raise RateLimitUnavailable() from exc
        if not admitted:
            raise RateLimitExceeded()

    async def release_login(self, email: str, ip: str | None) -> None:
        keys = (
            self._key("login-email", self._login_email_key(email)),
            self._key("login-ip", self._login_ip_key(ip)),
        )
        try:
            await get_redis().eval(RELEASE_LOGIN, len(keys), *keys)
        except Exception:
            # A successful credential check must not fail solely because cleanup
            # failed; the reservation expires and therefore fails conservatively.
            return
