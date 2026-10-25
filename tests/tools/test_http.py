import asyncio

import httpx
import pytest
import respx
from fastmcp.exceptions import ToolError

from factory_tools.http import request, truncate, upstream_error


def test_truncate_marks_cut_text():
    cut = truncate("a" * 1300)
    assert cut.endswith(" (truncated)")
    assert len(cut) == 1212
    assert truncate("short") == "short"


def test_upstream_error_carries_service_status_body_and_hint():
    response = httpx.Response(503, text="x" * 300)
    error = upstream_error("Overpass", response, "Try again in a minute.")
    assert isinstance(error, ToolError)
    assert str(error).startswith("Overpass returned HTTP 503: " + "x" * 200)
    assert str(error).endswith("Try again in a minute.")


@respx.mock
def test_request_retries_once_on_429_then_raises_with_the_wait():
    route = respx.get("https://x.test/a").mock(
        side_effect=[
            httpx.Response(429, headers={"Retry-After": "0"}),
            httpx.Response(429, headers={"Retry-After": "7"}),
        ]
    )

    async def go() -> None:
        async with httpx.AsyncClient() as client:
            await request(client, "Trello", "GET", "https://x.test/a", hint="")

    with pytest.raises(ToolError, match="try again in 7s"):
        asyncio.run(go())
    assert route.call_count == 2


@respx.mock
def test_request_raises_a_tool_error_with_status_body_and_hint():
    respx.get("https://x.test/a").mock(return_value=httpx.Response(500, text="boom"))

    async def go() -> None:
        async with httpx.AsyncClient() as client:
            await request(
                client, "Overpass", "GET", "https://x.test/a", hint="Try a smaller radius."
            )

    with pytest.raises(ToolError, match="Overpass returned HTTP 500: boom. Try a smaller radius."):
        asyncio.run(go())


@respx.mock
def test_request_returns_the_response_on_success():
    respx.get("https://x.test/a").mock(return_value=httpx.Response(200, json={"ok": True}))

    async def go() -> dict:
        async with httpx.AsyncClient() as client:
            return (await request(client, "Trello", "GET", "https://x.test/a", hint="")).json()

    assert asyncio.run(go()) == {"ok": True}
