import asyncio

import httpx
import pytest
import respx
from fastmcp import Client
from fastmcp.exceptions import ToolError

from factory_tools.trello import server

API = "https://api.trello.com/1"
CID = "0123456789abcdef0123456a"
LISTS = [{"id": f"l-{n.lower().replace(' ', '-')}", "name": n} for n in server.BOARD_LISTS]
EXPECTED_TOOLS = {
    "trello_list_cards",
    "trello_get_card",
    "trello_move_card",
    "trello_comment_card",
    "trello_create_card",
    "trello_update_card_description",
    "trello_add_label",
    "trello_add_checklist",
    "trello_check_item",
    "trello_set_priority",
}


@pytest.fixture(autouse=True)
def configured(monkeypatch):
    monkeypatch.setenv("TRELLO_API_KEY", "k")
    monkeypatch.setenv("TRELLO_TOKEN", "t")
    monkeypatch.setenv("TRELLO_BOARD_ID", "board")


def run(coro):
    return asyncio.run(coro)


async def call(tool: str, /, **arguments):
    async with Client(server.mcp) as client:
        return (await client.call_tool(tool, arguments)).data


def mock_look_reads(card_id: str, board_labels: list[dict] | None = None) -> None:
    respx.get(f"{API}/cards/{card_id}/stickers").mock(return_value=httpx.Response(200, json=[]))
    respx.post(f"{API}/cards/{card_id}/stickers").mock(
        return_value=httpx.Response(200, json={"id": "s"})
    )
    respx.get(f"{API}/boards/board/labels").mock(
        return_value=httpx.Response(200, json=board_labels or [])
    )
    respx.post(f"{API}/cards/{card_id}/idLabels").mock(return_value=httpx.Response(200, json=[]))


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
        side_effect=lambda request: (order.append("put"), httpx.Response(200, json={}))[1]
    )
    mock_look_reads(CID, [{"id": "lab-cr", "name": "🔍 Code reviewer"}])
    result = run(
        call(
            "trello_move_card",
            card_id="0123456789abcdef0123456a",
            to_list="Review",
            reason="PR #4 opened",
        )
    )
    assert order == ["comment", "put", "put"]
    assert result == {
        "id": "0123456789abcdef0123456a",
        "list": "Review",
        "comment_posted": True,
        "look_applied": True,
        "detail": "",
    }


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
    respx.get(f"{API}/cards/0123456789abcdef0123456a/checklists").mock(
        return_value=httpx.Response(200, json=[])
    )
    card = run(call("trello_get_card", card_id="0123456789abcdef0123456a"))
    assert card["description"] == "D" and card["list"] == "Ideas" and card["comments"] == []
    assert card["labels"] == [] and card["checklist"] == []


def test_get_card_description_names_labels_and_the_checklist():
    tool = run(tools())["trello_get_card"]
    assert "labels" in tool.description
    assert "Acceptance criteria" in tool.description


def test_move_card_says_the_comment_is_signed_and_the_actor_label_set():
    tool = run(tools())["trello_move_card"]
    assert "signed by the lane the card leaves" in tool.description
    assert "actor label" in tool.description
    labels = run(tools())["trello_add_label"].input_schema["properties"]["name"]
    assert "🤖 Senior developer" in str(labels)


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
    mock_look_reads(
        "0123456789abcdef0123456b",
        [{"id": "lab-idea", "name": "Idea"}, {"id": "lab-po", "name": "💡 Product owner"}],
    )
    created = run(call("trello_create_card", list_name="Ideas", title="Dark mode", description="d"))
    assert created["id"] == "0123456789abcdef0123456b"
    assert created["label"] == "Idea" and created["look_applied"] is True
    updated = run(
        call("trello_update_card_description", card_id="0123456789abcdef0123456b", text="story")
    )
    assert updated == {"id": "0123456789abcdef0123456b", "description_updated": True}


@respx.mock
def test_move_to_a_renamed_list_posts_no_comment():
    renamed = [item for item in LISTS if item["name"] != "Review"] + [
        {"id": "l-cr", "name": "Code review"}
    ]
    respx.get(f"{API}/boards/board/lists").mock(return_value=httpx.Response(200, json=renamed))
    respx.get(f"{API}/cards/{CID}").mock(
        return_value=httpx.Response(200, json={"idBoard": "board"})
    )
    comment = respx.post(f"{API}/cards/{CID}/actions/comments")
    with pytest.raises(ToolError, match="The board has: .*Code review"):
        run(call("trello_move_card", card_id=CID, to_list="Review", reason="PR opened"))
    assert not comment.called


def test_text_fields_cap_at_trellos_limit():
    with pytest.raises(ToolError):
        run(call("trello_comment_card", card_id=CID, text="x" * 16385))


def test_the_look_tools_are_writes_that_say_who_uses_them():
    listed = run(tools())
    owners = {
        "trello_add_label": "product owner",
        "trello_add_checklist": "product owner",
        "trello_check_item": "tester",
        "trello_set_priority": "delivery lead",
    }
    for name, owner in owners.items():
        assert listed[name].annotations.read_only_hint is False
        assert listed[name].annotations.destructive_hint is False
        assert owner in listed[name].description.lower(), name


def test_add_checklist_bounds_its_items():
    schema = run(tools())["trello_add_checklist"].input_schema["properties"]["items"]
    assert (schema["minItems"], schema["maxItems"]) == (3, 8)
    assert (schema["items"]["minLength"], schema["items"]["maxLength"]) == (3, 200)


def sealed() -> respx.MockRouter:
    return respx.mock(assert_all_mocked=True, assert_all_called=False)


def test_the_sealed_mock_lets_no_request_leave_the_process():
    with sealed(), pytest.raises(respx.models.AllMockedAssertionError):
        httpx.get(f"{API}/cards/{CID}")


@pytest.mark.parametrize(
    ("items", "message"),
    [
        (["one thing", "two things"], "List should have at least 3 items"),
        (["a criterion"] * 9, "List should have at most 8 items"),
        (["ok criterion", "no", "fine criterion"], "String should have at least 3 characters"),
        (
            ["ok criterion", "x" * 201, "fine criterion"],
            "String should have at most 200 characters",
        ),
    ],
)
def test_add_checklist_rejects_items_out_of_bounds_before_any_call(items, message):
    with sealed() as router:
        card = router.get(f"{API}/cards/{CID}").mock(
            return_value=httpx.Response(200, json={"id": CID, "idBoard": "board"})
        )
        with pytest.raises(ToolError, match=f"validation error(?s:.*){message}"):
            run(call("trello_add_checklist", card_id=CID, items=items))
    assert card.called is False


def test_add_label_accepts_only_the_palette():
    with sealed() as router:
        card = router.get(f"{API}/cards/{CID}").mock(
            return_value=httpx.Response(200, json={"id": CID, "idBoard": "board", "labels": []})
        )
        with pytest.raises(ToolError, match="validation error(?s:.*)Input should be 'Idea'"):
            run(call("trello_add_label", card_id=CID, name="Urgent"))
    assert card.called is False


@respx.mock
def test_add_label_check_item_and_priority_reach_trello():
    respx.get(f"{API}/cards/{CID}").mock(
        return_value=httpx.Response(200, json={"id": CID, "idBoard": "board", "labels": []})
    )
    mock_look_reads(CID, [{"id": "lab-high", "name": "High severity"}])
    respx.post(f"{API}/labels").mock(return_value=httpx.Response(200, json={"id": "lab-new"}))
    respx.get(f"{API}/cards/{CID}/checklists").mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "id": "cl",
                    "name": "Acceptance criteria",
                    "checkItems": [{"id": "i1", "name": "Stars persist", "state": "incomplete"}],
                }
            ],
        )
    )
    respx.put(f"{API}/cards/{CID}/checkItem/i1").mock(return_value=httpx.Response(200, json={}))
    labelled = run(call("trello_add_label", card_id=CID, name="Depends on"))
    assert labelled == {"id": CID, "label": "Depends on", "added": True}
    ticked = run(call("trello_check_item", card_id=CID, text="Stars persist"))
    assert ticked["already_complete"] is False
    assert run(call("trello_set_priority", card_id=CID, high=True)) == {"id": CID, "high": True}


@respx.mock
def test_add_checklist_reaches_trello():
    respx.get(f"{API}/cards/{CID}").mock(
        return_value=httpx.Response(200, json={"id": CID, "idBoard": "board"})
    )
    respx.get(f"{API}/cards/{CID}/checklists").mock(return_value=httpx.Response(200, json=[]))
    respx.post(f"{API}/cards/{CID}/checklists").mock(
        return_value=httpx.Response(200, json={"id": "cl"})
    )
    items = respx.post(f"{API}/checklists/cl/checkItems").mock(
        return_value=httpx.Response(200, json={"id": "i"})
    )
    criteria = ["Stars persist", "Header counts", "Works offline"]
    result = run(call("trello_add_checklist", card_id=CID, items=criteria))
    assert result == {"id": CID, "checklist_items": 3}
    assert items.call_count == 3
