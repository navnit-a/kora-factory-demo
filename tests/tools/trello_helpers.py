import asyncio
import json

import httpx
import respx

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
    {"id": "l-agent-ops", "name": "Agent ops"},
]


def form(request: httpx.Request) -> dict:
    return dict(httpx.QueryParams(request.content.decode()))


def body(request: httpx.Request) -> dict:
    return json.loads(request.content)


def mock_look(
    card_id: str,
    stickers: list[dict] | None = None,
    card_labels: list[dict] | None = None,
    board_labels: list[dict] | None = None,
    list_id: str | None = None,
) -> dict[str, respx.Route]:
    card = {"id": card_id, "idBoard": "board", "idList": list_id, "labels": card_labels or []}
    return {
        "card": respx.get(f"{API}/cards/{card_id}").mock(
            return_value=httpx.Response(200, json=card)
        ),
        "put": respx.put(f"{API}/cards/{card_id}").mock(return_value=httpx.Response(200, json={})),
        "stickers": respx.get(f"{API}/cards/{card_id}/stickers").mock(
            return_value=httpx.Response(200, json=stickers or [])
        ),
        "add_sticker": respx.post(f"{API}/cards/{card_id}/stickers").mock(
            return_value=httpx.Response(200, json={"id": "s-new"})
        ),
        "board_labels": respx.get(f"{API}/boards/board/labels").mock(
            return_value=httpx.Response(200, json=board_labels or [])
        ),
        "new_label": respx.post(f"{API}/labels").mock(
            return_value=httpx.Response(200, json={"id": "lab-new"})
        ),
        "add_label": respx.post(f"{API}/cards/{card_id}/idLabels").mock(
            return_value=httpx.Response(200, json=[])
        ),
    }


def client() -> TrelloClient:
    return TrelloClient("key", "token", "board", httpx.AsyncClient())


def run(coro):
    return asyncio.run(coro)


def mock_lists(lists: list[dict] = LISTS) -> respx.Route:
    return respx.get(f"{API}/boards/board/lists").mock(return_value=httpx.Response(200, json=lists))


CARD = "0123456789abcdef0123456a"


def delete_route(path: str) -> respx.Route:
    return respx.delete(f"{API}{path}").mock(return_value=httpx.Response(200, json={}))


def comment_route() -> respx.Route:
    return respx.post(f"{API}/cards/{CARD}/actions/comments").mock(
        return_value=httpx.Response(200, json={"id": "a1"})
    )
