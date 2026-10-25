from __future__ import annotations

from typing import TYPE_CHECKING

from fastmcp.exceptions import ToolError

from factory_tools.trello.look import (
    COVER_STYLE,
    HIGH_SEVERITY,
    LABELS,
    LANE_LOOK,
    LANE_STICKER_POS,
    LANE_STICKERS,
    STAR,
    STAR_POS,
    LaneLook,
    labels_after_move,
)

if TYPE_CHECKING:
    from factory_tools.trello.client import TrelloClient


def required_id(reply: dict, what: str) -> str:
    found = reply.get("id")
    if not isinstance(found, str) or not found:
        raise ToolError(f"Trello did not return an id for the new {what}; try again.")
    return found


async def set_cover(client: TrelloClient, card_id: str, color: str | None) -> None:
    cover = {"color": color, **COVER_STYLE} if color else None
    await client._write_json("PUT", f"/cards/{client._checked_id(card_id)}", {"cover": cover})


async def stickers(client: TrelloClient, card_id: str) -> list[dict]:
    found = await client._read(f"/cards/{client._checked_id(card_id)}/stickers", {})
    return found if isinstance(found, list) else []


async def _add_sticker(client: TrelloClient, card_id: str, image: str, pos: dict) -> None:
    fields = {"image": image, **{key: str(value) for key, value in pos.items()}}
    await client._write("POST", f"/cards/{client._checked_id(card_id)}/stickers", fields)


async def _remove_stickers(client: TrelloClient, card_id: str, images: frozenset[str]) -> None:
    for sticker in await stickers(client, card_id):
        if sticker.get("image") in images and sticker.get("id"):
            await client._write("DELETE", f"/cards/{card_id}/stickers/{sticker['id']}", {})


async def set_lane_sticker(client: TrelloClient, card_id: str, image: str | None) -> None:
    await _remove_stickers(client, card_id, LANE_STICKERS)
    if image is not None:
        await _add_sticker(client, card_id, image, LANE_STICKER_POS)


async def set_star(client: TrelloClient, card_id: str, on: bool) -> None:
    if not on:
        await _remove_stickers(client, card_id, frozenset({STAR}))
        return
    images = {sticker.get("image") for sticker in await stickers(client, card_id)}
    if STAR not in images:
        await _add_sticker(client, card_id, STAR, STAR_POS)


async def board_labels(client: TrelloClient) -> dict[str, str]:
    found = await client._read(f"/boards/{client.board_id}/labels", {"fields": "id,name,color"})
    labels = found if isinstance(found, list) else []
    return {label["name"]: label["id"] for label in labels if label.get("name") and label.get("id")}


async def label_records(client: TrelloClient) -> dict[str, dict]:
    found = await client._read(f"/boards/{client.board_id}/labels", {"fields": "id,name,color"})
    labels = found if isinstance(found, list) else []
    return {
        label["id"]: {"name": label.get("name") or "", "color": label.get("color")}
        for label in labels
        if isinstance(label.get("id"), str) and label["id"]
    }


async def rename_label(client: TrelloClient, label_id: str, name: str) -> None:
    await client._write("PUT", f"/labels/{label_id}", {"name": name})


def _label_look(label: dict) -> dict:
    name, color = label.get("name"), label.get("color")
    return {
        "name": name if isinstance(name, str) else "",
        "color": color if isinstance(color, str) and color else None,
    }


async def card_look(client: TrelloClient, card_id: str) -> dict:
    card = await client._board_card(card_id, "idBoard,desc,cover,labels")
    labels = card.get("labels", [])
    if not isinstance(labels, list):
        raise ToolError(f"Trello sent card {card_id}'s labels in an unexpected shape; try again.")
    cover = card.get("cover")
    color = cover.get("color") if isinstance(cover, dict) else None
    return {
        "cover": color if isinstance(color, str) and color else None,
        "description": card.get("desc") or "",
        "labels": tuple(_label_look(label) for label in labels if isinstance(label, dict)),
    }


async def ensure_label(client: TrelloClient, name: str) -> str:
    if name not in LABELS:
        known = ", ".join(LABELS)
        raise ToolError(f"No label named '{name}' in the board language. Use one of: {known}.")
    existing = await board_labels(client)
    if name in existing:
        return existing[name]
    fields = {"name": name, "color": LABELS[name], "idBoard": client.board_id}
    return required_id(await client._write("POST", "/labels", fields), "label")


async def _card_label_ids(client: TrelloClient, card_id: str) -> dict[str, str]:
    card = await client._board_card(card_id, "idBoard,labels")
    return {label.get("name", ""): label.get("id", "") for label in card.get("labels", [])}


async def card_labels(client: TrelloClient, card_id: str) -> tuple[str, ...]:
    return tuple(name for name in await _card_label_ids(client, card_id) if name)


async def _attach(client: TrelloClient, card_id: str, name: str) -> None:
    label_id = await ensure_label(client, name)
    await client._write("POST", f"/cards/{card_id}/idLabels", {"value": label_id})


async def _detach(client: TrelloClient, card_id: str, label_id: str) -> None:
    await client._write("DELETE", f"/cards/{card_id}/idLabels/{label_id}", {})


async def add_label(client: TrelloClient, card_id: str, name: str) -> dict:
    present = name in await card_labels(client, card_id)
    if not present:
        await _attach(client, card_id, name)
    return {"id": card_id, "label": name, "added": not present}


async def remove_label(client: TrelloClient, card_id: str, name: str) -> dict:
    label_id = (await _card_label_ids(client, card_id)).get(name)
    if label_id:
        await _detach(client, card_id, label_id)
    return {"id": card_id, "label": name, "removed": bool(label_id)}


async def relabel(
    client: TrelloClient, card_id: str, to_list: str, reason: str, extra: tuple[str, ...]
) -> None:
    current = await _card_label_ids(client, card_id)
    names = tuple(dict.fromkeys((*(name for name in current if name), *extra)))
    wanted = labels_after_move(names, to_list, reason)
    for name in (name for name in wanted if name not in current):
        await _attach(client, card_id, name)
    for name, label_id in current.items():
        if name and name not in wanted:
            await _detach(client, card_id, label_id)


async def dress(
    client: TrelloClient, card_id: str, to_list: str, reason: str, extra: tuple[str, ...]
) -> None:
    look = LANE_LOOK.get(to_list, LaneLook(None, None))
    await set_cover(client, card_id, look.cover)
    await set_lane_sticker(client, card_id, look.sticker)
    await relabel(client, card_id, to_list, reason, extra)


async def set_priority(client: TrelloClient, card_id: str, high: bool) -> dict:
    label = add_label if high else remove_label
    await label(client, card_id, HIGH_SEVERITY)
    await set_star(client, card_id, high)
    return {"id": card_id, "high": high}
