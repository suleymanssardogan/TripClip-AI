import asyncio
import httpx
from app.core import internal_client as pooling


def test_pool_reuses_transport_with_isolated_cookies_headers_and_timeouts(monkeypatch):
    async def scenario():
        seen = []
        async def respond(request):
            seen.append(request)
            return httpx.Response(200, headers={"set-cookie": "private=value"}, json={"ok": True})
        transport = httpx.MockTransport(respond)
        monkeypatch.setattr(pooling, "_transport", transport)
        async with pooling.internal_client(15) as first:
            first.headers["x-user-id"] = "1"
            await first.get("http://core.invalid/test")
            assert first.cookies.get("private") == "value"
            assert first.timeout.read == 15
        async with pooling.internal_client(45) as second:
            assert not second.cookies
            assert second.timeout.read == 45
            assert second.timeout.pool == 5
            await second.get("http://core.invalid/test")
        assert seen[0].headers["x-user-id"] == "1"
        assert "x-user-id" not in seen[1].headers
        assert "cookie" not in seen[1].headers
        await transport.aclose()
    asyncio.run(scenario())


def test_lifespan_closes_shared_pool():
    async def scenario():
        async with pooling.client_lifespan(None):
            transport = pooling._transport
            assert transport is not None
            async with pooling.internal_client(10) as client:
                assert client._transport.transport is transport
            assert pooling._transport is transport
        assert pooling._transport is None
    asyncio.run(scenario())


def test_page_validation_happens_before_upstream_call(client, auth_headers, mock_core_api):
    path = "/api/mobile/trips" if "Mobile" in client.app.title else "/api/web/trips"
    for query in ("limit=0", "limit=51", "offset=-1"):
        assert client.get(f"{path}?{query}", headers=auth_headers).status_code == 422
    mock_core_api.get.assert_not_called()
