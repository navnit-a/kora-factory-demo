import os
import re
from dataclasses import dataclass

import httpx
from fastmcp.exceptions import ToolError

from factory_tools.http import json_or_error, request, truncate
from factory_tools.trello import card_view, checklist_client, lists_client, look_client
from factory_tools.trello.look import labels_on_create, signed_reason

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

    set_cover = look_client.set_cover
    stickers = look_client.stickers
    set_lane_sticker = look_client.set_lane_sticker
    set_star = look_client.set_star
    board_labels = look_client.board_labels
    ensure_label = look_client.ensure_label
    label_records = look_client.label_records
    rename_label = look_client.rename_label
    card_look = look_client.card_look
    card_labels = look_client.card_labels
    add_label = look_client.add_label
    remove_label = look_client.remove_label
    set_priority = look_client.set_priority
    add_checklist = checklist_client.add_checklist
    checklist_items = checklist_client.checklist_items
    check_item = checklist_client.check_item

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
        return lists_client.canonical_ids(await self.board_lists())

    async def board_lists(self) -> list[dict]:
        return await self._read(f"/boards/{self.board_id}/lists", {"fields": "name"})

    async def rename_list(self, list_id: str, name: str) -> None:
        await self._write("PUT", f"/lists/{list_id}", {"name": name})

    async def create_list(self, name: str, pos: str = "bottom") -> dict:
        query = {"name": name, "idBoard": self.board_id, "pos": pos}
        reply = await self._send_write("POST", "/lists", query)
        return {"id": look_client.required_id(reply, "list"), "name": name}

    async def cards_in(self, list_name: str, limit: int) -> list[dict]:
        list_id = lists_client.list_id(await self.board_lists(), list_name)
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
            **await card_view.labels_and_checklist(self, card_id),
        }

    async def move(self, card_id: str, to_list: str) -> dict:
        await self._board_card(card_id, "idBoard")
        list_id = lists_client.list_id(await self.board_lists(), to_list)
        await self._write("PUT", f"/cards/{card_id}", {"idList": list_id})
        return {"id": card_id, "list": to_list}

    async def move_with_reason(self, card_id: str, to_list: str, reason: str) -> dict:
        card = await self._board_card(card_id, "idBoard,idList")
        lists = await self.board_lists()
        list_id = lists_client.list_id(lists, to_list)
        from_list = lists_client.lane_of(lists, card.get("idList"))
        signed = signed_reason(from_list, to_list, reason)
        await self._write("POST", f"/cards/{card_id}/actions/comments", {"text": signed})
        await self._write("PUT", f"/cards/{card_id}", {"idList": list_id})
        look = await self.apply_look(card_id, to_list, reason)
        return {"id": card_id, "list": to_list, "comment_posted": True, **look}

    async def apply_look(
        self, card_id: str, to_list: str, reason: str, extra_labels: tuple[str, ...] = ()
    ) -> dict:
        failures = await look_client.dress(self, card_id, to_list, reason, extra_labels)
        return {"look_applied": not failures, "detail": "; ".join(failures)}

    async def comment(self, card_id: str, text: str) -> dict:
        await self._board_card(card_id, "idBoard")
        body = await self._write("POST", f"/cards/{card_id}/actions/comments", {"text": text})
        return {"id": card_id, "comment_id": body.get("id", "")}

    async def create(self, list_name: str, title: str, description: str) -> dict:
        list_id = lists_client.list_id(await self.board_lists(), list_name)
        body = await self._write(
            "POST", "/cards", {"idList": list_id, "name": title, "desc": description}
        )
        card_id = body.get("id", "")
        labels = labels_on_create(title, list_name)
        look = await self.apply_look(card_id, list_name, "", labels)
        created = {"id": card_id, "url": body.get("shortUrl", ""), "list": list_name}
        return {**created, "label": labels[0], **look}

    async def set_description(self, card_id: str, text: str) -> dict:
        await self._board_card(card_id, "idBoard")
        await self._write("PUT", f"/cards/{card_id}", {"desc": text})
        return {"id": card_id, "description_updated": True}

    async def archive(self, card_id: str) -> dict:
        await self._board_card(card_id, "idBoard")
        await self._write("PUT", f"/cards/{card_id}", {"closed": "true"})
        return {"id": card_id, "archived": True}

    def _checked_id(self, card_id: str) -> str:
        if not CARD_ID.match(card_id):
            raise ToolError(
                f"'{card_id}' is not a Trello card id; use an id from trello_list_cards."
            )
        return card_id

    async def _board_card(self, card_id: str, fields: str) -> dict:
        card = await self._read(f"/cards/{self._checked_id(card_id)}", {"fields": fields})
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
        return await self._send_write(method, path, data=fields)

    async def _write_json(self, method: str, path: str, payload: dict) -> dict:
        return await self._send_write(method, path, json=payload)

    async def _send_write(
        self, method: str, path: str, query: dict[str, str] | None = None, **body: dict
    ) -> dict:
        params = {**(query or {}), **self._auth()}
        response = await request(
            self.http, "Trello", method, API + path, WRITE_HINT, params=params, **body
        )
        reply = json_or_error(response, "Trello", WRITE_HINT)
        return reply if isinstance(reply, dict) else {}

    def _auth(self) -> dict[str, str]:
        return {"key": self.key, "token": self.token}


def _summary(card: dict, list_name: str) -> dict:
    return {
        "id": card.get("id", ""),
        "title": card.get("name", ""),
        "list": list_name,
        "url": card.get("shortUrl", ""),
        "last_activity": card.get("dateLastActivity", ""),
    }
