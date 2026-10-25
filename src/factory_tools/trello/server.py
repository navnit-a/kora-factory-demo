from collections.abc import Awaitable, Callable
from typing import Annotated

import httpx
from fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import Field

from factory_tools.lists import BOARD_LISTS, ListName
from factory_tools.trello.client import TrelloClient
from factory_tools.trello.look import CHECKLIST_NAME, LABELS, LabelName

TRELLO_TEXT_LIMIT = 16384
READ = ToolAnnotations(read_only_hint=True, idempotent_hint=True, open_world_hint=True)
WRITE = ToolAnnotations(
    read_only_hint=False, destructive_hint=False, idempotent_hint=False, open_world_hint=True
)
LIST_DESCRIPTION = "One of the board's lists: " + ", ".join(BOARD_LISTS) + "."
LABEL_DESCRIPTION = "One label of the board language: " + ", ".join(LABELS) + "."
Criterion = Annotated[str, Field(min_length=3, max_length=200)]
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


async def with_trello[T](action: Callable[[TrelloClient], Awaitable[T]]) -> T:
    async with httpx.AsyncClient() as http:
        return await action(TrelloClient.from_env(http))


def text_field(description: str, min_length: int = 1):
    return Field(min_length=min_length, max_length=TRELLO_TEXT_LIMIT, description=description)


@mcp.tool(
    annotations=READ,
    description="List the cards in one list of the factory board, in board order, top first: "
    "id, title, list, url and last activity.",
)
async def trello_list_cards(
    list_name: Annotated[ListName, Field(description=LIST_DESCRIPTION)],
    limit: Annotated[
        int, Field(ge=1, le=50, description="Maximum cards to return, top of the list first.")
    ] = 10,
) -> list[dict]:
    return await with_trello(lambda trello: trello.cards_in(list_name, limit))


@mcp.tool(
    annotations=READ,
    description="Read one card in full: title, list, description and its last five comments, "
    "newest first.",
)
async def trello_get_card(card_id: CardId) -> dict:
    return await with_trello(lambda trello: trello.card(card_id))


@mcp.tool(
    annotations=WRITE,
    description="Move a card to another list. The target list is checked first, then the reason "
    "is posted as a comment, then the card moves.",
)
async def trello_move_card(
    card_id: CardId,
    to_list: Annotated[ListName, Field(description=LIST_DESCRIPTION)],
    reason: Annotated[str, text_field("Why the card moves; posted as a comment.", 3)],
) -> dict:
    return await with_trello(lambda trello: trello.move_with_reason(card_id, to_list, reason))


@mcp.tool(
    annotations=WRITE,
    description="Add a comment to a card: what was done, what was checked, what is left.",
)
async def trello_comment_card(
    card_id: CardId,
    text: Annotated[str, text_field("The comment, in plain words.")],
) -> dict:
    return await with_trello(lambda trello: trello.comment(card_id, text))


@mcp.tool(annotations=WRITE, description="Create a new card in a list of the factory board.")
async def trello_create_card(
    list_name: Annotated[ListName, Field(description=LIST_DESCRIPTION)],
    title: Annotated[str, text_field("A short imperative title.", 3)],
    description: Annotated[str, text_field("The story or idea in full, Markdown allowed.", 0)],
) -> dict:
    return await with_trello(lambda trello: trello.create(list_name, title, description))


@mcp.tool(
    annotations=WRITE,
    description="Replace a card's description, for example to turn an idea into a user story.",
)
async def trello_update_card_description(
    card_id: CardId,
    text: Annotated[str, text_field("The new description; replaces the old one entirely.", 0)],
) -> dict:
    return await with_trello(lambda trello: trello.set_description(card_id, text))


@mcp.tool(
    annotations=WRITE,
    description="Add a named label to a card; the board's colour for it is applied. Used by the "
    "product owner (type, Proposed via Telegram), the delivery lead and support (Depends on). "
    "Moves and creates already set the type, Shipped and the lane look.",
)
async def trello_add_label(
    card_id: CardId,
    name: Annotated[LabelName, Field(description=LABEL_DESCRIPTION)],
) -> dict:
    return await with_trello(lambda trello: trello.add_label(card_id, name))


@mcp.tool(
    annotations=WRITE,
    description=f"Give a card its '{CHECKLIST_NAME}' checklist, one item per criterion, in order. "
    "Used by the product owner when a story is written; replaces the card's existing criteria.",
)
async def trello_add_checklist(
    card_id: CardId,
    items: Annotated[
        list[Criterion],
        Field(
            min_length=3,
            max_length=8,
            description="Three to eight acceptance criteria, each 3 to 200 characters.",
        ),
    ],
) -> dict:
    return await with_trello(lambda trello: trello.add_checklist(card_id, tuple(items)))


@mcp.tool(
    annotations=WRITE,
    description=f"Tick one item of a card's '{CHECKLIST_NAME}' checklist once it is verified. "
    "Used by the tester; the exact text or its first words pick the item.",
)
async def trello_check_item(
    card_id: CardId,
    text: Annotated[
        str,
        Field(min_length=3, max_length=200, description="The criterion's text or first words."),
    ],
) -> dict:
    return await with_trello(lambda trello: trello.check_item(card_id, text))


@mcp.tool(
    annotations=WRITE,
    description="Mark a card high priority (a star sticker and the High severity label) or clear "
    "it. Used by the delivery lead and support for urgent work.",
)
async def trello_set_priority(
    card_id: CardId,
    high: Annotated[bool, Field(description="True to mark high priority, False to clear it.")],
) -> dict:
    return await with_trello(lambda trello: trello.set_priority(card_id, high))
