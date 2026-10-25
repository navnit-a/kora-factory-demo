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


def test_serve_binds_to_loopback_unless_told_otherwise(monkeypatch):
    from factory_tools.serve import bind_host

    monkeypatch.delenv("BIND_HOST", raising=False)
    assert bind_host() == "127.0.0.1"
    monkeypatch.setenv("BIND_HOST", "0.0.0.0")
    assert bind_host() == "0.0.0.0"


def test_client_waits_longer_than_overpass_query_timeout():
    from factory_tools.http import DEFAULT_TIMEOUT_S

    assert DEFAULT_TIMEOUT_S > 25


def test_no_tool_uses_a_docstring_for_its_description():
    import inspect

    from factory_tools.places import server as places
    from factory_tools.telegram import server as telegram
    from factory_tools.transport import server as transport
    from factory_tools.trello import server as trello

    for module in (trello, telegram, transport, places):
        for name, fn in inspect.getmembers(module, inspect.iscoroutinefunction):
            if name.startswith(("trello_", "telegram_", "transport_", "places_")):
                assert fn.__doc__ is None, f"{module.__name__}.{name} has a docstring"
