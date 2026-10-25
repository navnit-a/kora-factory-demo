import asyncio

import httpx
import pytest
import respx
from fastmcp import Client
from fastmcp.exceptions import ToolError

from factory_tools.trello import server

API = "https://api.trello.com/1"
LISTS = [{"id": f"l-{n.lower().replace(' ', '-')}", "name": n} for n in server.BOARD_LISTS]
EXPECTED_TOOLS = {
    "trello_list_cards",
    "trello_get_card",
    "trello_move_card",
    "trello_comment_card",
    "trello_create_card",
    "trello_update_card_description",
}


@pytest.fixture(autouse=True)
def configured(monkeypatch):
    monkeypatch.setenv("TRELLO_API_KEY", "k")
    monkeypatch.setenv("TRELLO_TOKEN", "t")
    monkeypatch.setenv("TRELLO_BOARD_ID", "board")


def run(coro):
    return asyncio.run(coro)


async def call(name: str, **arguments):
    async with Client(server.mcp) as client:
        return (await client.call_tool(name, arguments)).data


async def tools():
    async with Client(server.mcp) as client:
        return {tool.name: tool for tool in await client.list_tools()}


def test_tools_are_namespaced_and_annotated():
    listed = run(tools())
    assert set(listed) == EXPECTED_TOOLS
    assert listed["trello_list_cards"].annotations.read_only_hint is True
    assert listed["trello_get_card"].annotations.read_only_hint is True
    assert listed["trello_move_card"].annotations.destructive_hint is False
    assert listed["trello_move_card"].annotations.read_only_hint is not True


def test_every_tool_describes_itself_and_its_parameters():
    for tool in run(tools()).values():
        assert tool.description and len(tool.description) > 30
        for name, prop in tool.input_schema.get("properties", {}).items():
            assert prop.get("description"), f"{tool.name}.{name} has no description"


@respx.mock
def test_list_cards_defaults_to_ten():
    respx.get(f"{API}/boards/board/lists").mock(return_value=httpx.Response(200, json=LISTS))
    route = respx.get(f"{API}/lists/l-ready/cards").mock(return_value=httpx.Response(200, json=[]))
    assert run(call("trello_list_cards", list_name="Ready")) == []
    assert route.calls[0].request.url.params["limit"] == "10"


@respx.mock
def test_move_card_comments_the_reason_then_moves():
    respx.get(f"{API}/boards/board/lists").mock(return_value=httpx.Response(200, json=LISTS))
    respx.get(f"{API}/cards/0123456789abcdef0123456a").mock(
        return_value=httpx.Response(
            200, json={"id": "0123456789abcdef0123456a", "idBoard": "board"}
        )
    )
    order: list[str] = []
    respx.post(f"{API}/cards/0123456789abcdef0123456a/actions/comments").mock(
        side_effect=lambda request: (
            order.append("comment"),
            httpx.Response(200, json={"id": "a1"}),
        )[1]
    )
    respx.put(f"{API}/cards/0123456789abcdef0123456a").mock(
        side_effect=lambda request: (order.append("move"), httpx.Response(200, json={}))[1]
    )
    result = run(
        call(
            "trello_move_card",
            card_id="0123456789abcdef0123456a",
            to_list="Review",
            reason="PR #4 opened",
        )
    )
    assert order == ["comment", "move"]
    assert result == {"id": "0123456789abcdef0123456a", "list": "Review", "comment_posted": True}


def test_to_list_outside_the_board_is_rejected_before_any_call():
    with pytest.raises(ToolError):
        run(
            call(
                "trello_move_card",
                card_id="0123456789abcdef0123456a",
                to_list="Archive",
                reason="x",
            )
        )


@respx.mock
def test_get_card_returns_description_and_comments():
    respx.get(f"{API}/boards/board/lists").mock(return_value=httpx.Response(200, json=LISTS))
    respx.get(f"{API}/cards/0123456789abcdef0123456a").mock(
        return_value=httpx.Response(
            200,
            json={
                "id": "0123456789abcdef0123456a",
                "name": "T",
                "desc": "D",
                "idList": "l-ideas",
                "idBoard": "board",
                "shortUrl": "u",
            },
        )
    )
    respx.get(f"{API}/cards/0123456789abcdef0123456a/actions").mock(
        return_value=httpx.Response(200, json=[])
    )
    card = run(call("trello_get_card", card_id="0123456789abcdef0123456a"))
    assert card["description"] == "D" and card["list"] == "Ideas" and card["comments"] == []


@respx.mock
def test_create_card_and_update_description():
    respx.get(f"{API}/boards/board/lists").mock(return_value=httpx.Response(200, json=LISTS))
    respx.post(f"{API}/cards").mock(
        return_value=httpx.Response(200, json={"id": "0123456789abcdef0123456b", "shortUrl": "u"})
    )
    respx.put(f"{API}/cards/0123456789abcdef0123456b").mock(
        return_value=httpx.Response(200, json={})
    )
    respx.get(f"{API}/cards/0123456789abcdef0123456b").mock(
        return_value=httpx.Response(
            200, json={"id": "0123456789abcdef0123456b", "idBoard": "board"}
        )
    )
    created = run(call("trello_create_card", list_name="Ideas", title="Dark mode", description="d"))
    assert created["id"] == "0123456789abcdef0123456b"
    updated = run(
        call("trello_update_card_description", card_id="0123456789abcdef0123456b", text="story")
    )
    assert updated == {"id": "0123456789abcdef0123456b", "description_updated": True}
