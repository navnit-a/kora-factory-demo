import os
from dataclasses import dataclass

import httpx
from fastmcp.exceptions import ToolError

from factory_tools.http import request, truncate
from factory_tools.lists import lists_sentence

API = "https://api.trello.com/1"
COMMENT_TAIL = 5
ENV_KEYS = ("TRELLO_API_KEY", "TRELLO_TOKEN", "TRELLO_BOARD_ID")
CARD_FIELDS = "id,name,desc,idList,shortUrl,dateLastActivity"
RETRY_HINT = "Check the card id and that the board still has that list."


@dataclass(frozen=True)
class TrelloClient:
    key: str
    token: str
    board_id: str
    http: httpx.AsyncClient

    @classmethod
    def from_env(cls, http: httpx.AsyncClient) -> "TrelloClient":
        values = {name: os.environ.get(name, "") for name in ENV_KEYS}
        missing = [name for name, value in values.items() if not value]
        if missing:
            raise ToolError(f"Trello is not configured: set {', '.join(missing)}")
        return cls(
            values["TRELLO_API_KEY"], values["TRELLO_TOKEN"], values["TRELLO_BOARD_ID"], http
        )

    async def list_ids(self) -> dict[str, str]:
        response = await self._get(f"/boards/{self.board_id}/lists", {"fields": "name"})
        return {item["name"]: item["id"] for item in response.json()}

    async def cards_in(self, list_name: str, limit: int) -> list[dict]:
        ids = await self.list_ids()
        list_id = _list_id(ids, list_name)
        response = await self._get(
            f"/lists/{list_id}/cards", {"fields": CARD_FIELDS, "limit": str(limit)}
        )
        return [_summary(card, list_name) for card in response.json()]

    async def card(self, card_id: str) -> dict:
        ids = await self.list_ids()
        names = {value: key for key, value in ids.items()}
        card = (await self._get(f"/cards/{card_id}", {"fields": CARD_FIELDS})).json()
        actions = (
            await self._get(
                f"/cards/{card_id}/actions", {"filter": "commentCard", "limit": str(COMMENT_TAIL)}
            )
        ).json()
        comments = [
            {"when": a.get("date", ""), "text": truncate(a.get("data", {}).get("text", ""))}
            for a in actions
        ]
        return {
            **_summary(card, names.get(card.get("idList"), "")),
            "description": truncate(card.get("desc", "")),
            "comments": comments,
        }

    async def move(self, card_id: str, to_list: str) -> dict:
        list_id = _list_id(await self.list_ids(), to_list)
        await self._put(f"/cards/{card_id}", {"idList": list_id})
        return {"id": card_id, "list": to_list}

    async def comment(self, card_id: str, text: str) -> dict:
        response = await self._post(f"/cards/{card_id}/actions/comments", {"text": text})
        return {"id": card_id, "comment_id": response.json().get("id", "")}

    async def create(self, list_name: str, title: str, description: str) -> dict:
        list_id = _list_id(await self.list_ids(), list_name)
        response = await self._post(
            "/cards", {"idList": list_id, "name": title, "desc": description}
        )
        body = response.json()
        return {"id": body.get("id", ""), "url": body.get("shortUrl", ""), "list": list_name}

    async def set_description(self, card_id: str, text: str) -> dict:
        await self._put(f"/cards/{card_id}", {"desc": text})
        return {"id": card_id, "description_updated": True}

    async def _get(self, path: str, params: dict) -> httpx.Response:
        return await self._call("GET", path, params)

    async def _put(self, path: str, params: dict) -> httpx.Response:
        return await self._call("PUT", path, params)

    async def _post(self, path: str, params: dict) -> httpx.Response:
        return await self._call("POST", path, params)

    async def _call(self, method: str, path: str, params: dict) -> httpx.Response:
        auth = {"key": self.key, "token": self.token}
        return await request(
            self.http, "Trello", method, API + path, RETRY_HINT, params={**params, **auth}
        )


def _list_id(ids: dict[str, str], list_name: str) -> str:
    if list_name not in ids:
        raise ToolError(f"No list named '{list_name}'. {lists_sentence()}")
    return ids[list_name]


def _summary(card: dict, list_name: str) -> dict:
    return {
        "id": card.get("id", ""),
        "title": card.get("name", ""),
        "list": list_name,
        "url": card.get("shortUrl", ""),
        "last_activity": card.get("dateLastActivity", ""),
    }
