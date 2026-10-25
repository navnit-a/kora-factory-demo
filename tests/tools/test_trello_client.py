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
    with pytest.raises(ToolError, match="No list named 'Review'. Lists are: Ideas, Backlog"):
        run(client().cards_in("Review", 10))


@respx.mock
def test_cards_in_requests_the_list_id_with_a_limit():
    mock_lists()
    route = respx.get(f"{API}/lists/l-ready/cards").mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "id": "c1",
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
            "id": "c1",
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
    respx.get(f"{API}/cards/c1").mock(
        return_value=httpx.Response(
            200,
            json={
                "id": "c1",
                "name": "Add now and next",
                "desc": "d" * 1300,
                "idList": "l-review",
                "shortUrl": "https://trello.com/c/c1",
                "dateLastActivity": "2026-10-25T01:00:00.000Z",
            },
        )
    )
    actions = respx.get(f"{API}/cards/c1/actions").mock(
        return_value=httpx.Response(
            200,
            json=[{"date": "2026-10-25T00:59:00.000Z", "data": {"text": "x" * 1300}}],
        )
    )
    card = run(client().card("c1"))
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
    put = respx.put(f"{API}/cards/c1").mock(
        return_value=httpx.Response(200, json={"id": "c1", "idList": "l-done"})
    )
    moved = run(client().move("c1", "Done"))
    assert put.calls[0].request.url.params["idList"] == "l-done"
    assert moved == {"id": "c1", "list": "Done"}


@respx.mock
def test_create_posts_to_the_list_id():
    mock_lists()
    post = respx.post(f"{API}/cards").mock(
        return_value=httpx.Response(200, json={"id": "c9", "shortUrl": "https://trello.com/c/c9"})
    )
    created = run(client().create("Ideas", "Dark mode", "Attendees in a dim hall"))
    params = post.calls[0].request.url.params
    assert params["idList"] == "l-ideas" and params["name"] == "Dark mode"
    assert created == {"id": "c9", "url": "https://trello.com/c/c9", "list": "Ideas"}


@respx.mock
def test_comment_and_description_use_their_endpoints():
    comment = respx.post(f"{API}/cards/c1/actions/comments").mock(
        return_value=httpx.Response(200, json={"id": "a1"})
    )
    desc = respx.put(f"{API}/cards/c1").mock(return_value=httpx.Response(200, json={"id": "c1"}))
    assert run(client().comment("c1", "done")) == {"id": "c1", "comment_id": "a1"}
    assert comment.calls[0].request.url.params["text"] == "done"
    assert run(client().set_description("c1", "new")) == {"id": "c1", "description_updated": True}
    assert desc.calls[0].request.url.params["desc"] == "new"


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
