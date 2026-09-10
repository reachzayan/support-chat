import asyncio
import time

from app.services.kb_host_limiter import HostLimiter


async def test_same_host_waits_configured_delay() -> None:
    limiter = HostLimiter(delay_ms=40)
    started = time.monotonic()
    await limiter.wait("sample-site.example.com")
    await limiter.wait("sample-site.example.com")
    elapsed = time.monotonic() - started
    assert elapsed >= 0.04


async def test_different_hosts_wait_in_parallel() -> None:
    limiter = HostLimiter(delay_ms=50)
    await limiter.wait("sample-site.example.com")
    await limiter.wait("sample-services.example.com")

    async def hit(host: str) -> None:
        await limiter.wait(host)

    started = time.monotonic()
    await asyncio.gather(hit("sample-site.example.com"), hit("sample-services.example.com"))
    elapsed = time.monotonic() - started
    assert elapsed >= 0.05
    assert elapsed < 0.09
