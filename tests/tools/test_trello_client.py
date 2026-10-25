import asyncio

import httpx
import pytest
import respx
from fastmcp.exceptions import ToolError

from factory_tools.trello.client import TrelloClient

API = "https://api.trello.com/1"
LISTS = [
    {"id": "l-ideas", "name": "Ideas"},
    {"id": "l-backlog", "name": "Backlog"},
    {"id": "l-ready", "name": "Ready"},
    {"id": "l-progress", "name": "In Progress"},
    {"id": "l-review", "name": "Review"},
    {"id": "l-testing", "name": "Testing"},
    {"id": "l-done", "name": "Done"},
    {"id": "l-blocked", "name": "Blocked"},
]


def form(request: httpx.Request) -> dict:
    return dict(httpx.QueryParams(request.content.decode()))


def client() -> TrelloClient:
    return TrelloClient("key", "token", "board", httpx.AsyncClient())


def run(coro):
    return asyncio.run(coro)


def mock_lists(lists: list[dict] = LISTS) -> respx.Route:
    return respx.get(f"{API}/boards/board/lists").mock(return_value=httpx.Response(200, json=lists))


@respx.mock
def test_list_ids_resolves_names_at_call_time():
    renamed = [{**item, "id": "l-ideas-new"} if item["name"] == "Ideas" else item for item in LISTS]
    respx.get(f"{API}/boards/board/lists").mock(
        side_effect=[httpx.Response(200, json=LISTS), httpx.Response(200, json=renamed)]
    )
    c = client()
    assert run(c.list_ids())["Ideas"] == "l-ideas"
    assert run(c.list_ids())["Ideas"] == "l-ideas-new"


@respx.mock
def test_cards_in_unknown_list_names_the_lists():
    mock_lists([{"id": "l-ideas", "name": "Ideas"}])
    with pytest.raises(
        ToolError, match="No list named 'Review' on the board. The board has: Ideas"
    ):
        run(client().cards_in("Review", 10))


@respx.mock
def test_cards_in_requests_the_list_id_with_a_limit():
    mock_lists()
    route = respx.get(f"{API}/lists/l-ready/cards").mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "id": "0123456789abcdef0123456a",
                    "name": "Add now and next",
                    "shortUrl": "https://trello.com/c/c1",
                    "dateLastActivity": "2026-10-25T01:00:00.000Z",
                }
            ],
        )
    )
    cards = run(client().cards_in("Ready", 10))
    assert cards == [
        {
            "id": "0123456789abcdef0123456a",
            "title": "Add now and next",
            "list": "Ready",
            "url": "https://trello.com/c/c1",
            "last_activity": "2026-10-25T01:00:00.000Z",
        }
    ]
    assert route.calls[0].request.url.params["limit"] == "10"


@respx.mock
def test_card_includes_last_five_comments_truncated():
    mock_lists()
    respx.get(f"{API}/cards/0123456789abcdef0123456a").mock(
        return_value=httpx.Response(
            200,
            json={
                "id": "0123456789abcdef0123456a",
                "name": "Add now and next",
                "desc": "d" * 1300,
                "idList": "l-review",
                "idBoard": "board",
                "shortUrl": "https://trello.com/c/c1",
                "dateLastActivity": "2026-10-25T01:00:00.000Z",
            },
        )
    )
    actions = respx.get(f"{API}/cards/0123456789abcdef0123456a/actions").mock(
        return_value=httpx.Response(
            200,
            json=[{"date": "2026-10-25T00:59:00.000Z", "data": {"text": "x" * 1300}}],
        )
    )
    card = run(client().card("0123456789abcdef0123456a"))
    assert card["list"] == "Review"
    assert card["description"].endswith(" (truncated)")
    assert card["comments"] == [
        {"when": "2026-10-25T00:59:00.000Z", "text": "x" * 1200 + " (truncated)"}
    ]
    params = actions.calls[0].request.url.params
    assert params["filter"] == "commentCard" and params["limit"] == "5"


@respx.mock
def test_move_sends_the_target_list_id():
    mock_lists()
    respx.get(f"{API}/cards/0123456789abcdef0123456a").mock(
        return_value=httpx.Response(
            200, json={"id": "0123456789abcdef0123456a", "idBoard": "board"}
        )
    )
    put = respx.put(f"{API}/cards/0123456789abcdef0123456a").mock(
        return_value=httpx.Response(
            200, json={"id": "0123456789abcdef0123456a", "idList": "l-done"}
        )
    )
    moved = run(client().move("0123456789abcdef0123456a", "Done"))
    assert form(put.calls[0].request)["idList"] == "l-done"
    assert moved == {"id": "0123456789abcdef0123456a", "list": "Done"}


@respx.mock
def test_create_posts_to_the_list_id():
    mock_lists()
    post = respx.post(f"{API}/cards").mock(
        return_value=httpx.Response(
            200, json={"id": "0123456789abcdef0123456b", "shortUrl": "https://trello.com/c/c9"}
        )
    )
    created = run(client().create("Ideas", "Dark mode", "Attendees in a dim hall"))
    fields = form(post.calls[0].request)
    assert fields["idList"] == "l-ideas" and fields["name"] == "Dark mode"
    assert created == {
        "id": "0123456789abcdef0123456b",
        "url": "https://trello.com/c/c9",
        "list": "Ideas",
    }


@respx.mock
def test_comment_and_description_use_their_endpoints():
    respx.get(f"{API}/cards/0123456789abcdef0123456a").mock(
        return_value=httpx.Response(
            200, json={"id": "0123456789abcdef0123456a", "idBoard": "board"}
        )
    )
    comment = respx.post(f"{API}/cards/0123456789abcdef0123456a/actions/comments").mock(
        return_value=httpx.Response(200, json={"id": "a1"})
    )
    desc = respx.put(f"{API}/cards/0123456789abcdef0123456a").mock(
        return_value=httpx.Response(200, json={"id": "0123456789abcdef0123456a"})
    )
    assert run(client().comment("0123456789abcdef0123456a", "done")) == {
        "id": "0123456789abcdef0123456a",
        "comment_id": "a1",
    }
    assert form(comment.calls[0].request)["text"] == "done"
    assert run(client().set_description("0123456789abcdef0123456a", "new")) == {
        "id": "0123456789abcdef0123456a",
        "description_updated": True,
    }
    assert form(desc.calls[0].request)["desc"] == "new"


@respx.mock
def test_429_surfaces_the_wait():
    respx.get(f"{API}/boards/board/lists").mock(
        return_value=httpx.Response(429, headers={"Retry-After": "3"})
    )
    with pytest.raises(ToolError, match="Trello is rate limiting; try again in 3s"):
        run(client().list_ids())


def test_from_env_reads_the_three_variables(monkeypatch):
    monkeypatch.setenv("TRELLO_API_KEY", "k")
    monkeypatch.setenv("TRELLO_TOKEN", "t")
    monkeypatch.setenv("TRELLO_BOARD_ID", "b")
    c = TrelloClient.from_env(httpx.AsyncClient())
    assert (c.key, c.token, c.board_id) == ("k", "t", "b")


def test_from_env_names_a_missing_variable(monkeypatch):
    monkeypatch.delenv("TRELLO_TOKEN", raising=False)
    monkeypatch.setenv("TRELLO_API_KEY", "k")
    monkeypatch.setenv("TRELLO_BOARD_ID", "b")
    with pytest.raises(ToolError, match="TRELLO_TOKEN"):
        TrelloClient.from_env(httpx.AsyncClient())


@pytest.mark.parametrize("bad", ["../boards/x", "c1/actions", "abc def", "", "x" * 30])
def test_card_ids_that_are_not_trello_ids_are_rejected_before_any_call(bad):
    with pytest.raises(ToolError, match="not a Trello card id"):
        run(client().card(bad))


@respx.mock
def test_a_card_on_another_board_is_refused():
    respx.get(f"{API}/cards/0123456789abcdef01234567").mock(
        return_value=httpx.Response(
            200, json={"id": "0123456789abcdef01234567", "idBoard": "other"}
        )
    )
    move = respx.put(f"{API}/cards/0123456789abcdef01234567")
    with pytest.raises(ToolError, match="not on the factory board"):
        run(client().move("0123456789abcdef01234567", "Done"))
    assert not move.called


@respx.mock
def test_missing_list_error_names_the_lists_the_board_really_has():
    mock_lists([{"id": "l-ideas", "name": "Ideas"}, {"id": "l-cr", "name": "Code review"}])
    with pytest.raises(ToolError) as caught:
        run(client().cards_in("Review", 10))
    message = str(caught.value)
    assert "No list named 'Review' on the board" in message
    assert "The board has: Code review, Ideas" in message


@respx.mock
def test_writes_send_text_in_the_form_body_not_the_url():
    respx.get(f"{API}/cards/0123456789abcdef0123456a").mock(
        return_value=httpx.Response(200, json={"idBoard": "board"})
    )
    route = respx.post(f"{API}/cards/0123456789abcdef0123456a/actions/comments").mock(
        return_value=httpx.Response(200, json={"id": "a1"})
    )
    run(client().comment("0123456789abcdef0123456a", "x" * 5000))
    request = route.calls[0].request
    assert "text" not in request.url.params
    assert dict(httpx.QueryParams(request.content.decode()))["text"] == "x" * 5000


@respx.mock
def test_non_json_reply_is_a_tool_error_with_a_next_step():
    respx.get(f"{API}/boards/board/lists").mock(
        return_value=httpx.Response(200, text="<html>maintenance</html>")
    )
    with pytest.raises(ToolError, match="Trello sent a reply that is not JSON"):
        run(client().list_ids())


CARD = "0123456789abcdef0123456a"


@respx.mock
def test_archive_closes_a_card_on_the_board():
    respx.get(f"{API}/cards/{CARD}").mock(
        return_value=httpx.Response(200, json={"id": CARD, "idBoard": "board"})
    )
    put = respx.put(f"{API}/cards/{CARD}").mock(
        return_value=httpx.Response(200, json={"id": CARD, "closed": True})
    )
    assert run(client().archive(CARD)) == {"id": CARD, "archived": True}
    assert form(put.calls[0].request) == {"closed": "true"}


@respx.mock
def test_archive_refuses_a_card_on_another_board():
    respx.get(f"{API}/cards/{CARD}").mock(
        return_value=httpx.Response(200, json={"id": CARD, "idBoard": "elsewhere"})
    )
    with pytest.raises(ToolError, match="not on the factory board"):
        run(client().archive(CARD))


@respx.mock
def test_archive_failure_never_shows_the_credentials():
    respx.get(f"{API}/cards/{CARD}").mock(
        return_value=httpx.Response(200, json={"id": CARD, "idBoard": "board"})
    )
    respx.put(f"{API}/cards/{CARD}").mock(return_value=httpx.Response(500, text="oops"))
    with pytest.raises(ToolError) as caught:
        run(client().archive(CARD))
    assert "token" not in str(caught.value)
    assert "key=" not in str(caught.value)


def test_no_tool_can_archive():
    from factory_demo.tools_check import expected_tool_names

    assert not [name for name in expected_tool_names() if "archive" in name or "delete" in name]
