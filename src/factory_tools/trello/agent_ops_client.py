from __future__ import annotations

from typing import TYPE_CHECKING

from fastmcp.exceptions import ToolError

from factory_tools.trello import lists_client, look_client
from factory_tools.trello.look import (
    AGENT_OPS,
    AGENT_OPS_LABEL,
    AGENT_OPS_PREFIX,
    BLOCKED,
    WATCH_LOG_TITLE,
)

if TYPE_CHECKING:
    from factory_tools.trello.client import TrelloClient

OUTSIDE_LANES = "a list outside the factory lanes"


def _first_line(text: str) -> str:
    line = next((line.strip() for line in text.splitlines() if line.strip()), "")
    if not line:
        raise ToolError("The watch log needs a first line with text; nothing was written.")
    return line


async def _watch_log_id(client: TrelloClient) -> str:
    list_id = lists_client.list_id(await client.board_lists(), AGENT_OPS)
    found = await client._read(f"/lists/{list_id}/cards", {"fields": "id,name"})
    cards = found if isinstance(found, list) else []
    ids = tuple(card.get("id", "") for card in cards if card.get("name") == WATCH_LOG_TITLE)
    if not ids:
        raise ToolError(
            f"No card titled '{WATCH_LOG_TITLE}' in the {AGENT_OPS} lane; nothing was written. "
            "The operator creates it with scripts/dress-board.py."
        )
    if len(ids) > 1:
        raise ToolError(
            f"{len(ids)} cards titled '{WATCH_LOG_TITLE}' in the {AGENT_OPS} lane; nothing was "
            "written. The operator must archive all but one."
        )
    return ids[0]


async def write_watch_log(client: TrelloClient, text: str) -> dict:
    line = _first_line(text)
    card_id = await _watch_log_id(client)
    await client._write("PUT", f"/cards/{card_id}", {"desc": text})
    reply = await client._write("POST", f"/cards/{card_id}/actions/comments", {"text": line})
    return {"id": card_id, "description_updated": True, "comment_id": reply.get("id", "")}


def _checked_note(note: str) -> str:
    if not note.startswith(AGENT_OPS_PREFIX):
        raise ToolError(f"The note must start with '{AGENT_OPS_PREFIX}'; nothing was written.")
    return note


async def _require_blocked(client: TrelloClient, card_id: str) -> None:
    card = await client._board_card(card_id, "idBoard,idList")
    lane = lists_client.lane_of(await client.board_lists(), card.get("idList"))
    if lane != BLOCKED:
        raise ToolError(
            f"Card {card_id} is in {lane or OUTSIDE_LANES}, not {BLOCKED}; agent ops marks only "
            f"{BLOCKED} cards. Nothing was written."
        )


async def mark_diagnosed(client: TrelloClient, card_id: str, note: str) -> dict:
    checked = _checked_note(note)
    await _require_blocked(client, card_id)
    reply = await client._write("POST", f"/cards/{card_id}/actions/comments", {"text": checked})
    await look_client.add_label(client, card_id, AGENT_OPS_LABEL)
    return {"id": card_id, "label": AGENT_OPS_LABEL, "comment_id": reply.get("id", "")}
