from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Literal, Protocol

from factory_demo.practices import OPERATOR_PREFIX

IN_FLIGHT_LANES = ("In Progress", "Review", "Testing")
LANE_LIMIT = 50
NOTES = {
    "pause": "the team is paused from {at}; the idle clock stops.",
    "resume": "the team resumed at {at}; the idle clock restarts now.",
}

Action = Literal["pause", "resume"]


class Board(Protocol):
    async def cards_in(self, list_name: str, limit: int) -> list[dict]: ...

    async def comment(self, card_id: str, text: str) -> dict: ...


def operator_notes(
    lanes_cards: Mapping[str, Sequence[dict]], action: Action, when: datetime
) -> tuple[tuple[str, str], ...]:
    at = when.astimezone(UTC).strftime("%H:%M")
    text = f"{OPERATOR_PREFIX} {NOTES[action].format(at=at)}"
    return tuple(
        (card["id"], text) for lane in IN_FLIGHT_LANES for card in lanes_cards.get(lane, ())
    )


async def post_operator_notes(
    trello: Board, action: Action, when: datetime
) -> tuple[tuple[str, str], ...]:
    lanes_cards = {lane: await trello.cards_in(lane, LANE_LIMIT) for lane in IN_FLIGHT_LANES}
    notes = operator_notes(lanes_cards, action, when)
    for card_id, text in notes:
        await trello.comment(card_id, text)
    return notes
