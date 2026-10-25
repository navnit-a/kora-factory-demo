import httpx
import pytest
import respx
from fastmcp import Client
from fastmcp.exceptions import ToolError

from factory_tools.trello import server
from tests.tools.trello_helpers import API, CARD, LISTS, form, run

WATCH_LOG = "🛰 Agent ops watch log"
LOG_ID = "0123456789abcdef0123456f"
OTHER_ID = "0123456789abcdef0123456e"
LOG_TEXT = "Last run 01:12: read 4 runs and 1 Blocked cards.\n- Nothing needed attention."
NOTE = "Agent ops: platform for run r-1: the tester was refused contents:write."


@pytest.fixture(autouse=True)
def configured(monkeypatch):
    monkeypatch.setenv("TRELLO_API_KEY", "k")
    monkeypatch.setenv("TRELLO_TOKEN", "t")
    monkeypatch.setenv("TRELLO_BOARD_ID", "board")


async def call(tool: str, /, **arguments):
    async with Client(server.mcp) as client:
        return (await client.call_tool(tool, arguments)).data


def sealed() -> respx.MockRouter:
    return respx.mock(assert_all_mocked=True, assert_all_called=False)


def mock_board_lists(router: respx.MockRouter) -> None:
    router.get(f"{API}/boards/board/lists").mock(return_value=httpx.Response(200, json=LISTS))


def mock_agent_ops_lane(router: respx.MockRouter, cards: list[dict]) -> None:
    mock_board_lists(router)
    router.get(f"{API}/lists/l-agent-ops/cards").mock(return_value=httpx.Response(200, json=cards))


def mock_blocked_card(router: respx.MockRouter, list_id: str) -> None:
    mock_board_lists(router)
    card = {"id": CARD, "idBoard": "board", "idList": list_id, "labels": []}
    router.get(f"{API}/cards/{CARD}").mock(return_value=httpx.Response(200, json=card))
    router.get(f"{API}/boards/board/labels").mock(
        return_value=httpx.Response(200, json=[{"id": "lab-ops", "name": "🛰 Agent ops"}])
    )


async def listed_tools() -> dict:
    async with Client(server.mcp) as client:
        return {tool.name: tool for tool in await client.list_tools()}


def test_watch_log_tool_takes_no_card_id_and_bounds_its_text():
    listed = run(listed_tools())
    properties = listed["trello_write_watch_log"].input_schema["properties"]
    assert set(properties) == {"text"}
    assert (properties["text"]["minLength"], properties["text"]["maxLength"]) == (1, 16384)
    note = listed["trello_mark_diagnosed"].input_schema["properties"]["note"]
    assert (note["minLength"], note["maxLength"]) == (3, 2000)


def test_write_watch_log_targets_only_the_watch_log_card():
    cards = [{"id": OTHER_ID, "name": "Pinned note"}, {"id": LOG_ID, "name": WATCH_LOG}]
    with sealed() as router:
        mock_agent_ops_lane(router, cards)
        log_put = router.put(f"{API}/cards/{LOG_ID}").mock(
            return_value=httpx.Response(200, json={})
        )
        log_comment = router.post(f"{API}/cards/{LOG_ID}/actions/comments").mock(
            return_value=httpx.Response(200, json={"id": "a1"})
        )
        other_put = router.put(f"{API}/cards/{OTHER_ID}")
        result = run(call("trello_write_watch_log", text=LOG_TEXT))
    assert result == {"id": LOG_ID, "description_updated": True, "comment_id": "a1"}
    assert form(log_put.calls[0].request) == {"desc": LOG_TEXT}
    assert form(log_comment.calls[0].request)["text"] == LOG_TEXT.splitlines()[0]
    assert not other_put.called


@pytest.mark.parametrize(
    ("cards", "message"),
    [
        ([{"id": OTHER_ID, "name": "Pinned note"}], "No card titled '🛰 Agent ops watch log'"),
        (
            [{"id": LOG_ID, "name": WATCH_LOG}, {"id": OTHER_ID, "name": WATCH_LOG}],
            "2 cards titled '🛰 Agent ops watch log'",
        ),
    ],
)
def test_write_watch_log_refuses_when_the_card_is_missing_or_duplicated(cards, message):
    with sealed() as router:
        mock_agent_ops_lane(router, cards)
        writes = (
            router.put(f"{API}/cards/{LOG_ID}"),
            router.put(f"{API}/cards/{OTHER_ID}"),
            router.post(f"{API}/cards/{LOG_ID}/actions/comments"),
            router.post(f"{API}/cards/{OTHER_ID}/actions/comments"),
        )
        with pytest.raises(ToolError, match=message):
            run(call("trello_write_watch_log", text=LOG_TEXT))
    assert not any(route.called for route in writes)


def test_write_watch_log_needs_a_first_line_before_any_call():
    with sealed() as router:
        lists = router.get(f"{API}/boards/board/lists")
        with pytest.raises(ToolError, match="first line"):
            run(call("trello_write_watch_log", text="\n  \n"))
    assert not lists.called


@pytest.mark.parametrize(
    ("list_id", "lane"),
    [("l-review", "Review"), ("l-agent-ops", "Agent ops"), ("l-gone", "a list outside")],
)
def test_mark_diagnosed_refuses_cards_outside_blocked(list_id, lane):
    with sealed() as router:
        mock_blocked_card(router, list_id)
        comment = router.post(f"{API}/cards/{CARD}/actions/comments")
        label = router.post(f"{API}/cards/{CARD}/idLabels")
        with pytest.raises(ToolError, match=f"is in {lane}.*not Blocked"):
            run(call("trello_mark_diagnosed", card_id=CARD, note=NOTE))
    assert not comment.called and not label.called


@pytest.mark.parametrize(
    "note", ["platform for run r-1", " Agent ops: late prefix", "agent ops: lower case"]
)
def test_mark_diagnosed_requires_the_agent_ops_prefix(note):
    with sealed() as router:
        card = router.get(f"{API}/cards/{CARD}")
        with pytest.raises(ToolError, match="must start with 'Agent ops:'"):
            run(call("trello_mark_diagnosed", card_id=CARD, note=note))
    assert not card.called


def recorded(order: list[str], step: str, reply: object):
    return lambda request: (order.append(step), httpx.Response(200, json=reply))[1]


def test_mark_diagnosed_comments_then_labels_a_blocked_card():
    order: list[str] = []
    with sealed() as router:
        mock_blocked_card(router, "l-blocked")
        comment = router.post(f"{API}/cards/{CARD}/actions/comments").mock(
            side_effect=recorded(order, "comment", {"id": "a2"})
        )
        label = router.post(f"{API}/cards/{CARD}/idLabels").mock(
            side_effect=recorded(order, "label", [])
        )
        result = run(call("trello_mark_diagnosed", card_id=CARD, note=NOTE))
    assert result == {"id": CARD, "label": "🛰 Agent ops", "comment_id": "a2"}
    assert form(comment.calls[0].request)["text"] == NOTE
    assert form(label.calls[0].request)["value"] == "lab-ops"
    assert order == ["comment", "label"]
