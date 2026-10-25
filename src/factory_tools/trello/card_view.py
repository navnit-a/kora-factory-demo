from __future__ import annotations

from typing import TYPE_CHECKING

from factory_tools.trello import checklist_client, look_client

if TYPE_CHECKING:
    from factory_tools.trello.client import TrelloClient


async def labels_and_checklist(client: TrelloClient, card_id: str) -> dict:
    look = await look_client.card_look(client, card_id)
    items = await checklist_client.checklist_items(client, card_id)
    return {
        "labels": [label["name"] for label in look["labels"] if label["name"]],
        "checklist": [{"text": text, "state": state} for text, state in items],
    }
