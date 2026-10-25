from __future__ import annotations

from typing import TYPE_CHECKING

from fastmcp.exceptions import ToolError

from factory_tools.trello.look import CHECKLIST_NAME
from factory_tools.trello.look_client import required_id

if TYPE_CHECKING:
    from factory_tools.trello.client import TrelloClient

COMPLETE = "complete"
ADD_HINT = "the product owner adds them with trello_add_checklist"


async def _checklists(client: TrelloClient, card_id: str) -> list[dict]:
    await client._board_card(card_id, "idBoard")
    found = await client._read(f"/cards/{card_id}/checklists", {})
    return found if isinstance(found, list) else []


def _criteria(checklists: list[dict]) -> tuple[dict, ...]:
    return tuple(
        item
        for checklist in checklists
        if checklist.get("name") == CHECKLIST_NAME
        for item in checklist.get("checkItems", [])
        if item.get("id")
    )


async def add_checklist(client: TrelloClient, card_id: str, items: tuple[str, ...]) -> dict:
    if not items:
        raise ToolError(f"Give the card at least one acceptance criterion; {ADD_HINT}.")
    for checklist in await _checklists(client, card_id):
        if checklist.get("name") == CHECKLIST_NAME and checklist.get("id"):
            await client._write("DELETE", f"/checklists/{checklist['id']}", {})
    created = await client._write("POST", f"/cards/{card_id}/checklists", {"name": CHECKLIST_NAME})
    checklist_id = required_id(created, "checklist")
    for item in items:
        await client._write(
            "POST", f"/checklists/{checklist_id}/checkItems", {"name": item, "checked": "false"}
        )
    return {"id": card_id, "checklist_items": len(items)}


async def checklist_items(client: TrelloClient, card_id: str) -> tuple[tuple[str, str], ...]:
    criteria = _criteria(await _checklists(client, card_id))
    return tuple((item.get("name", ""), item.get("state", "")) for item in criteria)


def _match(items: tuple[dict, ...], text: str) -> dict | None:
    exact = next((item for item in items if item.get("name") == text), None)
    wanted = text.strip().casefold()
    if exact or not wanted:
        return exact
    return next(
        (item for item in items if item.get("name", "").casefold().startswith(wanted)), None
    )


def _no_match(text: str, items: tuple[dict, ...]) -> ToolError:
    if not items:
        return ToolError(f"The card has no {CHECKLIST_NAME} checklist yet; {ADD_HINT}.")
    names = "; ".join(f"'{item.get('name', '')}'" for item in items)
    return ToolError(
        f"No acceptance criterion matches '{text}'. The card's {CHECKLIST_NAME} are: {names}. "
        "Use the exact text, or its first words."
    )


async def check_item(client: TrelloClient, card_id: str, text: str) -> dict:
    items = _criteria(await _checklists(client, card_id))
    item = _match(items, text)
    if item is None:
        raise _no_match(text, items)
    name = item.get("name", "")
    if item.get("state") == COMPLETE:
        return {"id": card_id, "item": name, "already_complete": True}
    await client._write("PUT", f"/cards/{card_id}/checkItem/{item['id']}", {"state": COMPLETE})
    return {"id": card_id, "item": name, "already_complete": False}
