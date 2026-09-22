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

    async def peek(self, bucket: str, *parts: str) -> int:
        try:
            raw = await get_redis().get(self._key(bucket, *parts))
        except Exception as exc:
            raise RateLimitUnavailable() from exc
        return int(raw) if raw is not None else 0

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

    async def guard_login(self, email: str, ip: str | None) -> None:
        settings = self._settings
        email_count = await self.peek("login-email", self._login_email_key(email))
        ip_count = await self.peek("login-ip", self._login_ip_key(ip))
        if email_count >= settings.rate_login_failure or ip_count >= settings.rate_login_failure:
            raise RateLimitExceeded()

    async def hit_login_failure(self, email: str, ip: str | None) -> None:
        settings = self._settings
        await self.hit(
            "login-email",
            settings.rate_login_failure,
            settings.rate_login_failure_window,
            self._login_email_key(email),
        )
        await self.hit(
            "login-ip",
            settings.rate_login_failure,
            settings.rate_login_failure_window,
            self._login_ip_key(ip),
        )
