"""Per-request clients share the lifespan-owned transport, never cookies or headers."""
from contextlib import asynccontextmanager
import os
import httpx

INTERNAL_API_SECRET = os.getenv("INTERNAL_API_SECRET", "")
_transport = None


class BorrowedTransport(httpx.AsyncBaseTransport):
    def __init__(self, transport):
        self.transport = transport

    async def handle_async_request(self, request):
        return await self.transport.handle_async_request(request)

    async def aclose(self):
        # Only the application lifespan closes the shared connection pool.
        pass


@asynccontextmanager
async def client_lifespan(app):
    global _transport
    transport = httpx.AsyncHTTPTransport(limits=httpx.Limits(
        max_connections=100, max_keepalive_connections=20, keepalive_expiry=30), retries=0)
    _transport = transport
    try:
        yield
    finally:
        _transport = None
        await transport.aclose()


def internal_client(timeout: float) -> httpx.AsyncClient:
    headers = {"X-Internal-Secret": INTERNAL_API_SECRET} if INTERNAL_API_SECRET else {}
    transport = BorrowedTransport(_transport) if _transport is not None else None
    return httpx.AsyncClient(timeout=httpx.Timeout(timeout, connect=5, pool=5),
                             headers=headers, transport=transport)
