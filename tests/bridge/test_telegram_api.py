import json

import httpx
import pytest
import respx
from fastmcp.exceptions import ToolError

from factory_bridge.telegram_api import Message, TelegramBot, private_message

TOKEN = "123:abc"
UPDATES = f"https://api.telegram.org/bot{TOKEN}/getUpdates"
SEND = f"https://api.telegram.org/bot{TOKEN}/sendMessage"


def update(chat_type: str = "private", text: str | None = "/idea hello there", **extra) -> dict:
    message = {
        "message_id": 9,
        "date": 1_700_000_000,
        "chat": {"id": 42, "type": chat_type},
        "from": {"id": 7, "is_bot": False, "first_name": "Ana"},
        **({"text": text} if text is not None else {}),
        **extra,
    }
    return {"update_id": 100, "message": message}


def test_private_message_reads_the_fields():
    assert private_message(update()) == Message(
        update_id=100,
        chat_id=42,
        user_id=7,
        first_name="Ana",
        text="/idea hello there",
        date=1_700_000_000,
    )


@pytest.mark.parametrize("chat_type", ["channel", "group", "supergroup"])
def test_private_message_ignores_channels_and_groups(chat_type):
    assert private_message(update(chat_type)) is None


def test_private_message_ignores_updates_without_text():
    assert private_message(update(text=None)) is None
    assert private_message({"update_id": 1, "edited_message": {}}) is None


def test_private_message_ignores_malformed_ids():
    broken = update()
    broken["message"]["from"] = {"id": "7", "first_name": "Ana"}
    assert private_message(broken) is None


def test_private_message_tolerates_a_missing_first_name():
    plain = update()
    plain["message"]["from"] = {"id": 7}
    assert private_message(plain).first_name == ""


@respx.mock
async def test_get_updates_uses_allowed_updates_and_offset():
    route = respx.post(UPDATES).mock(
        return_value=httpx.Response(200, json={"ok": True, "result": [update()]})
    )
    async with httpx.AsyncClient() as http:
        updates = await TelegramBot(TOKEN, http).get_updates(101, timeout_s=20)
    assert updates == [update()]
    body = json.loads(route.calls.last.request.content)
    assert body == {"offset": 101, "timeout": 20, "allowed_updates": ["message"]}
    assert route.calls.last.request.extensions["timeout"]["read"] == 30


@respx.mock
async def test_get_updates_rejects_a_reply_without_results():
    respx.post(UPDATES).mock(return_value=httpx.Response(200, json={"ok": True}))
    async with httpx.AsyncClient() as http:
        with pytest.raises(ToolError, match="getUpdates"):
            await TelegramBot(TOKEN, http).get_updates(0)


@respx.mock
async def test_get_updates_rejects_an_update_without_an_id():
    respx.post(UPDATES).mock(
        return_value=httpx.Response(200, json={"ok": True, "result": [{"message": {}}]})
    )
    async with httpx.AsyncClient() as http:
        with pytest.raises(ToolError, match="update_id"):
            await TelegramBot(TOKEN, http).get_updates(0)


@respx.mock
async def test_get_updates_surfaces_http_errors_as_tool_errors():
    respx.post(UPDATES).mock(
        return_value=httpx.Response(409, json={"ok": False, "description": "Conflict"})
    )
    async with httpx.AsyncClient() as http:
        with pytest.raises(ToolError, match="409"):
            await TelegramBot(TOKEN, http).get_updates(0)


@respx.mock
async def test_send_posts_plain_text_without_parse_mode():
    route = respx.post(SEND).mock(return_value=httpx.Response(200, json={"ok": True}))
    async with httpx.AsyncClient() as http:
        await TelegramBot(TOKEN, http).send(42, "a *b* _c_ `d`")
    assert json.loads(route.calls.last.request.content) == {"chat_id": 42, "text": "a *b* _c_ `d`"}
