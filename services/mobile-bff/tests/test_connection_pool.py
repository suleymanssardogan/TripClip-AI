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


def test_video_page_parameters_and_metadata_survive_proxy(client, auth_headers, mock_core_api, make_response):
    mock_core_api.get.return_value = make_response(200, {"plans": [], "total": 24,
        "limit": 20, "offset": 20, "has_more": False})
    response = client.get("/api/mobile/videos?limit=20&offset=20", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["offset"] == 20
    assert response.json()["total"] == 24
    assert mock_core_api.get.call_args.kwargs["params"] == {"limit": 20, "offset": 20}


def test_video_list_upstream_error_is_not_reported_as_empty_success(client, auth_headers, mock_core_api, make_response):
    mock_core_api.get.return_value = make_response(503, {"code": "SERVICE_UNAVAILABLE", "message": "Unavailable"})
    assert client.get("/api/mobile/videos", headers=auth_headers).status_code >= 400
