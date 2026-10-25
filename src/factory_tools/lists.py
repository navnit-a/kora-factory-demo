import re
from dataclasses import dataclass
from typing import Literal

DISPLAY_SEPARATOR = " · "
LEADING_SYMBOLS = re.compile(r"^[^0-9A-Za-z]+")


@dataclass(frozen=True)
class Lane:
    name: str
    display: str
    actor: str | None


LANES: tuple[Lane, ...] = (
    Lane("Ideas", "💡 Ideas · product owner shapes", "💡 Product owner"),
    Lane("Backlog", "📋 Backlog · delivery lead orders", "📋 Delivery lead"),
    Lane("Ready", "🟡 Ready · next for the developer", "📋 Delivery lead"),
    Lane("In Progress", "🛠 In Progress · senior developer builds", "🤖 Senior developer"),
    Lane("Review", "🔍 Review · code reviewer reads", "🔍 Code reviewer"),
    Lane("Testing", "🧪 Testing · tester proves", "🧪 Tester"),
    Lane("Done", "✅ Done · shipped", None),
    Lane("Blocked", "⛔ Blocked · needs a human", "🙋 Needs a human"),
    Lane("Agent ops", "🛰 Agent ops · watching the agents", "🛰 Agent ops"),
)

BOARD_LISTS: tuple[str, ...] = tuple(lane.name for lane in LANES)

ListName = Literal[
    "Ideas", "Backlog", "Ready", "In Progress", "Review", "Testing", "Done", "Blocked", "Agent ops"
]

LANES_BY_FOLDED_NAME: dict[str, Lane] = {lane.name.casefold(): lane for lane in LANES}


def lists_sentence() -> str:
    return "Lists are: " + ", ".join(BOARD_LISTS) + "."


def canonical_name(raw: str) -> str | None:
    stem = LEADING_SYMBOLS.sub("", raw).split(DISPLAY_SEPARATOR, 1)[0].strip()
    lane = LANES_BY_FOLDED_NAME.get(stem.casefold())
    return lane.name if lane else None


def display_name(name: str) -> str:
    return _lane(name).display


def actor_label(name: str) -> str | None:
    return _lane(name).actor


def lane_display_names() -> tuple[str, ...]:
    return tuple(lane.display for lane in LANES)


def _lane(name: str) -> Lane:
    lane = next((lane for lane in LANES if lane.name == name), None)
    if lane is None:
        raise ValueError(f"No lane named '{name}'. {lists_sentence()}")
    return lane
