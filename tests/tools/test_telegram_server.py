import asyncio

import httpx
import pytest
import respx
from fastmcp import Client
from fastmcp.exceptions import ToolError

from factory_tools.telegram import server

SEND = "https://api.telegram.org/bottoken123/sendMessage"


@pytest.fixture(autouse=True)
def configured(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "token123")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "-100777")
    monkeypatch.setenv("TELEGRAM_CHANNEL", "@kora_factory_demo")


async def send(text: str) -> dict:
    async with Client(server.mcp) as client:
        return (await client.call_tool("telegram_send_message", {"text": text})).data


def run(coro):
    return asyncio.run(coro)


@respx.mock
def test_send_message_posts_to_the_channel():
    route = respx.post(SEND).mock(
        return_value=httpx.Response(200, json={"ok": True, "result": {"message_id": 42}})
    )
    result = run(send("kora factory is online"))
    body = dict(httpx.QueryParams(route.calls[0].request.content.decode()))
    assert body == {"chat_id": "-100777", "text": "kora factory is online"}
    assert result == {"message_id": 42, "url": "https://t.me/kora_factory_demo/42"}


@respx.mock
def test_long_message_is_truncated_not_rejected():
    route = respx.post(SEND).mock(
        return_value=httpx.Response(200, json={"ok": True, "result": {"message_id": 1}})
    )
    run(send("x" * 5000))
    sent = dict(httpx.QueryParams(route.calls[0].request.content.decode()))["text"]
    assert len(sent) <= 4096
    assert sent.endswith("…(truncated)")


@respx.mock
def test_telegram_error_names_the_description():
    respx.post(SEND).mock(
        return_value=httpx.Response(
            400, json={"ok": False, "description": "Bad Request: chat not found"}
        )
    )
    with pytest.raises(ToolError, match="chat not found"):
        run(send("hi"))


def test_missing_token_is_a_clear_tool_error(monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN")
    with pytest.raises(ToolError, match="TELEGRAM_BOT_TOKEN"):
        run(send("hi"))


def test_tool_is_a_write_with_a_description():
    async def listed():
        async with Client(server.mcp) as client:
            return (await client.list_tools())[0]

    tool = run(listed())
    assert tool.name == "telegram_send_message"
    assert tool.annotations.read_only_hint is False
    assert tool.annotations.destructive_hint is False
    assert tool.input_schema["properties"]["text"]["description"]
