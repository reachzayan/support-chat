"""Run the real push worker with only the external gateway routed to local TLS."""

import asyncio
import os
import ssl

import httpx


class LocalGatewayTransport(httpx.AsyncBaseTransport):
    def __init__(self):
        context = ssl.create_default_context(cafile=os.environ["E2E_PUSH_CERT"])
        self.transport = httpx.AsyncHTTPTransport(verify=context)

    async def handle_async_request(self, request):
        assert request.url.host == "fcm.googleapis.com", "Unexpected external network request"
        request.url = request.url.copy_with(host="127.0.0.1", port=int(os.environ["E2E_PUSH_PORT"]))
        return await self.transport.handle_async_request(request)

    async def aclose(self):
        await self.transport.aclose()


async def main():
    # Preserve the real HTTP client, crypto, queue, database and worker loop.
    original_client = httpx.AsyncClient

    def gateway_client(**kwargs):
        return original_client(transport=LocalGatewayTransport(), **kwargs)

    httpx.AsyncClient = gateway_client
    from app.workers.push_notifications import start_push_notifications, stop_push_notifications

    await start_push_notifications()
    print("PUSH_WORKER_STARTED", flush=True)
    try:
        await asyncio.Event().wait()
    finally:
        await stop_push_notifications()


if __name__ == "__main__":
    asyncio.run(main())
