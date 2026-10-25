from typing import Annotated

import httpx
from fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import Field

from factory_tools.lists import BOARD_LISTS, ListName
from factory_tools.trello.client import TrelloClient

READ = ToolAnnotations(read_only_hint=True, idempotent_hint=True, open_world_hint=True)
WRITE = ToolAnnotations(
    read_only_hint=False, destructive_hint=False, idempotent_hint=False, open_world_hint=True
)
LIST_DESCRIPTION = "One of the board's lists: " + ", ".join(BOARD_LISTS) + "."
CardId = Annotated[
    str, Field(description="The Trello card id from trello_list_cards or trello_get_card.")
]

mcp = FastMCP(
    "trello",
    instructions=(
        "Tools for the kora factory Trello board. Cards move between the lists "
        + ", ".join(BOARD_LISTS)
        + ". Read a card before changing it, and always give a reason when moving one."
    ),
)


def client() -> TrelloClient:
    return TrelloClient.from_env(httpx.AsyncClient())


@mcp.tool(annotations=READ)
async def trello_list_cards(
    list_name: Annotated[ListName, Field(description=LIST_DESCRIPTION)],
    limit: Annotated[
        int, Field(ge=1, le=50, description="Maximum cards to return, oldest first.")
    ] = 10,
) -> list[dict]:
    """List the cards in one list of the factory board: id, title, list, url and last activity."""
    return await client().cards_in(list_name, limit)


@mcp.tool(annotations=READ)
async def trello_get_card(card_id: CardId) -> dict:
    """Read one card in full: title, list, description and its last five comments, newest first."""
    return await client().card(card_id)


@mcp.tool(annotations=WRITE)
async def trello_move_card(
    card_id: CardId,
    to_list: Annotated[ListName, Field(description=LIST_DESCRIPTION)],
    reason: Annotated[
        str, Field(min_length=3, description="Why the card moves; posted as a comment.")
    ],
) -> dict:
    """Move a card to another list, posting the reason as a comment first."""
    trello = client()
    await trello.comment(card_id, reason)
    moved = await trello.move(card_id, to_list)
    return {**moved, "comment_posted": True}


@mcp.tool(annotations=WRITE)
async def trello_comment_card(
    card_id: CardId,
    text: Annotated[str, Field(min_length=1, description="The comment, in plain words.")],
) -> dict:
    """Add a comment to a card: what was done, what was checked, what is left."""
    return await client().comment(card_id, text)


@mcp.tool(annotations=WRITE)
async def trello_create_card(
    list_name: Annotated[ListName, Field(description=LIST_DESCRIPTION)],
    title: Annotated[str, Field(min_length=3, description="A short imperative title.")],
    description: Annotated[str, Field(description="The story or idea in full, Markdown allowed.")],
) -> dict:
    """Create a new card in a list of the factory board."""
    return await client().create(list_name, title, description)


@mcp.tool(annotations=WRITE)
async def trello_update_card_description(
    card_id: CardId,
    text: Annotated[str, Field(description="The new description; replaces the old one entirely.")],
) -> dict:
    """Replace a card's description, for example to turn an idea into a user story."""
    return await client().set_description(card_id, text)
