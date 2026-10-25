import os
import re
from dataclasses import dataclass

import httpx
from fastmcp.exceptions import ToolError

from factory_tools.http import json_or_error, request, truncate
from factory_tools.lists import lists_sentence

API = "https://api.trello.com/1"
COMMENT_TAIL = 5
ENV_KEYS = ("TRELLO_API_KEY", "TRELLO_TOKEN", "TRELLO_BOARD_ID")
CARD_FIELDS = "id,name,desc,idList,idBoard,shortUrl,dateLastActivity"
CARD_ID = re.compile(r"^(?:[0-9a-fA-F]{24}|[A-Za-z0-9]{8})$")
READ_HINT = "Check the card id with trello_list_cards and try again."
WRITE_HINT = "Check the text is under 16,384 characters and the card is still on the board."


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
        lists = await self._read(f"/boards/{self.board_id}/lists", {"fields": "name"})
        return {item["name"]: item["id"] for item in lists}

    async def cards_in(self, list_name: str, limit: int) -> list[dict]:
        list_id = _list_id(await self.list_ids(), list_name)
        cards = await self._read(
            f"/lists/{list_id}/cards", {"fields": CARD_FIELDS, "limit": str(limit)}
        )
        return [_summary(card, list_name) for card in cards]

    async def card(self, card_id: str) -> dict:
        card = await self._board_card(card_id, CARD_FIELDS)
        names = {value: key for key, value in (await self.list_ids()).items()}
        actions = await self._read(
            f"/cards/{card_id}/actions", {"filter": "commentCard", "limit": str(COMMENT_TAIL)}
        )
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
        await self._board_card(card_id, "idBoard")
        list_id = _list_id(await self.list_ids(), to_list)
        await self._write("PUT", f"/cards/{card_id}", {"idList": list_id})
        return {"id": card_id, "list": to_list}

    async def move_with_reason(self, card_id: str, to_list: str, reason: str) -> dict:
        await self._board_card(card_id, "idBoard")
        list_id = _list_id(await self.list_ids(), to_list)
        await self._write("POST", f"/cards/{card_id}/actions/comments", {"text": reason})
        await self._write("PUT", f"/cards/{card_id}", {"idList": list_id})
        return {"id": card_id, "list": to_list, "comment_posted": True}

    async def comment(self, card_id: str, text: str) -> dict:
        await self._board_card(card_id, "idBoard")
        body = await self._write("POST", f"/cards/{card_id}/actions/comments", {"text": text})
        return {"id": card_id, "comment_id": body.get("id", "")}

    async def create(self, list_name: str, title: str, description: str) -> dict:
        list_id = _list_id(await self.list_ids(), list_name)
        body = await self._write(
            "POST", "/cards", {"idList": list_id, "name": title, "desc": description}
        )
        return {"id": body.get("id", ""), "url": body.get("shortUrl", ""), "list": list_name}

    async def set_description(self, card_id: str, text: str) -> dict:
        await self._board_card(card_id, "idBoard")
        await self._write("PUT", f"/cards/{card_id}", {"desc": text})
        return {"id": card_id, "description_updated": True}

    async def _board_card(self, card_id: str, fields: str) -> dict:
        if not CARD_ID.match(card_id):
            raise ToolError(
                f"'{card_id}' is not a Trello card id; use an id from trello_list_cards."
            )
        card = await self._read(f"/cards/{card_id}", {"fields": fields})
        if card.get("idBoard") != self.board_id:
            raise ToolError(
                f"Card {card_id} is not on the factory board; only its cards can be used."
            )
        return card

    async def _read(self, path: str, params: dict) -> dict | list:
        response = await request(
            self.http, "Trello", "GET", API + path, READ_HINT, params={**params, **self._auth()}
        )
        return json_or_error(response, "Trello", READ_HINT)

    async def _write(self, method: str, path: str, fields: dict) -> dict:
        response = await request(
            self.http, "Trello", method, API + path, WRITE_HINT, params=self._auth(), data=fields
        )
        body = json_or_error(response, "Trello", WRITE_HINT)
        return body if isinstance(body, dict) else {}

    def _auth(self) -> dict[str, str]:
        return {"key": self.key, "token": self.token}


def _list_id(ids: dict[str, str], list_name: str) -> str:
    if list_name not in ids:
        board = ", ".join(sorted(ids)) or "no lists"
        raise ToolError(
            f"No list named '{list_name}' on the board. The board has: {board}. "
            f"The factory expects: {lists_sentence().removeprefix('Lists are: ')}"
        )
    return ids[list_name]


def _summary(card: dict, list_name: str) -> dict:
    return {
        "id": card.get("id", ""),
        "title": card.get("name", ""),
        "list": list_name,
        "url": card.get("shortUrl", ""),
        "last_activity": card.get("dateLastActivity", ""),
    }
